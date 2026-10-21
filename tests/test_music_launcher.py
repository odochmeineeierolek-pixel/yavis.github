import tempfile, unittest
from pathlib import Path
from yavis.launcher import Launcher
from yavis.music import Playlist


class TestPlaylist(unittest.TestCase):
    def test_scan_next_prev_wrap(self):
        with tempfile.TemporaryDirectory() as d:
            for n in ["b.mp3", "a.wav", "x.txt"]: (Path(d) / n).write_text("")
            p = Playlist.scan(d)
            self.assertEqual([t.name for t in p.tracks], ["a.wav", "b.mp3"])
            self.assertEqual(p.next().name, "a.wav"); self.assertEqual(p.next().name, "b.mp3")
            self.assertEqual(p.next().name, "a.wav"); self.assertEqual(p.prev().name, "b.mp3")
    def test_empty_and_shuffle(self):
        self.assertIsNone(Playlist().next())
        p = Playlist([Path("1.mp3"), Path("2.mp3")], shuffle=True); p.next()
        first = p.current(); self.assertNotEqual(p.next(), first)


class TestLauncher(unittest.TestCase):
    def test_gate_and_launch(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / "app.exe"; exe.write_text("")
            calls = []; L = Launcher(Path(d) / "a.json", opener=calls.append)
            L.add("Notiz", str(exe))
            self.assertIn("nicht freigegeben", L.launch("Notiz")); self.assertEqual(calls, [])
            L.set_enabled("Notiz", True)
            self.assertIn("gestartet", L.launch("Notiz")); self.assertEqual(calls, [[str(exe)]])
            self.assertTrue(Launcher(Path(d) / "a.json").apps["Notiz"].enabled)   # persistiert
            self.assertIn("nicht in der Liste", L.launch("Fremd"))
            exe.unlink(); self.assertIn("nicht gefunden", L.launch("Notiz"))
