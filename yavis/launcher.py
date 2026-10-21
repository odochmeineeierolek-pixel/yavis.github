"""Programmauswahl: YAVIS startet NUR Programme, die du hinzugefuegt UND freigegeben hast."""
from __future__ import annotations
import json, os, subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable


@dataclass
class AppEntry:
    name: str
    path: str
    enabled: bool = False   # Standard: gesperrt, bis du es aktivierst


def _default_open(argv: list[str]) -> None:
    if hasattr(os, "startfile"):      # Windows: oeffnet .exe UND .lnk-Verknuepfungen
        os.startfile(argv[0])
    else:
        subprocess.Popen(argv)


def scan_start_menu(dirs: list[Path] | None = None) -> dict[str, str]:
    """Findet installierte Programme (Startmenue-Verknuepfungen). Nur Auflistung, nichts wird gestartet."""
    if dirs is None:
        dirs = [Path(os.environ.get(k, "")) / "Microsoft/Windows/Start Menu/Programs" for k in ("PROGRAMDATA", "APPDATA")]
    found: dict[str, str] = {}
    for d in dirs:
        if d.is_dir():
            for f in sorted(d.rglob("*.lnk")):
                if not any(w in f.stem.lower() for w in ("uninstall", "deinstall", "readme")):
                    found.setdefault(f.stem, str(f))
    return dict(sorted(found.items(), key=lambda kv: kv[0].lower()))


class Launcher:
    def __init__(self, store: Path | None = None, opener: Callable[[list[str]], object] | None = None) -> None:
        self.store, self.opener = store, opener or _default_open
        self.apps: dict[str, AppEntry] = {}
        if store and store.exists():
            try:
                for d in json.loads(store.read_text(encoding="utf-8")):
                    self.apps[d["name"]] = AppEntry(**d)
            except (json.JSONDecodeError, TypeError, KeyError):
                self.apps = {}

    def _save(self) -> None:
        if self.store:
            self.store.write_text(json.dumps([asdict(a) for a in self.apps.values()], indent=2), encoding="utf-8")

    def add(self, name: str, path: str) -> AppEntry:
        self.apps[name] = AppEntry(name, path); self._save(); return self.apps[name]

    def remove(self, name: str) -> bool:
        ok = self.apps.pop(name, None) is not None; self._save(); return ok

    def set_enabled(self, name: str, on: bool) -> None:
        if name in self.apps:
            self.apps[name].enabled = on; self._save()

    def launch(self, name: str) -> str:
        a = self.apps.get(name)
        if a is None: return f"Programm '{name}' ist nicht in der Liste."
        if not a.enabled: return f"'{name}' ist nicht freigegeben."
        if not Path(a.path).is_file(): return f"Datei nicht gefunden: {a.path}"
        try:
            self.opener([a.path])          # Liste, kein Shell-String -> keine Befehlseinschleusung
        except OSError as e:
            return f"Start fehlgeschlagen: {e}"
        return f"'{name}' wurde gestartet."


def register_tools(registry, launcher: Launcher) -> None:
    from .tools import Tool
    for name in launcher.apps:
        registry.register(Tool(f"open_{name.lower().replace(' ', '_')}", f"Programm {name} starten",
                               lambda n=name: launcher.launch(n)))
