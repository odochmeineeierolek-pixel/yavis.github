"""PySide6-Oberflaeche (Schwarz/Rot/Gelb). ACHTUNG: noch nicht auf Windows ausgefuehrt."""
from __future__ import annotations
import math, sys, threading
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QUrl
from PySide6.QtGui import QPainter, QConicalGradient, QColor, QPen
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget,
    QListWidgetItem, QStackedWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QGridLayout, QFileDialog, QSlider, QComboBox, QCheckBox, QMessageBox, QInputDialog)
from pathlib import Path
from .agent import Agent, build_system_prompt
from .config import Settings, data_dir
from .launcher import Launcher, register_tools, scan_start_menu
from .llm import OllamaClient, LLMError
from .memory import Memory
from .extras import register_extras
from .music import Playlist
from .plugins import PluginManager, PluginError, generate_plugin
from .tools import default_registry
from .tts import Speaker, TTSError
from .voices import build_catalog, get_voice
from .wakewords import validate_names

CSS = """* {color:#f2f2f2; font-family:'Segoe UI'; font-size:14px;}
QMainWindow,QWidget#bg {background:#0a0a0a;} QListWidget#nav {background:#0d0d0d; border:none; font-size:16px;}
QListWidget#nav::item {padding:12px;} QListWidget#nav::item:selected {background:#3a2f0a; color:#ffd400; border-radius:8px;}
QLineEdit,QTextEdit,QListWidget {background:#121212; border:1px solid #c01818; border-radius:10px; padding:8px;}
QPushButton {background:#1a1a1a; border:1px solid #444; border-radius:8px; padding:8px 14px;}
QPushButton:hover {border-color:#ffd400;} QPushButton#go {background:#ffd400; color:#000; font-weight:bold;}
QFrame#card,QLabel#card {background:#141414; border:1px solid #2a2a2a; border-radius:12px; padding:14px;}"""


class Orb(QWidget):
    """Leuchtender Ring; pulsiert staerker, solange YAVIS antwortet."""
    def __init__(self) -> None:
        super().__init__(); self.setMinimumSize(180, 180); self.level, self.t = 0.2, 0.0
        tm = QTimer(self); tm.timeout.connect(self._tick); tm.start(33)
    def _tick(self) -> None:
        self.t += 0.12; self.update()
    def paintEvent(self, _) -> None:
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        c = self.rect().center(); r = min(self.width(), self.height()) / 2 - 14
        r += 8 * self.level * math.sin(self.t * 2)
        g = QConicalGradient(c, -self.t * 20)
        for pos, col in ((0, "#ff1a1a"), (0.5, "#ffd400"), (1, "#ff1a1a")): g.setColorAt(pos, QColor(col))
        p.setPen(QPen(g, 6)); p.drawEllipse(c, r, r)
        p.setPen(QColor("#ffd400")); p.drawText(self.rect(), Qt.AlignCenter, "YAVIS")


class Bridge(QObject):
    piece, done = Signal(str), Signal()
    speak_ready, notice, ask_confirm = Signal(str), Signal(str), Signal(str)
    plugins_changed = Signal()


