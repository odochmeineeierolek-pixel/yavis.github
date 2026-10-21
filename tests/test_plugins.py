import json, tempfile, unittest, zipfile
from pathlib import Path
from yavis.agent import Agent
from yavis.config import Settings
from yavis.plugins import PluginManager, PluginError, lint, parse_generated, generate_plugin
from yavis.tools import default_registry
from tests.test_core import FakeLLM

GOOD = 'def shout(a):\n    print("laerm")\n    return a.upper()\nTOOLS = {"shout": shout}\n'


def manifest(name="hallo", perms=None, timeout=5, tools=None):
    return {"name": name, "description": "Test", "tools": tools or {"shout": "Schreit"}, "permissions": perms or [], "timeout_s": timeout}


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp()); self.m = PluginManager(self.d / "plugins")
    def stage(self, code=GOOD, **kw): return self.m.stage_generated(manifest(**kw), code)


class TestLifecycle(Base):
    def test_disabled_by_default_then_enable_run(self):
        n = self.stage()
        self.assertFalse(self.m.info(n).enabled)
        with self.assertRaises(PluginError): self.m.run(n, "shout", "x")
        self.m.enable(n); self.assertEqual(self.m.run(n, "shout", "hallo"), "HALLO")   # print() stoert nicht
    def test_code_change_revokes_approval(self):
        n = self.stage(); self.m.enable(n)
        (self.m.root / n / "plugin.py").write_text(GOOD + "# geaendert\n")
        i = self.m.info(n); self.assertFalse(i.enabled); self.assertTrue(i.changed)
        with self.assertRaises(PluginError): self.m.run(n, "shout", "x")
    def test_duplicate_and_remove(self):
        n = self.stage()
        with self.assertRaises(PluginError): self.stage()
        self.m.enable(n); self.m.remove(n); self.assertEqual(self.m.discover(), []); self.assertNotIn(n, self.m._state())
    def test_timeout_and_errors_contained(self):
        n = self.stage('def f(a):\n    while True: pass\nTOOLS = {"shout": f}\n', timeout=1); self.m.enable(n)
        with self.assertRaises(PluginError) as c: self.m.run(n, "shout", "")
        self.assertIn("Zeitlimit", str(c.exception))
        n2 = self.stage('def f(a):\n    return 1/0\nTOOLS = {"shout": f}\n', name="kaputt"); self.m.enable(n2)
        with self.assertRaises(PluginError) as c: self.m.run(n2, "shout", "")
        self.assertIn("ZeroDivisionError", str(c.exception))


class TestLint(Base):
    def test_dangerous_code_blocked(self):
        for bad in ["import os\nTOOLS={}", "import subprocess\nTOOLS={}", "from os import system\nTOOLS={}",
                    "x=eval('1')\nTOOLS={}", "open('f')\nTOOLS={}", "getattr(1,'a')\nTOOLS={}",
                    "().__class__.__bases__\nTOOLS={}", "import urllib.request\nTOOLS={}", "from . import x\nTOOLS={}",
                    "__import__('os')\nTOOLS={}", "def f(:\n"]:
            self.assertTrue(lint(bad, []), bad)
        self.assertIn("TOOLS", lint("x=1", [])[0])
    def test_permissions_unlock_only_their_modules(self):
        self.assertEqual(lint("import urllib.request\nTOOLS={}", ["network"]), [])
        self.assertTrue(lint("import os\nTOOLS={}", ["network", "files"]))
        self.assertEqual(lint("open('f')\nTOOLS={}", ["files"]), [])
        self.assertTrue(lint("import socket\nTOOLS={}", ["files"]))
    def test_enable_refuses_bad_plugin(self):
        n = self.stage("import os\nTOOLS={}")
        with self.assertRaises(PluginError): self.m.enable(n)
    def test_manifest_validation(self):
        for kw in ({"name": "Ab"}, {"perms": ["root"]}, {"timeout": 99}, {"tools": {"X Y": "a"}}):
            with self.assertRaises(PluginError): self.stage(**kw)


class TestInstall(Base):
    def mkzip(self, files):
        z = self.d / "p.zip"
        with zipfile.ZipFile(z, "w") as f:
            for k, v in files.items(): f.writestr(k, v)
        return z
    def test_zip_ok_and_rejects_extras(self):
        ok = self.mkzip({"plugin.json": json.dumps(manifest("zipper")), "plugin.py": GOOD})
        self.assertEqual(self.m.install_zip(ok), "zipper"); self.assertFalse(self.m.info("zipper").enabled)
        for files in ({"plugin.json": "{}", "plugin.py": "", "evil.exe": "x"}, {"../plugin.json": "{}", "plugin.py": ""}):
            with self.assertRaises(PluginError): self.m.install_zip(self.mkzip(files))
        with self.assertRaises(PluginError): self.m.install_zip(self.d / "nope.zip")
    def test_install_example_dir(self):
        n = self.m.install_dir(Path(__file__).parent.parent / "examples" / "plugin_vorlage"); self.m.enable(n)
        self.assertEqual(self.m.run(n, "umdrehen", "abc"), "cba"); self.assertEqual(self.m.run(n, "woerter", "a b c"), "3 Woerter")


class TestGenerate(Base):
    REPLY = "Hier:\n```json\n%s\n```\n```python\n%s\n```"
    def test_generated_is_staged_disabled(self):
        llm = FakeLLM([self.REPLY % (json.dumps(manifest("gen")), GOOD)])
        n = generate_plugin(llm, self.m, "schreit"); self.assertEqual(n, "gen"); self.assertFalse(self.m.info(n).enabled)
        self.assertIn("schreit", llm.calls[0][0]["content"])
    def test_generated_malicious_cannot_be_enabled(self):
        n = generate_plugin(FakeLLM([self.REPLY % (json.dumps(manifest("boese")), "import os\nTOOLS={'shout': os.getcwd}")]), self.m, "x")
        self.assertTrue(self.m.info(n).problems)
        with self.assertRaises(PluginError): self.m.enable(n)
    def test_parse_failures(self):
        for t in ["nix", "```json\n{}\n```", "```json\n{kaputt\n```\n```python\nx\n```"]:
            with self.assertRaises(PluginError): parse_generated(t)


class TestAgentIntegration(Base):
    def test_sync_registers_and_agent_uses_plugin(self):
        n = self.stage(); reg = default_registry(); self.m.sync(reg); self.assertNotIn("plugin_hallo_shout", reg.names())
        self.m.enable(n); self.m.sync(reg); self.assertIn("plugin_hallo_shout", reg.names())
        a = Agent(FakeLLM(["[[tool:plugin_hallo_shout|hi]]"], ["Fertig, Master."]), Settings(), reg)
        "".join(a.ask("schrei")); self.assertIn("HI", a.history[-2]["content"])
        self.m.disable(n); self.m.sync(reg); self.assertNotIn("plugin_hallo_shout", reg.names())
    def test_permissioned_plugin_needs_confirmation(self):
        n = self.stage(perms=["network"]); self.m.enable(n); reg = default_registry(); self.m.sync(reg)
        self.assertIn("nicht bestaetigt", reg.run("plugin_hallo_shout", None, "x"))
        self.assertEqual(reg.run("plugin_hallo_shout", lambda t: True, "x"), "X")


if __name__ == "__main__":
    unittest.main()
