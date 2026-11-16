"""Édition de la composition ; le lecteur reçoit toujours un instantané indépendant."""

from dataclasses import replace
from math import ceil

from makitop.model.composition import FORMATS, Transform
from makitop.model.effects import CATALOG, Effect
from makitop.model.media import MediaKind
from makitop.model.project import Project
from makitop.model.timeline import ImageClip, MediaClip, Timeline


class CompositionEditor:
    def __init__(self, session, playback, on_refresh=lambda: None):
        self.session = session
        self.playback = playback
        self.on_refresh = on_refresh
        self.selected_id = None
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

    def add_media(self, media):
        start = 0 if self.source_mode else self.playback.current_time()
        track = max((c.track for c in self.project.timeline.clips), default=-1) + 1
        clip = self._new_clip(media, start, track)
        self.project.timeline.add_clip(clip)
        self.selected_id = clip.id
        self._edited(start)
        return clip

    def select(self, clip_id):
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
        clips[index] = replace(clips[index], **changes)
        self._edited(position)

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
            self.update_clip(self.selected_id, transform=Transform())

    def remove_selected(self):
        if self.selected is None:
            return
        self.project.timeline.remove_clip(self.selected_id)
        self.selected_id = None
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

    def set_timeline_zoom(self, pixels_per_second):
        if pixels_per_second != self.project.view.timeline_zoom:
            self.project.view.timeline_zoom = pixels_per_second
            self.session.mark_dirty()

    def _edited(self, position=None):
        playing = self.playback.is_playing() and not self.source_mode
        self.session.mark_dirty()
        self.show_montage(position)
        if playing:
            self.playback.play()
