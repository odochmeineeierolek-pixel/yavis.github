"""Einstellungen (JSON, lokal gespeichert)."""
from __future__ import annotations
import json, os
from dataclasses import dataclass, asdict, field
from pathlib import Path


def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    p = Path(base) / "YAVIS"
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class Settings:
    ollama_url: str = "http://127.0.0.1:11434"
    model: str = "llama3.2"
    address_as: str = "Master"
    emotion: str = "neutral"   # neutral | freundlich | liebevoll | traurig | wuetend
    request_timeout_s: int = 60
    allowed_dirs: list[str] = field(default_factory=list)
    voice_id: str = "w:kerstin-low:Warm"      # warme weibliche Standardstimme
    speak_replies: bool = True
    volume: float = 0.8
    piper_path: str = ""                      # leer = <Datenordner>/piper/piper.exe
    wake_names: list[str] = field(default_factory=lambda: ["YAVIS", "Hey YAVIS"])

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or data_dir() / "settings.json"
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
                return cls(**known)
            except (json.JSONDecodeError, TypeError):
                pass  # kaputte Datei -> Standardwerte
        return cls()

    def save(self, path: Path | None = None) -> None:
        path = path or data_dir() / "settings.json"
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
