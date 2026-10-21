import unittest
from datetime import date
from yavis.agent import Agent
from yavis.config import Settings
from yavis.extras import calculate, roll_dice, make_password, days_until, Timers, register_extras, JOKES
from yavis.memory import Memory
from yavis.tools import default_registry
from tests.test_core import FakeLLM


class TestExtras(unittest.TestCase):
    def test_calculate(self):
        self.assertEqual(calculate("12*(3+4)"), "84"); self.assertEqual(calculate("2^10"), "1024")
        self.assertEqual(calculate("1,5+1"), "2.5"); self.assertIn("null", calculate("1/0"))
    def test_calculate_rejects_code(self):
        for bad in ["__import__('os').system('x')", "open('f')", "9**9**9", "2**1000"]:
            self.assertEqual(calculate(bad), "Das kann ich nicht berechnen.", bad)
    def test_dice(self):
        for _ in range(50):
            r = roll_dice("3w6"); self.assertTrue(3 <= int(r.split("= ")[1]) <= 18)
        self.assertIn("Format", roll_dice("quatsch"))
    def test_password(self):
        self.assertEqual(len(make_password("20")), 20); self.assertEqual(len(make_password("")), 16)
        self.assertEqual(len(make_password("3")), 8); self.assertNotEqual(make_password("16"), make_password("16"))
    def test_days_until(self):
        t = date(2026, 10, 21)
        self.assertEqual(days_until("24.12.2026", t), "Noch 64 Tage."); self.assertIn("heute", days_until("21.10.2026", t))
        self.assertIn("TT.MM", days_until("morgen", t))
    def test_timers_fake_clock(self):
        now = [0.0]; t = Timers(lambda: now[0]); t.set("5 Pudding"); t.set("1 Ei")
        now[0] = 61; self.assertEqual(t.due(), ["Ei"]); self.assertEqual(t.due(), [])
        now[0] = 301; self.assertEqual(t.due(), ["Pudding"]); self.assertIn("Keine", t.status())
        self.assertIn("Format", t.set("abc"))
    def test_notes_and_registry(self):
        m = Memory(); reg = default_registry(); register_extras(reg, m)
        self.assertIn("calculate", reg.names()); reg.run("add_note", arg="Milch")
        self.assertIn("Milch", reg.run("list_notes")); self.assertTrue(JOKES)
    def test_agent_passes_argument(self):
        reg = default_registry(); register_extras(reg)
        a = Agent(FakeLLM(["[[tool:calculate|6*7]]"], ["Das ergibt 42, Master."]), Settings(), reg)
        "".join(a.ask("6 mal 7?")); self.assertIn("Tool-Ergebnis (calculate): 42", a.history[-2]["content"])


if __name__ == "__main__":
    unittest.main()
