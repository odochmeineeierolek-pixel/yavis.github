"""Sprachausgabe ueber Piper (lokal, kostenlos). Piper-EXE und .onnx-Modelle muessen vorhanden sein."""
from __future__ import annotations
import re, subprocess, tempfile, wave
from pathlib import Path
from typing import Callable
from .voices import Voice


class TTSError(RuntimeError):
    pass


def clean_for_speech(text: str, max_chars: int = 600) -> str:
    t = re.sub(r"\[\[tool:[^\]]*\]\]", "", text)
    t = re.sub(r"https?://\S+", "Link", t)
    t = re.sub(r"[*_`#>]+", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > max_chars:
        cut = t[:max_chars]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        t = cut[:end + 1] if end > 100 else cut
    return t


def apply_pitch(wav_path: Path, pitch: float) -> None:
    """Hebt/senkt die Tonhoehe durch Aendern der Abtastrate (stdlib). Tempo wird beim Erzeugen ausgeglichen."""
    if abs(pitch - 1.0) < 1e-3:
        return
    with wave.open(str(wav_path), "rb") as r:
        params, frames = r.getparams(), r.readframes(r.getnframes())
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(params.nchannels); w.setsampwidth(params.sampwidth)
        w.setframerate(int(params.framerate * pitch)); w.writeframes(frames)


class Speaker:
    def __init__(self, piper_exe: Path, models_dir: Path, runner: Callable = subprocess.run, timeout_s: int = 60) -> None:
        self.piper_exe, self.models_dir, self.runner, self.timeout = Path(piper_exe), Path(models_dir), runner, timeout_s

    def model_path(self, voice: Voice) -> Path:
        return self.models_dir / f"{voice.model}.onnx"

    def available(self, voice: Voice) -> str | None:
        """None = bereit, sonst verstaendliche Fehlermeldung."""
        if not self.piper_exe.is_file():
            return f"Piper nicht gefunden: {self.piper_exe}"
        if not self.model_path(voice).is_file():
            return f"Stimmenmodell fehlt: {self.model_path(voice).name}"
        return None

    def synthesize(self, text: str, voice: Voice, out_dir: Path | None = None) -> Path:
        problem = self.available(voice)
        if problem:
            raise TTSError(problem)
        text = clean_for_speech(text)
        if not text:
            raise TTSError("Kein sprechbarer Text")
        out = Path(tempfile.mkstemp(suffix=".wav", dir=out_dir)[1])
        # Wiedergabe wird um 'pitch' schneller -> beim Erzeugen entsprechend langsamer sprechen
        cmd = [str(self.piper_exe), "--model", str(self.model_path(voice)), "--output_file", str(out),
               "--length_scale", str(round(voice.length_scale * voice.pitch, 3)),
               "--noise_scale", str(voice.noise_scale), "--noise_w", str(voice.noise_w)]
        try:
            res = self.runner(cmd, input=text.encode("utf-8"), capture_output=True, timeout=self.timeout,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired as e:
            raise TTSError("Zeitlimit bei Piper") from e
        except OSError as e:
            raise TTSError(f"Piper konnte nicht gestartet werden: {e}") from e
        if res.returncode != 0 or not out.exists() or out.stat().st_size < 44:
            raise TTSError("Piper hat keine Audiodatei erzeugt")
        apply_pitch(out, voice.pitch)
        return out
