"""Édition de la composition ; le lecteur reçoit toujours un instantané indépendant."""

import copy
import uuid
from dataclasses import replace
from math import ceil

from makitop.model.composition import FORMATS, Transform, normalize_angle, with_zoom
from makitop.model.effects import CATALOG, Effect
from makitop.model.keyframes import PROPERTIES, Keyframe, curve, upsert, value_at
from makitop.model.media import MediaKind
from makitop.model.project import Project
from makitop.model.text import PRESETS
from makitop.model.timeline import ImageClip, MediaClip, TextClip, Timeline
from makitop.model.transitions import Transition, span_for


class CompositionEditor:
    def __init__(self, session, playback, on_refresh=lambda: None):
        self.session = session
        self.playback = playback
        self.on_refresh = on_refresh
        self.selected_id = None
        self.selected_keyframe = None
        self._clipboard = None
        self._undo_stack: list = []
        self._redo_stack: list = []
        self._MAX_UNDO = 50

    @property
    def project(self):
        return self.session.project

    @property
    def selected(self):
        return next((c for c in self.project.timeline.clips if c.id == self.selected_id), None)

    def show_montage(self, position=None):
        if position is None:
            position = self.playback.current_time()
        self.playback.set_project(self.project, position)
        self.on_refresh()

    @staticmethod
    def _new_clip(media, start, track):
        if media.kind == MediaKind.IMAGE:
            return ImageClip(start, media, 5.0, track=track)
        if media.kind != MediaKind.VIDEO or not media.duration or media.duration <= 0:
            raise ValueError("Choisissez une vidéo lisible ou une image.")
        return MediaClip(start, media, 0, media.duration, track=track)

    def add_media(self, media, start=None):
        self.push_undo()
        if start is None:
            start = self.playback.current_time()
        track = max((c.track for c in self.project.timeline.clips), default=-1) + 1
        clip = self._new_clip(media, start, track)
        self.project.timeline.add_clip(clip)
        self.selected_id, self.selected_keyframe = clip.id, None
        self._edited(start)
        return clip

    def add_text(self, preset: str, start: float | None = None,
                 new_track: bool = False) -> TextClip:
        self.push_undo()
        template = PRESETS[preset]
        if start is None:
            start = self.playback.current_time()
        duration = 5.0
        clips = self.project.timeline.clips
        front_media = max((c.track for c in clips if not isinstance(c, TextClip)), default=-1)
        if new_track:
            track = max((c.track for c in clips), default=-1) + 1
        else:
            occupied = {c.track for c in clips
                        if start < c.timeline_end and c.timeline_start < start + duration}
            track = next((track for track in range(front_media + 1, 100)
                          if track not in occupied), None)
        if track is None:
            raise ValueError("Aucune piste libre au premier plan à cet instant.")
        clip = TextClip(start, duration, template.content, style=template.style,
                        transform=template.box, track=track)
        self.project.timeline.add_clip(clip)
        self.selected_id, self.selected_keyframe = clip.id, None
        self._edited(start)
        return clip

    def update_text_style(self, **changes):
        clip = self.selected
        if isinstance(clip, TextClip):
            style = replace(clip.style, **changes)
            if style != clip.style:
                self.update_clip(clip.id, style=style)

    def set_clip_orientation(self, *, rotation=None, flip_horizontal=None, flip_vertical=None):
        clip = self.selected
        if clip is None or isinstance(clip, TextClip) or clip.media.kind == MediaKind.AUDIO:
            return
        transform = clip.transform
        updated = replace(
            transform,
            rotation=transform.rotation if rotation is None else normalize_angle(rotation),
            flip_horizontal=(transform.flip_horizontal if flip_horizontal is None
                             else flip_horizontal),
            flip_vertical=transform.flip_vertical if flip_vertical is None else flip_vertical,
        )
        if updated != transform:
            self.update_clip(clip.id, transform=updated, animate_transform=False)

    def set_clip_speed(self, speed):
        clip = self.selected
        if not isinstance(clip, MediaClip):
            return
        # Valider avant de déplacer la tête de lecture ou les images clés.
        updated = replace(clip, speed=speed)
        if updated.speed == clip.speed:
            return
        factor = clip.speed / updated.speed
        keys = tuple(replace(key, time=key.time * factor) for key in clip.keyframes)
        current = self.playback.current_time()
        if clip.timeline_start <= current <= clip.timeline_end:
            current = clip.timeline_start + (current - clip.timeline_start) * factor
        if self.selected_keyframe is not None:
            name, time = self.selected_keyframe
            self.selected_keyframe = (name, time * factor)
        self.update_clip(clip.id, speed=updated.speed, keyframes=keys, position=current)

    def resize_animated_box(self, displayed, zoom_scale):
        """Applique la boîte visible en tenant compte d'une courbe de zoom existante."""
        clip = self.selected
        if clip is None:
            return
        time = self.keyframe_time(clip)
        before = clip.unzoomed_transform_at(time)
        scale = max(zoom_scale, displayed.width / 8, displayed.height / 8)
        width, height = displayed.width / scale, displayed.height / scale
        box = replace(
            displayed, width=width, height=height,
            x=displayed.x + (displayed.width - width) / 2,
            y=displayed.y + (displayed.height - height) / 2,
        )
        keys = clip.keyframes
        base = {}
        selected = self.selected_keyframe
        for name in ("x", "y", "width", "height"):
            if curve(keys, name):
                value = getattr(box, name)
                if abs(value - getattr(before, name)) > 1e-9:
                    keys = self._value_key(keys, name, time, value)
                    selected = (name, time)
                base[name] = getattr(clip.transform, name)
        if abs(displayed.width - clip.transform_at(time).width) > 1e-9:
            keys = self._value_key(keys, "zoom", time, displayed.width)
            selected = ("zoom", time)
        transform = replace(box, **base)
        self.selected_keyframe = selected
        self.update_clip(clip.id, transform=transform, keyframes=keys, animate_transform=False)

    def select(self, clip_id):
        if clip_id != self.selected_id:
            self.selected_keyframe = None
        self.selected_id = clip_id
        clip = self.selected
        if clip is not None and not (
            clip.timeline_start <= self.playback.current_time() < clip.timeline_end
        ):
            self.show_montage(clip.timeline_start)
        else:
            self.on_refresh()

    @property
    def selected_transition(self):
        return next((t for t in self.project.timeline.transitions
                     if t.incoming_id == self.selected_id), None)

    def apply_transition(self, kind):
        incoming = self.selected
        if (not isinstance(incoming, (ImageClip, MediaClip))
                or incoming.media.kind == MediaKind.AUDIO):
            raise ValueError("Sélectionnez le clip d’arrivée dans la timeline.")
        timeline = self.project.timeline
        previous = self.selected_transition
        cut = incoming.timeline_start
        candidates = [
            clip for clip in timeline.clips if isinstance(clip, (ImageClip, MediaClip))
            and clip.media.kind != MediaKind.AUDIO
            and clip.timeline_start < cut - 1e-8
            and clip.timeline_end >= cut - 1 / timeline.fps - 1e-8
        ]
        if not candidates:
            raise ValueError("Le clip d’arrivée doit toucher ou chevaucher un clip précédent.")
        outgoing = max(candidates, key=lambda clip: (
            previous is not None and clip.id == previous.outgoing_id,
            clip.track == incoming.track, clip.timeline_start, clip.track,
        ))
        if any(t.outgoing_id == outgoing.id and t.incoming_id != incoming.id
               for t in timeline.transitions):
            raise ValueError("Le clip précédent est déjà relié à une autre transition.")
        transition = Transition(
            outgoing.id, incoming.id, kind, previous.duration if previous else 0.8,
        )
        span = span_for(transition, outgoing, incoming, 1 / timeline.fps)
        if span is None:
            raise ValueError("Impossible de placer une transition à cette jonction.")
        if transition == previous:
            self._preview_transition(transition)
            return
        self.push_undo()
        timeline.transitions = (*(
            t for t in timeline.transitions if t.incoming_id != incoming.id
        ), transition)
        self._preview_transition(transition)

    def set_transition_duration(self, seconds):
        current = self.selected_transition
        if current is None:
            return
        updated = replace(current, duration=round(seconds, 3))
        if updated == current:
            return
        self.push_undo()
        timeline = self.project.timeline
        timeline.transitions = tuple(updated if t is current else t for t in timeline.transitions)
        self._preview_transition(updated)

    def _preview_transition(self, transition):
        spans = self.project.timeline.transition_spans()
        span = next((item for item in spans if item.transition == transition), None)
        self._edited((span.start + span.end) / 2 if span is not None else None)

    def remove_transition(self):
        current = self.selected_transition
        if current is not None:
            self.push_undo()
            timeline = self.project.timeline
            timeline.transitions = tuple(t for t in timeline.transitions if t is not current)
            self._edited()

    def update_clip(self, clip_id, *, position=None, animate_transform=True, **changes):
        self.push_undo()
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
        if animate_transform and "transform" in changes:
            transform = changes["transform"]
            current = (clip.unzoomed_transform_at(time) if isinstance(clip, TextClip)
                       else clip.transform_at(time))
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
            time = self.keyframe_time()
            transform = (clip.unzoomed_transform_at(time) if isinstance(clip, TextClip)
                         else clip.transform_at(time))
            transform = replace(transform, **{property: value})
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
        if clip is None or property not in clip.keyframe_properties:
            raise ValueError("Sélectionnez un clip et une propriété animable.")
        self.playback.pause()
        time = self.keyframe_time()
        if any(k.property == property and abs(k.time - time) < 1e-9 for k in clip.keyframes):
            self.remove_keyframe(property, time)
            return
        if property == "volume":
            value = clip.volume_at(time)
        elif property == "opacity":
            value = clip.opacity_at(time)
        elif isinstance(clip, TextClip) and property != "zoom":
            value = getattr(clip.unzoomed_transform_at(time), property)
        else:
            value = getattr(clip.transform_at(time), "width" if property == "zoom" else property)
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
        self.push_undo()
        if value not in FORMATS:
            raise ValueError("Format de composition inconnu.")
        self.project.canvas_format = value
        self._edited()

    def set_fps(self, value):
        self.push_undo()
        # Valide avant de modifier le projet ; les positions restent en secondes.
        timeline = replace(self.project.timeline, fps=value)
        self.project.timeline = timeline
        self._edited()

    def move_layer(self, direction):
        self.push_undo()
        clip = self.selected
        if clip is None:
            self._undo_stack.pop()
            return
        previous = clip.track
        tracks = {c.track for c in self.project.timeline.clips
                  if (c.track - previous) * direction > 0}
        if not tracks:
            return
        target = min(tracks) if direction > 0 else max(tracks)
        for current in self.project.timeline.clips:
            if current.track == previous:
                current.track = target
            elif current.track == target:
                current.track = previous
        self._edited()

    def add_effect(self, kind):
        clip = self.selected
        if clip is None or isinstance(clip, TextClip):
            raise ValueError("Sélectionnez une vidéo ou une image dans la timeline.")
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
        if self.selected is None:
            return
        self.push_undo()
        clip = self.selected
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
        self.push_undo()
        self.project.timeline.remove_clip(self.selected_id)
        self.selected_id = None
        self.selected_keyframe = None
        self._edited()

    def seek(self, position):
        self.playback.seek(position)

    def sync_playhead(self):
        """Reporte la position de lecture dans le projet (appelé à chaque image)."""
        position = round(self.playback.current_time(), 3)
        self.project.view.playhead = position

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
        self.push_undo()
        rows = self.rows()
        clip = next((c for c in rows if c.id == clip_id), None)
        if clip is None:
            return
        rows.remove(clip)
        rows.insert(max(0, min(row, len(rows))), clip)
        for track, current in enumerate(rows):
            current.track = min(track, 99)
        self._edited()

    @staticmethod
    def _kf_default(clip, prop):
        if prop == "volume":
            return clip.volume
        if prop == "zoom":
            return clip.transform.width
        return getattr(clip.transform, prop, 1.0)

    def split_at_playhead(self):
        t = self.playback.current_time()
        timeline = self.project.timeline
        clips_to_split = [
            c for c in timeline.clips
            if c.timeline_start + 1e-6 < t < c.timeline_end - 1e-6
        ]
        if not clips_to_split:
            return
        self.push_undo()
        for clip in clips_to_split:
            local_t = t - clip.timeline_start
            left_kf = tuple(k for k in clip.keyframes if k.time <= local_t)
            right_kf = tuple(
                replace(k, time=k.time - local_t)
                for k in clip.keyframes if k.time >= local_t
            )
            # Keyframe synthétique au point de coupe pour préserver la valeur interpolée
            for prop in {k.property for k in clip.keyframes}:
                default = self._kf_default(clip, prop)
                val = value_at(clip.keyframes, prop, local_t, default)
                # Interpolation active à local_t (du segment qui part du dernier kf avant)
                pts = sorted((k for k in clip.keyframes if k.property == prop),
                             key=lambda k: k.time)
                interp = next((k.interpolation for k in reversed(pts)
                               if k.time <= local_t), "linear")
                if not any(k.property == prop and abs(k.time - local_t) < 1e-9
                           for k in left_kf):
                    left_kf = upsert(left_kf, Keyframe(prop, local_t, val, interp))
                if not any(k.property == prop and abs(k.time) < 1e-9
                           for k in right_kf):
                    right_kf = upsert(right_kf, Keyframe(prop, 0.0, val, interp))
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

    def copy_selected(self):
        if self.selected is not None:
            self._clipboard = self.selected

    def cut_selected(self):
        clip = self.selected
        if clip is None:
            return
        self.push_undo()
        self._clipboard = clip
        self.project.timeline.remove_clip(clip.id)
        self.selected_id = None
        self._edited()

    def paste_clip(self):
        if self._clipboard is None:
            return
        self.push_undo()
        clip = self._clipboard
        new_start = self.playback.current_time()
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
            pasted = replace(clip, id=new_id, timeline_start=new_start, track=target_track)
        else:
            return
        self.project.timeline.add_clip(pasted)
        self.selected_id = new_id
        self._edited(new_start)

    def duplicate_selected(self):
        clip = self.selected
        if clip is None:
            return
        self.push_undo()
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

    def push_undo(self):
        self._undo_stack.append({
            "timeline": copy.deepcopy(self.project.timeline),
            "selected_id": self.selected_id,
            "selected_keyframe": self.selected_keyframe,
            "position": self.playback.current_time(),
        })
        if len(self._undo_stack) > self._MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self):
        if not self._undo_stack:
            return
        self._redo_stack.append({
            "timeline": copy.deepcopy(self.project.timeline),
            "selected_id": self.selected_id,
            "selected_keyframe": self.selected_keyframe,
            "position": self.playback.current_time(),
        })
        self._restore(self._undo_stack.pop())

    def redo(self):
        if not self._redo_stack:
            return
        self._undo_stack.append({
            "timeline": copy.deepcopy(self.project.timeline),
            "selected_id": self.selected_id,
            "selected_keyframe": self.selected_keyframe,
            "position": self.playback.current_time(),
        })
        self._restore(self._redo_stack.pop())

    def _restore(self, snapshot):
        self.project.timeline = snapshot["timeline"]
        self.selected_id = snapshot["selected_id"]
        self.selected_keyframe = snapshot["selected_keyframe"]
        playing = self.playback.is_playing()
        self.session.mark_dirty()
        self.show_montage(snapshot["position"])
        if playing:
            self.playback.play()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def _edited(self, position=None):
        playing = self.playback.is_playing()
        self.session.mark_dirty()
        self.show_montage(position)
        if playing:
            self.playback.play()
