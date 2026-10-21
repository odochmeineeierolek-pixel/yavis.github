import json, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from yavis.agent import Agent, build_system_prompt
from yavis.config import Settings
from yavis.llm import OllamaClient, LLMError
from yavis.memory import Memory
from yavis.tools import Tool, ToolRegistry, default_registry, get_time


class FakeLLM:
    def __init__(self, *replies): self.replies, self.calls = list(replies), []
    def chat_stream(self, messages):
        self.calls.append([m.copy() for m in messages])
        yield from self.replies.pop(0)


class FakeOllama(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200); self.end_headers()
        for i, w in enumerate(["Hallo ", "Master"]):
            self.wfile.write((json.dumps({"message": {"content": w}, "done": False}) + "\n").encode())
        self.wfile.write((json.dumps({"message": {"content": ""}, "done": True}) + "\n").encode())
    def log_message(self, *a): pass


class TestTools(unittest.TestCase):
    def test_time_format(self):
        self.assertRegex(get_time(), r"^\w+, \d{2}\.\d{2}\.\d{4}, \d{2}:\d{2} Uhr$")
    def test_unknown_tool_is_refused(self):
        self.assertIn("Unbekannt", default_registry().run("rm_rf"))
    def test_confirmation_required(self):
        r = ToolRegistry(); r.register(Tool("del", "x", lambda: "geloescht", needs_confirmation=True))
        self.assertIn("nicht bestaetigt", r.run("del"))
        self.assertIn("nicht bestaetigt", r.run("del", lambda t: False))
        self.assertEqual(r.run("del", lambda t: True), "geloescht")
    def test_tool_exception_is_contained(self):
        r = ToolRegistry(); r.register(Tool("boom", "x", lambda: 1 / 0))
        self.assertIn("fehlgeschlagen", r.run("boom"))


class TestMemory(unittest.TestCase):
    def test_crud(self):
        m = Memory(); i = m.add(" Kaffee ")
        self.assertEqual(m.list(), [(i, "Kaffee")])
        self.assertTrue(m.edit(i, "Tee")); self.assertEqual(m.list()[0][1], "Tee")
        self.assertTrue(m.delete(i)); self.assertEqual(m.list(), [])
        self.assertFalse(m.delete(999))


class TestSettings(unittest.TestCase):
    def test_roundtrip_and_corrupt(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"; s = Settings(model="x"); s.save(p)
            self.assertEqual(Settings.load(p).model, "x")
            p.write_text("{kaputt"); self.assertEqual(Settings.load(p).model, "llama3.2")


class TestAgent(unittest.TestCase):
    def test_prompt_contains_master_and_tool(self):
        p = build_system_prompt(Settings(), default_registry())
        self.assertIn("Master", p); self.assertIn("get_time", p)
    def test_plain_answer(self):
        a = Agent(FakeLLM(["Hallo ", "Master"]), Settings(), default_registry())
        self.assertEqual("".join(a.ask("Hi")), "Hallo Master")
    def test_tool_roundtrip(self):
        llm = FakeLLM(["[[tool:get_time]]"], ["Es ist spaet, Master."])
        a = Agent(llm, Settings(), default_registry())
        self.assertEqual("".join(a.ask("Wie spaet?")), "Es ist spaet, Master.")
        self.assertIn("Uhr", llm.calls[1][-1]["content"])  # echtes Tool-Ergebnis wurde uebergeben


class TestOllamaClient(unittest.TestCase):
    def test_streaming_over_http(self):
        srv = HTTPServer(("127.0.0.1", 0), FakeOllama)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        c = OllamaClient(f"http://127.0.0.1:{srv.server_port}", "m", 5)
        self.assertEqual(list(c.chat_stream([{"role": "user", "content": "x"}])), ["Hallo ", "Master"])
        srv.shutdown()
    def test_unreachable_raises_llmerror(self):
        with self.assertRaises(LLMError):
            list(OllamaClient("http://127.0.0.1:1", "m", 2).chat_stream([]))


if __name__ == "__main__":
    unittest.main()
