"""Playlist-Logik (ohne Audio-Backend, daher testbar). Wiedergabe macht die GUI via QtMultimedia."""
from __future__ import annotations
import random
from pathlib import Path

EXT = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}


class Playlist:
    def __init__(self, tracks: list[Path] | None = None, shuffle: bool = False) -> None:
        self.tracks, self.index, self.shuffle = list(tracks or []), -1, shuffle

    @classmethod
    def scan(cls, folder: str | Path) -> "Playlist":
        files = sorted(p for p in Path(folder).rglob("*") if p.suffix.lower() in EXT)
        return cls(files)

    def current(self) -> Path | None:
        return self.tracks[self.index] if 0 <= self.index < len(self.tracks) else None

    def next(self) -> Path | None:
        n = len(self.tracks)
        if n == 0:
            return None
        if self.shuffle and n > 1:
            self.index = random.choice([i for i in range(n) if i != self.index])
        else:
            self.index = (self.index + 1) % n
        return self.current()

    def prev(self) -> Path | None:
        if not self.tracks:
            return None
        self.index = (self.index - 1) % len(self.tracks)
        return self.current()
