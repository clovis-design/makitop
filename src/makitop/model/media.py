from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator


class Media(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: Path
    name: str = ""

    @model_validator(mode="after")
    def _default_name(self) -> "Media":
        if not self.name:
            object.__setattr__(self, "name", self.path.stem)
        return self

class Video(Media):
    duration: float
    width: int
    height: int
    fps: float

# Classes Photos, Audio...