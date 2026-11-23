"""Édition de la composition ; le lecteur reçoit toujours un instantané indépendant."""

import uuid
from dataclasses import replace
from math import ceil

from makitop.model.composition import FORMATS, Transform, with_zoom
from makitop.model.effects import CATALOG, Effect
from makitop.model.keyframes import PROPERTIES, Keyframe, curve, upsert
from makitop.model.media import MediaKind
from makitop.model.project import Project
from makitop.model.timeline import ImageClip, MediaClip, Timeline


class CompositionEditor:
    def __init__(self, session, playback, on_refresh=lambda: None):
        self.session = session
        self.playback = playback
        self.on_refresh = on_refresh
        self.selected_id = None
        self.selected_keyframe = None
        self.source_mode = False

    @property
    def project(self):
        return self.session.project

    @property
    def selected(self):
        return next((c for c in self.project.timeline.clips if c.id == self.selected_id), None)

    def show_montage(self, position=None):
        if position is None:
            position = 0 if self.source_mode else self.playback.current_time()
        self.source_mode = False
        self.playback.set_project(self.project, position)
        self.on_refresh()

    def preview_source(self, media):
        clip = self._new_clip(media, 0, 0)
        self.source_mode = True
        self.playback.set_project(Project(
            media=[media], timeline=Timeline(
                clips=[clip], fps=min(120, max(1, ceil(media.fps or self.project.timeline.fps))),
            ),
            canvas_format=self.project.canvas_format,
        ))
        self.on_refresh()

    @staticmethod
    def _new_clip(media, start, track):
        if media.kind == MediaKind.IMAGE:
            return ImageClip(start, media, 5.0, track=track)
        if media.kind != MediaKind.VIDEO or not media.duration or media.duration <= 0:
            raise ValueError("Choisissez une vidéo lisible ou une image.")
        return MediaClip(start, media, 0, media.duration, track=track)

    def add_media(self, media, start=None):
        if start is None:
            start = 0 if self.source_mode else self.playback.current_time()
        track = max((c.track for c in self.project.timeline.clips), default=-1) + 1
        clip = self._new_clip(media, start, track)
        self.project.timeline.add_clip(clip)
        self.selected_id = clip.id
        self._edited(start)
        return clip

    def select(self, clip_id):
        if clip_id != self.selected_id:
            self.selected_keyframe = None
        self.selected_id = clip_id
        clip = self.selected
        if clip is not None and (self.source_mode or not (
            clip.timeline_start <= self.playback.current_time() < clip.timeline_end
        )):
            self.show_montage(clip.timeline_start)
        else:
            self.on_refresh()

    def update_clip(self, clip_id, *, position=None, **changes):
        clips = self.project.timeline.clips
        index = next(i for i, c in enumerate(clips) if c.id == clip_id)
        clip = clips[index]
        # Modifier une propriété déjà animée crée/met à jour la clé sous la tête
        # de lecture ; les propriétés non animées restent des réglages constants.
        keys = clip.keyframes
        time = self.keyframe_time(clip)
        if "volume" in changes and curve(keys, "volume"):
            keys = self._value_key(keys, "volume", time, changes.pop("volume"))
            self.selected_keyframe = ("volume", time)
        if "transform" in changes:
            transform = changes["transform"]
            current = clip.transform_at(time)
            base = {}
            for name in ("x", "y", "width", "height"):
                if curve(keys, name):
                    if getattr(transform, name) != getattr(current, name):
                        keys = self._value_key(keys, name, time, getattr(transform, name))
                        self.selected_keyframe = (name, time)
                    base[name] = getattr(clip.transform, name)
            changes["transform"] = replace(transform, **base)
        if keys != clip.keyframes:
            changes["keyframes"] = keys
        clips[index] = replace(clips[index], **changes)
        self._edited(position)

    def keyframe_time(self, clip=None):
        clip = clip or self.selected
        if clip is None:
            raise ValueError("Sélectionnez un clip.")
        time = self.playback.current_time() - clip.timeline_start
        # Conserver les clés hors grille (projet dont la cadence a changé).
        for key in clip.keyframes:
            if abs(key.time - time) < 1e-8:
                return key.time
        fps = self.project.timeline.fps
        return min(clip.duration, max(0, round(time * fps) / fps))

    @staticmethod
    def _value_key(keys, property, time, value):
        existing = next((k for k in curve(keys, property) if abs(k.time - time) < 1e-9), None)
        mode = existing.interpolation if existing else "linear"
        return upsert(keys, Keyframe(property, time, value, mode))

    def set_animated_value(self, property, value):
        clip = self.selected
        if clip is None:
            return
        if property == "zoom":
            if curve(clip.keyframes, "zoom"):
                time = self.keyframe_time()
                keys = self._value_key(clip.keyframes, "zoom", time, value)
                replace(clip, keyframes=keys).transform_at(time)
                self.selected_keyframe = ("zoom", time)
                self.update_clip(clip.id, keyframes=keys)
            else:
                self.update_clip(clip.id, transform=with_zoom(clip.transform, value))
        elif property == "volume":
            self.update_clip(clip.id, volume=value)
        else:
            transform = replace(clip.transform_at(self.keyframe_time()), **{property: value})
            self.update_clip(clip.id, transform=transform)

    def set_selected_keyframe_value(self, value):
        """Modifie la clé sélectionnée, indépendamment de la tête de lecture."""
        clip = self.selected
        if clip is None or self.selected_keyframe is None:
            return
        property, time = self.selected_keyframe
        key = next((k for k in clip.keyframes if (k.property, k.time) == (property, time)), None)
        if key is None:
            raise ValueError("Image clé introuvable.")
        if value == key.value:
            return
        keys = upsert(clip.keyframes, replace(key, value=value))
        if property == "zoom":
            replace(clip, keyframes=keys).transform_at(time)
        self.update_clip(clip.id, keyframes=keys)

    def toggle_keyframe(self, property):
        clip = self.selected
        if clip is None or property not in PROPERTIES:
            raise ValueError("Sélectionnez un clip et une propriété animable.")
        self.playback.pause()
        time = self.keyframe_time()
        if any(k.property == property and abs(k.time - time) < 1e-9 for k in clip.keyframes):
            self.remove_keyframe(property, time)
            return
        value = (clip.volume_at(time) if property == "volume"
                 else clip.transform_at(time).width if property == "zoom"
                 else getattr(clip.transform_at(time), property))
        self.selected_keyframe = (property, time)
        self.update_clip(clip.id, keyframes=upsert(clip.keyframes, Keyframe(property, time, value)))

    def select_keyframe(self, clip_id, property, time):
        clip = next(c for c in self.project.timeline.clips if c.id == clip_id)
        if not any(k.property == property and k.time == time for k in clip.keyframes):
            raise ValueError("Image clé introuvable.")
        self.playback.pause()
        self.selected_id = clip_id
        self.selected_keyframe = (property, time)
        self.show_montage(clip.timeline_start + time)

    def move_keyframe(self, property, time, new_time):
        clip = self.selected
        if clip is None:
            return
        if not 0 <= new_time <= clip.duration:
            raise ValueError("L'image clé doit rester dans la durée du clip.")
        old = next(k for k in clip.keyframes if k.property == property and k.time == time)
        if any(k is not old and k.property == property and abs(k.time - new_time) < 1e-9
               for k in clip.keyframes):
            raise ValueError("Une image clé existe déjà à cet instant pour cette propriété.")
        keys = tuple(k for k in clip.keyframes if k is not old)
        keys = upsert(keys, replace(old, time=new_time))
        self.selected_keyframe = (property, new_time)
        self.update_clip(clip.id, keyframes=keys, position=clip.timeline_start + new_time)

    def remove_keyframe(self, property=None, time=None):
        clip = self.selected
        if clip is None:
            return
        if property is None:
            if self.selected_keyframe is None:
                return
            property, time = self.selected_keyframe
        keys = tuple(k for k in clip.keyframes if not (k.property == property and k.time == time))
        self.selected_keyframe = None
        self.update_clip(clip.id, keyframes=keys)

    def set_keyframe_interpolation(self, mode):
        clip = self.selected
        if clip is None or self.selected_keyframe is None:
            return
        property, time = self.selected_keyframe
        keys = tuple(replace(k, interpolation=mode) if (k.property, k.time) == (property, time)
                     else k for k in clip.keyframes)
        self.update_clip(clip.id, keyframes=keys)

    def adjacent_keyframe(self, direction):
        clip = self.selected
        if clip is None:
            return
        time = self.playback.current_time() - clip.timeline_start
        keys = sorted((k for k in clip.keyframes if 0 <= k.time <= clip.duration
                       and (k.time - time) * direction > 1e-8),
                      key=lambda k: k.time, reverse=direction < 0)
        if keys:
            key = keys[0]
            self.select_keyframe(clip.id, key.property, key.time)

    def set_format(self, value):
        if value not in FORMATS:
            raise ValueError("Format de composition inconnu.")
        self.project.canvas_format = value
        self._edited()

    def set_fps(self, value):
        # Valide avant de modifier le projet ; les positions restent en secondes.
        timeline = replace(self.project.timeline, fps=value)
        self.project.timeline = timeline
        self._edited()

    def move_layer(self, direction):
        clip = self.selected
        if clip is None:
            return
        target = clip.track + direction
        if not 0 <= target <= 99:
            return
        previous = clip.track
        for current in self.project.timeline.clips:
            if current.track == previous:
                current.track = target
            elif current.track == target:
                current.track = previous
        self._edited()

    def add_effect(self, kind):
        clip = self.selected
        if clip is None:
            raise ValueError("Sélectionnez un clip dans la timeline.")
        if any(e.kind == kind for e in clip.effects):
            raise ValueError("Effet déjà appliqué à ce clip.")
        effect = Effect(kind, CATALOG[kind].default)
        self.update_clip(clip.id, effects=clip.effects + (effect,))

    def update_effect(self, index, amount):
        clip = self.selected
        if clip is None:
            return
        effects = list(clip.effects)
        effects[index] = Effect(effects[index].kind, amount)
        self.update_clip(clip.id, effects=tuple(effects))

    def remove_effect(self, index):
        clip = self.selected
        if clip is None:
            return
        self.update_clip(clip.id, effects=clip.effects[:index] + clip.effects[index + 1:])

    def reset_transform(self):
        if self.selected is not None:
            clip = self.selected
            # Réinitialiser enlève aussi l'animation géométrique, en conservant le son.
            self.selected_keyframe = None
            clips = self.project.timeline.clips
            index = next(i for i, c in enumerate(clips) if c.id == clip.id)
            clips[index] = replace(clip, transform=Transform(), keyframes=tuple(
                k for k in clip.keyframes if k.property == "volume"
            ))
            self._edited()

    def remove_selected(self):
        if self.selected is None:
            return
        self.project.timeline.remove_clip(self.selected_id)
        self.selected_id = None
        self.selected_keyframe = None
        self._edited()

    def seek(self, position):
        if self.source_mode:
            self.show_montage(position)
        else:
            self.playback.seek(position)

    def sync_playhead(self):
        """Reporte la position de lecture dans le projet (appelé à chaque image).

        Elle est enregistrée avec le projet ; la déplacer (clic, lecture, Stop) le
        marque comme modifié. L'aperçu d'un média seul ne touche pas au montage.
        """
        if self.source_mode:
            return
        position = round(self.playback.current_time(), 3)
        if position != self.project.view.playhead:
            self.project.view.playhead = position
            self.session.mark_dirty()

    def rows(self):
        """Clips dans l'ordre des lignes de la timeline : de la piste du fond (0) vers
        le premier plan. À piste égale, l'ordre de la liste du montage est conservé."""
        return sorted(self.project.timeline.clips, key=lambda clip: clip.track)

    def reorder_row(self, clip_id, row):
        """Le clip `clip_id` a été glissé à la ligne `row` de la timeline (0 = en haut).

        Le changement doit être reporté dans le modèle, sinon il disparaît au
        prochain rafraîchissement et n'est pas enregistré. Les pistes sont renumérotées
        0, 1, 2... dans le nouvel ordre : descendre une ligne fait passer le clip devant.
        """
        rows = self.rows()
        clip = next((c for c in rows if c.id == clip_id), None)
        if clip is None:
            return
        rows.remove(clip)
        rows.insert(max(0, min(row, len(rows))), clip)
        for track, current in enumerate(rows):
            current.track = min(track, 99)
        self._edited()

    def split_at_playhead(self):
        t = self.playback.current_time()
        timeline = self.project.timeline
        clips_to_split = [
            c for c in timeline.clips
            if c.timeline_start + 1e-6 < t < c.timeline_end - 1e-6
        ]
        if not clips_to_split:
            return
        for clip in clips_to_split:
            local_t = t - clip.timeline_start
            left_kf = tuple(k for k in clip.keyframes if k.time <= local_t)
            right_kf = tuple(
                replace(k, time=k.time - local_t)
                for k in clip.keyframes if k.time >= local_t
            )
            if isinstance(clip, MediaClip):
                left = replace(clip,
                               source_end=clip.source_start + local_t,
                               keyframes=left_kf)
                right = replace(clip,
                                id=uuid.uuid4().hex,
                                timeline_start=t,
                                source_start=clip.source_start + local_t,
                                keyframes=right_kf)
            elif isinstance(clip, ImageClip):
                left = replace(clip, display_duration=local_t, keyframes=left_kf)
                right = replace(clip,
                                id=uuid.uuid4().hex,
                                timeline_start=t,
                                display_duration=clip.timeline_end - t,
                                keyframes=right_kf)
            else:
                continue
            timeline.remove_clip(clip.id)
            timeline.add_clip(left)
            timeline.add_clip(right)
            if self.selected_id == clip.id:
                self.selected_id = left.id
        self._edited(t)

    def duplicate_selected(self):
        clip = self.selected
        if clip is None:
            return
        new_start = clip.timeline_end
        new_end = new_start + clip.duration
        same_track_free = not any(
            c.track == clip.track
            and c.timeline_start < new_end - 1e-6
            and c.timeline_end > new_start + 1e-6
            for c in self.project.timeline.clips
        )
        if same_track_free:
            target_track = clip.track
        else:
            existing = self.project.timeline.clips
            target_track = (max(c.track for c in existing) + 1) if existing else 0
        new_id = uuid.uuid4().hex
        if isinstance(clip, (MediaClip, ImageClip)):
            dup = replace(clip, id=new_id, timeline_start=new_start, track=target_track)
        else:
            return
        self.project.timeline.add_clip(dup)
        self.selected_id = new_id
        self._edited(dup.timeline_start)

    def set_timeline_zoom(self, pixels_per_second):
        pass

    def _edited(self, position=None):
        playing = self.playback.is_playing() and not self.source_mode
        self.session.mark_dirty()
        self.show_montage(position)
        if playing:
            self.playback.play()
