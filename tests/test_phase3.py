import tempfile, unittest
from pathlib import Path
from yavis.agent import build_system_prompt
from yavis.approvals import ApprovalQueue
from yavis.config import Settings
from yavis.launcher import scan_start_menu
from yavis.memory import Memory
from yavis.tools import default_registry
from yavis.voices import build_catalog, get_voice, piper_args


class TestVoices(unittest.TestCase):
    def test_catalog(self):
        c = build_catalog(); ids = [v.id for v in c]
        self.assertGreaterEqual(len(c), 30); self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue({"w", "m"} <= {v.gender for v in c})
        for v in c:
            self.assertTrue(.7 <= v.length_scale <= 1.5 and .7 <= v.pitch <= 1.2 and 0 < v.noise_scale <= 1)
    def test_lookup_and_args(self):
        v = get_voice("m:thorsten-medium:Hart & tief"); self.assertEqual(piper_args(v)[:2], ["--model", "de_DE-thorsten-medium"])
        with self.assertRaises(KeyError): get_voice("x")


class TestScan(unittest.TestCase):
    def test_scan_filters_uninstall(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "sub").mkdir()
            for n in ["Spotify.lnk", "sub/Firefox.lnk", "Uninstall Foo.lnk", "x.txt"]: (Path(d) / n).write_text("")
            self.assertEqual(list(scan_start_menu([Path(d), Path(d) / "gibtsnicht"])), ["Firefox", "Spotify"])


class TestApprovals(unittest.TestCase):
    def test_flow(self):
        q = ApprovalQueue(); i = q.submit("Angebot", "Logo-Design", "Text")
        self.assertEqual(q.items("approved"), []); self.assertTrue(q.approve(i))
        self.assertFalse(q.reject(i)); self.assertEqual(q.items("approved")[0][2], "Logo-Design")
        self.assertEqual(q.items(), [])


class TestLessons(unittest.TestCase):
    def test_lessons_reach_prompt(self):
        m = Memory(); m.add("normale Notiz"); m.add_lesson("Antworte kurz")
        self.assertEqual(m.lessons(), ["Antworte kurz"])
        p = build_system_prompt(Settings(), default_registry(), m.lessons())
        self.assertIn("Antworte kurz", p); self.assertIn("Master", build_system_prompt(Settings(), default_registry()))
        self.assertNotIn("normale Notiz", p)


if __name__ == "__main__":
    unittest.main()
