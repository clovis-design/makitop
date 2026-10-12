"""Édition de la composition ; le lecteur reçoit toujours un instantané indépendant."""

from dataclasses import replace

from makitop.model.composition import FORMATS, Transform
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
            media=[media], timeline=Timeline(clips=[clip]),
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

    def _edited(self, position=None):
        playing = self.playback.is_playing() and not self.source_mode
        self.session.mark_dirty()
        self.show_montage(position)
        if playing:
            self.playback.play()
