import tempfile, unittest, wave
from pathlib import Path
from yavis.config import Settings
from yavis.tts import Speaker, TTSError, clean_for_speech, apply_pitch
from yavis.voices import get_voice
from yavis.wakewords import match_wake, validate_names


def fake_wav(path, rate=22050):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(b"\x00\x01" * 2000)


class R:  # Fake-Ergebnis
    def __init__(self, rc=0): self.returncode = rc


class TestTTS(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp()); (self.d / "piper.exe").write_text("")
        (self.d / "de_DE-kerstin-low.onnx").write_text(""); self.calls = []
    def runner(self, cmd, input, capture_output, timeout, **kw):
        self.calls.append((cmd, input)); fake_wav(cmd[cmd.index("--output_file") + 1]); return R()
    def test_synthesize_args_and_pitch(self):
        v = get_voice("w:kerstin-low:Samtig & verfuehrerisch")
        out = Speaker(self.d / "piper.exe", self.d, self.runner).synthesize("Hallo **Master** [[tool:x]]", v)
        cmd, text = self.calls[0]
        self.assertEqual(text, "Hallo Master".encode()); self.assertEqual(cmd[cmd.index("--length_scale") + 1], str(round(1.15 * .95, 3)))
        with wave.open(str(out)) as w: self.assertEqual(w.getframerate(), int(22050 * .95))
    def test_missing_files_give_clear_errors(self):
        v = get_voice("w:kerstin-low:Warm")
        self.assertIn("Piper nicht gefunden", Speaker(self.d / "nix.exe", self.d).available(v))
        self.assertIn("Stimmenmodell fehlt", Speaker(self.d / "piper.exe", self.d).available(get_voice("m:karlsson-low:Normal")))
        with self.assertRaises(TTSError): Speaker(self.d / "nix.exe", self.d).synthesize("hi", v)
    def test_failure_paths(self):
        v = get_voice("w:kerstin-low:Warm"); sp = Speaker(self.d / "piper.exe", self.d, lambda *a, **k: R(1))
        with self.assertRaises(TTSError): sp.synthesize("hi", v)
        with self.assertRaises(TTSError): Speaker(self.d / "piper.exe", self.d, self.runner).synthesize("[[tool:x]] **", v)
    def test_clean_and_truncate(self):
        self.assertEqual(clean_for_speech("Siehe https://a.de/x  `code`"), "Siehe Link code")
        long = ("Das ist ein Satz. " * 100); out = clean_for_speech(long)
        self.assertTrue(len(out) <= 600 and out.endswith("."))
    def test_pitch_noop(self):
        p = self.d / "a.wav"; fake_wav(p); apply_pitch(p, 1.0)
        with wave.open(str(p)) as w: self.assertEqual(w.getframerate(), 22050)


class TestWake(unittest.TestCase):
    N = ["YAVIS", "Hey YAVIS", "Computer"]
    def test_match(self):
        self.assertEqual(match_wake("Hey Yavis, wie spaet ist es?", self.N), ("Hey YAVIS", "wie spaet ist es"))
        self.assertEqual(match_wake("yavis", self.N), ("YAVIS", ""))
        self.assertEqual(match_wake("Mach Musik an Computer", self.N), ("Computer", "Mach Musik an"))
    def test_tolerates_small_recognition_errors_only(self):
        self.assertEqual(match_wake("Yavies spiel Musik", self.N)[0], "YAVIS")
        for no in ["Davis ist hier", "Das Wetter heute", "Ich habe Computerprobleme"]:
            self.assertIsNone(match_wake(no, self.N)[0], no)
    def test_validate(self):
        names, err = validate_names(["  Jarvis ", "jarvis", "Frida", "x", "Böse;Name", "Hey  Frida"])
        self.assertEqual(names, ["Jarvis", "Frida", "Hey Frida"]); self.assertEqual(len(err), 2)
        self.assertIn("Mindestens", validate_names([""])[1][-1])
        self.assertEqual(validate_names(["Müller"])[0], ["Müller"])
    def test_settings_default_names_and_voice(self):
        s = Settings(); self.assertEqual(s.wake_names, ["YAVIS", "Hey YAVIS"]); get_voice(s.voice_id)


if __name__ == "__main__":
    unittest.main()
