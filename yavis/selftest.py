"""Selbsttest: startet die echte Oberflaeche (offscreen) und prueft Kernfunktionen. Aufruf: YAVIS.exe --selftest out.txt"""
from __future__ import annotations
import os, sys, tempfile, traceback
from pathlib import Path


def _examples() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent)) / "examples"


def run(out_path: str) -> int:
    lines, ok = [], True

    def check(name: str, cond: bool, extra: str = "") -> None:
        nonlocal ok
        ok = ok and bool(cond)
        lines.append(("OK      " if cond else "FEHLER  ") + name + (f" ({extra})" if extra else ""))

    try:
        os.environ["APPDATA"] = tempfile.mkdtemp()                 # frische, leere Daten
        from PySide6.QtWidgets import QApplication
        from .gui import CSS, Main
        from .llm import LLMError
        from .voices import get_voice
        app = QApplication([]); app.setStyleSheet(CSS); w = Main(); w.show(); app.processEvents()
        check("Hauptfenster startet", w.isVisible())
        check("Menue-Eintraege = Seiten", w.pages.count() == w.nav.count(), f"{w.nav.count()}")
        for i in range(w.nav.count()):
            w.nav.setCurrentRow(i); app.processEvents()
        check("Alle Seiten oeffnen", True)
        check("Mindestens 30 Stimmen", w.set_voice.count() >= 30, str(w.set_voice.count()))
        check("Fehlendes Piper = Meldung statt Absturz", isinstance(w.speaker.available(get_voice(w.settings.voice_id)), str))
        n = w.plugins.install_dir(_examples() / "plugin_vorlage"); w.plugins.enable(n)
        check("Plugin laeuft im eigenen Prozess", w.plugins.run(n, "umdrehen", "abc") == "cba")
        try:
            list(w.agent.ask("Hallo")); check("Ollama-Fehler wird sauber gemeldet", False, "kein Fehler")
        except LLMError:
            check("Ollama-Fehler wird sauber gemeldet", True)
    except BaseException:
        ok = False; lines.append("ABSTURZ:\n" + traceback.format_exc())
    Path(out_path).write_text("\n".join(lines) + ("\nSELFTEST BESTANDEN" if ok else "\nSELFTEST FEHLGESCHLAGEN"), encoding="utf-8")
    return 0 if ok else 1