class Main(QMainWindow):
    NAV = ["Home", "Chat", "Musik", "Programme", "Plugins", "Einstellungen"]

    def __init__(self) -> None:
        super().__init__(); self.setWindowTitle("YAVIS"); self.resize(1200, 760)
        self.settings = s = Settings.load(); self.launcher = Launcher(data_dir() / "apps.json")
        self.reg = reg = default_registry(); register_tools(reg, self.launcher)
        self.memory = Memory(data_dir() / 'memory.db'); self.timers = register_extras(reg, self.memory)
        self.plugins = PluginManager(data_dir() / 'plugins'); self.plugins.sync(reg)
        self._cevt, self._cok = threading.Event(), False
        poll = QTimer(self); poll.timeout.connect(lambda: [self.statusBar().showMessage(f'Timer fertig: {l}', 15000) for l in self.timers.due()]); poll.start(1000)
        self.agent = Agent(OllamaClient(s.ollama_url, s.model, s.request_timeout_s), s, reg, confirm=self._confirm, lessons=self.memory.lessons())
        self.bridge = Bridge(); self.bridge.piece.connect(self._on_piece); self.bridge.done.connect(self._on_done)
        self.bridge.ask_confirm.connect(self._on_ask_confirm); self.bridge.plugins_changed.connect(self._refresh_plugins)
        self.bridge.speak_ready.connect(self._play_voice); self.bridge.notice.connect(lambda m: self.statusBar().showMessage(m, 10000))
        pdir = Path(s.piper_path).parent if s.piper_path else data_dir() / "piper"
        self.speaker = Speaker(Path(s.piper_path) if s.piper_path else pdir / "piper.exe", pdir / "voices")
        self.voices, self._gen, self._reply = build_catalog(), 0, ""
        self.voice_player, self.voice_audio = QMediaPlayer(), QAudioOutput(); self.voice_player.setAudioOutput(self.voice_audio)
        self.voice_audio.setVolume(s.volume)
        self.voice_player.playbackStateChanged.connect(lambda st: setattr(self.orb, "level", 1.0 if st == QMediaPlayer.PlayingState else 0.2))
        self.playlist = Playlist(); self.player = QMediaPlayer(); self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio); self.audio.setVolume(0.6)
        self.player.mediaStatusChanged.connect(lambda st: st == QMediaPlayer.EndOfMedia and self._play(self.playlist.next()))
        root = QWidget(objectName="bg"); self.setCentralWidget(root); lay = QHBoxLayout(root)
        side = QVBoxLayout(); self.orb = Orb(); side.addWidget(self.orb)
        self.nav = QListWidget(objectName="nav"); self.nav.addItems(self.NAV); side.addWidget(self.nav)
        lay.addLayout(side, 1); self.pages = QStackedWidget(); lay.addWidget(self.pages, 4)
        self.pages.addWidget(self._home()); self.pages.addWidget(self._chat()); self.pages.addWidget(self._music())
        self.pages.addWidget(self._apps()); self.pages.addWidget(self._plugins_page()); self.pages.addWidget(self._settings())
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex); self.nav.setCurrentRow(0)

    def _home(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w)
        h = QLabel("<h1>Hallo, Master. Was moechtest du heute erledigen?</h1>"); v.addWidget(h)
        self.home_in = QLineEdit(placeholderText="Stelle eine Frage oder gib eine Aufgabe ..."); v.addWidget(self.home_in)
        self.home_in.returnPressed.connect(lambda: self._send(self.home_in, True))
        grid = QGridLayout()
        for i, (t, pg) in enumerate([("Chat & Fragen", 1), ("Musik abspielen", 2), ("Programme starten", 3), ("Plugins", 4), ("Einstellungen", 5)]):
            b = QPushButton(t); b.clicked.connect(lambda _, p=pg: self.nav.setCurrentRow(p)); grid.addWidget(b, i // 2, i % 2)
        v.addLayout(grid); v.addStretch(); return w

    def _chat(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); self.log = QTextEdit(readOnly=True); v.addWidget(self.log)
        stop = QPushButton("Stopp (Sprache)"); stop.clicked.connect(self._stop_speech); v.addWidget(stop)
        self.chat_in = QLineEdit(placeholderText="Nachricht ..."); v.addWidget(self.chat_in)
        self.chat_in.returnPressed.connect(lambda: self._send(self.chat_in, False)); return w

    def _send(self, box: QLineEdit, jump: bool) -> None:
        text = box.text().strip(); box.clear()
        if not text: return
        if jump: self.nav.setCurrentRow(1)
        self.log.append(f"<b style='color:#ffd400'>Du:</b> {text}"); self.log.append("<b style='color:#ff3030'>YAVIS:</b> ")
        self.orb.level = 1.0; self._reply = ""; self._stop_speech()
        def work() -> None:
            try:
                for p in self.agent.ask(text): self.bridge.piece.emit(p)
            except LLMError as e: self.bridge.piece.emit(f"[Fehler] {e} - Ist Ollama (ollama.com) installiert und gestartet, und das Modell geladen?")
            self.bridge.done.emit()
        threading.Thread(target=work, daemon=True).start()

    def _on_piece(self, p: str) -> None:
        self.log.moveCursor(self.log.textCursor().MoveOperation.End); self.log.insertPlainText(p); self._reply += p
    def _on_done(self) -> None:
        self.orb.level = 0.2
        if self.settings.speak_replies and self._reply.strip(): self._speak(self._reply)

    def _speak(self, text: str, voice=None) -> None:
        self._gen += 1; gen = self._gen; v = voice or get_voice(self.settings.voice_id)
        def work() -> None:
            try: path = self.speaker.synthesize(text, v)
            except TTSError as e: self.bridge.notice.emit(f"Sprachausgabe: {e}"); return
            if gen == self._gen: self.bridge.speak_ready.emit(str(path))   # veraltete Ergebnisse verwerfen
        threading.Thread(target=work, daemon=True).start()
    def _play_voice(self, path: str) -> None:
        self.voice_player.setSource(QUrl.fromLocalFile(path)); self.voice_player.play()
    def _confirm(self, tool) -> bool:                      # laeuft im Worker-Thread
        self._cevt.clear(); self._cok = False
        self.bridge.ask_confirm.emit(f"{tool.name}\n{tool.description}")
        self._cevt.wait(60); return self._cok               # keine Antwort in 60 s = Nein
    def _on_ask_confirm(self, text: str) -> None:
        self._cok = QMessageBox.question(self, "YAVIS fragt um Erlaubnis", f"YAVIS moechte ausfuehren:\n\n{text}\n\nErlauben?") == QMessageBox.Yes
        self._cevt.set()

    def _plugins_page(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(QLabel("Plugins sind IMMER aus, bis du sie aktivierst. Lies den Code unten, bevor du aktivierst."))
        self.plug_list = QListWidget(); self.plug_list.setMaximumHeight(160); v.addWidget(self.plug_list)
        self.plug_view = QTextEdit(readOnly=True); v.addWidget(self.plug_view)
        self.plug_list.currentItemChanged.connect(lambda *_: self._plugin_detail())
        row = QHBoxLayout()
        for label, fn in (("Ordner importieren", self._plug_import_dir), ("ZIP importieren", self._plug_import_zip),
                          ("Mit YAVIS erzeugen", self._plug_generate), ("Aktivieren", self._plug_enable),
                          ("Deaktivieren", self._plug_disable), ("Entfernen", self._plug_remove)):
            b = QPushButton(label); b.clicked.connect(fn); row.addWidget(b)
        v.addLayout(row); self._refresh_plugins(); return w
    def _plug_name(self):
        it = self.plug_list.currentItem(); return it.data(Qt.UserRole) if it else None
    def _refresh_plugins(self) -> None:
        self.plug_list.clear()
        for i in self.plugins.discover():
            tag = ("AN   " if i.enabled else "AUS  ") + i.name + ("  [Code geaendert - gesperrt]" if i.changed else "") + ("  [Probleme]" if i.problems else "")
            it = QListWidgetItem(tag); it.setData(Qt.UserRole, i.name); self.plug_list.addItem(it)
    def _plugin_detail(self) -> None:
        n = self._plug_name()
        if not n: self.plug_view.clear(); return
        i = self.plugins.info(n); code = (i.path / "plugin.py").read_text(encoding="utf-8", errors="replace") if (i.path / "plugin.py").exists() else ""
        self.plug_view.setPlainText(f"{i.manifest.get('description', '')}\nBerechtigungen: {i.manifest.get('permissions') or 'keine'}\n"
            f"Tools: {', '.join(i.manifest.get('tools', {}))}\nProbleme: {'; '.join(i.problems) or 'keine gefunden'}\n\n--- plugin.py ---\n{code}")
    def _plug_try(self, fn, *a) -> None:
        try: fn(*a)
        except PluginError as e: self.statusBar().showMessage(str(e), 10000)
        self._resync_plugins(); self._refresh_plugins()
    def _resync_plugins(self) -> None:
        self.plugins.sync(self.reg); self.agent.history[0]["content"] = build_system_prompt(self.settings, self.reg, self.memory.lessons())
    def _plug_import_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Plugin-Ordner")
        if d: self._plug_try(self.plugins.install_dir, Path(d))
    def _plug_import_zip(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Plugin-ZIP", "", "ZIP (*.zip)")
        if f: self._plug_try(self.plugins.install_zip, Path(f))
    def _plug_enable(self) -> None:
        n = self._plug_name()
        if not n: return
        i = self.plugins.info(n)
        if QMessageBox.question(self, "Plugin aktivieren", f"'{n}' aktivieren?\nBerechtigungen: {i.manifest.get('permissions') or 'keine'}\n\n"
                "Ich habe den Code gelesen und vertraue ihm.") == QMessageBox.Yes: self._plug_try(self.plugins.enable, n)
    def _plug_disable(self) -> None:
        n = self._plug_name()
        if n: self._plug_try(self.plugins.disable, n)
    def _plug_remove(self) -> None:
        n = self._plug_name()
        if n and QMessageBox.question(self, "Entfernen", f"'{n}' endgueltig loeschen?") == QMessageBox.Yes: self._plug_try(self.plugins.remove, n)
    def _plug_generate(self) -> None:
        wish, ok = QInputDialog.getText(self, "Plugin erzeugen", "Was soll das Plugin koennen?")
        if not ok or not wish.strip(): return
        self.statusBar().showMessage("YAVIS schreibt das Plugin ...", 0)
        def work() -> None:
            try: n = generate_plugin(self.agent.llm, self.plugins, wish); self.bridge.notice.emit(f"Plugin '{n}' erzeugt - noch AUS. Bitte Code pruefen, dann aktivieren.")
            except (PluginError, LLMError) as e: self.bridge.notice.emit(f"Plugin-Erzeugung fehlgeschlagen: {e}")
            self.bridge.plugins_changed.emit()
        threading.Thread(target=work, daemon=True).start()

    def _stop_speech(self) -> None:
        self._gen += 1; self.voice_player.stop()

    def _settings(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); s = self.settings; v.addWidget(QLabel("<h2>Einstellungen</h2>"))
        v.addWidget(QLabel("Anrede")); self.set_addr = QLineEdit(s.address_as); v.addWidget(self.set_addr)
        v.addWidget(QLabel(f"Stimme ({len(self.voices)} Profile)")); self.set_voice = QComboBox()
        for vo in self.voices: self.set_voice.addItem(("W  " if vo.gender == "w" else "M  ") + vo.label, vo.id)
        self.set_voice.setCurrentIndex(max(0, self.set_voice.findData(s.voice_id))); v.addWidget(self.set_voice)
        self.set_speak = QCheckBox("Antworten vorlesen"); self.set_speak.setChecked(s.speak_replies); v.addWidget(self.set_speak)
        self.set_vol = QSlider(Qt.Horizontal); self.set_vol.setRange(0, 100); self.set_vol.setValue(int(s.volume * 100))
        self.set_vol.valueChanged.connect(lambda x: self.voice_audio.setVolume(x / 100)); v.addWidget(QLabel("Lautstaerke")); v.addWidget(self.set_vol)
        t = QPushButton("Stimme testen"); t.clicked.connect(lambda: self._speak(
            f"Hallo {self.set_addr.text() or 'Master'}, so klinge ich.", get_voice(self.set_voice.currentData()))); v.addWidget(t)
        v.addWidget(QLabel("Namen, auf die YAVIS hoert (ein Name pro Zeile)"))
        self.set_names = QTextEdit("\n".join(s.wake_names)); self.set_names.setMaximumHeight(120); v.addWidget(self.set_names)
        b = QPushButton("Speichern", objectName="go"); b.clicked.connect(self._save_settings); v.addWidget(b); v.addStretch(); return w

    def _save_settings(self) -> None:
        names, errs = validate_names(self.set_names.toPlainText().splitlines())
        if errs: self.statusBar().showMessage("Nicht gespeichert: " + errs[0], 8000); return
        s = self.settings; s.wake_names, s.address_as = names, self.set_addr.text().strip() or "Master"
        s.voice_id, s.speak_replies, s.volume = self.set_voice.currentData(), self.set_speak.isChecked(), self.set_vol.value() / 100
        s.save(); self.agent.history[0]["content"] = build_system_prompt(s, self.reg, self.memory.lessons())
        self.statusBar().showMessage("Gespeichert", 4000)

    def _music(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); self.tracks = QListWidget(); v.addWidget(self.tracks)
        self.tracks.itemDoubleClicked.connect(lambda it: self._play_index(self.tracks.row(it)))
        row = QHBoxLayout()
        for label, fn in (("Ordner waehlen", self._pick_music), ("<<", lambda: self._play(self.playlist.prev())),
                          ("Play/Pause", self._toggle), (">>", lambda: self._play(self.playlist.next()))):
            b = QPushButton(label); b.clicked.connect(fn); row.addWidget(b)
        vol = QSlider(Qt.Horizontal); vol.setRange(0, 100); vol.setValue(60)
        vol.valueChanged.connect(lambda x: self.audio.setVolume(x / 100)); row.addWidget(vol); v.addLayout(row); return w

    def _pick_music(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Musikordner")
        if d:
            self.playlist = Playlist.scan(d); self.tracks.clear()
            self.tracks.addItems([t.name for t in self.playlist.tracks])
    def _play_index(self, i: int) -> None:
        self.playlist.index = i; self._play(self.playlist.current())
    def _play(self, path) -> None:
        if path: self.player.setSource(QUrl.fromLocalFile(str(path))); self.player.play(); self.tracks.setCurrentRow(self.playlist.index)
    def _toggle(self) -> None:
        if self.player.isPlaying(): self.player.pause()
        elif self.player.source().isEmpty(): self._play(self.playlist.next())
        else: self.player.play()

    def _apps(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); v.addWidget(QLabel("Haken = YAVIS darf dieses Programm starten"))
        self.app_list = QListWidget(); v.addWidget(self.app_list); self._refresh_apps()
        self.app_list.itemChanged.connect(lambda it: self.launcher.set_enabled(it.text(), it.checkState() == Qt.Checked))
        row = QHBoxLayout()
        for label, fn in (("Installierte suchen", self._scan_apps), ("Hinzufuegen", self._add_app), ("Starten", self._run_app), ("Entfernen", self._del_app)):
            b = QPushButton(label); b.clicked.connect(fn); row.addWidget(b)
        v.addLayout(row); return w
    def _refresh_apps(self) -> None:
        self.app_list.blockSignals(True); self.app_list.clear()
        for a in self.launcher.apps.values():
            it = QListWidgetItem(a.name); it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if a.enabled else Qt.Unchecked); self.app_list.addItem(it)
        self.app_list.blockSignals(False)
    def _add_app(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Programm waehlen", "", "Programme (*.exe)")
        if f:
            from pathlib import Path; self.launcher.add(Path(f).stem, f); self._refresh_apps()
    def _scan_apps(self) -> None:
        new = [(n, p) for n, p in scan_start_menu().items() if n not in self.launcher.apps]
        for n, p in new: self.launcher.add(n, p)          # neu gefundene sind GESPERRT, bis du den Haken setzt
        self._refresh_apps(); self.statusBar().showMessage(f"{len(new)} Programme gefunden (alle gesperrt)", 6000)
    def _run_app(self) -> None:
        it = self.app_list.currentItem()
        if it: self.statusBar().showMessage(self.launcher.launch(it.text()), 5000)
    def _del_app(self) -> None:
        it = self.app_list.currentItem()
        if it: self.launcher.remove(it.text()); self._refresh_apps()


def main() -> int:
    app = QApplication(sys.argv); app.setStyleSheet(CSS); w = Main(); w.show(); return app.exec()


if __name__ == "__main__":
    sys.exit(main())
