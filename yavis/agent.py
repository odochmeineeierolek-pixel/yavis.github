"""Agent: Systemprompt, Verlauf, Streaming, Tool-Marker [[tool:NAME]]."""
from __future__ import annotations
import re
from typing import Callable, Iterator
from .config import Settings
from .llm import LLM
from .tools import ToolRegistry, Tool

_TOOL_RE = re.compile(r"\[\[tool:([a-z_0-9]+)(?:\|([^\]]*))?\]\]")
_TONE = {"neutral": "sachlich und neutral", "freundlich": "freundlich und warm",
         "liebevoll": "liebevoll und herzlich", "traurig": "leicht melancholisch",
         "wuetend": "gereizt, aber stets respektvoll"}


def build_system_prompt(s: Settings, tools: ToolRegistry, lessons: list[str] | None = None) -> str:
    learned = ("\nGelernte Praeferenzen des Nutzers:\n" + "\n".join(f"- {x}" for x in lessons)) if lessons else ""
    return (f"Du bist YAVIS, ein lokaler KI-Assistent. Antworte auf natuerlichem Deutsch, kurz und klar. "
            f"Sprich den Nutzer immer mit '{s.address_as}' an. Ton: {_TONE.get(s.emotion, _TONE['neutral'])}.\n"
            f"Verfuegbare Tools:\n{tools.describe()}\n"
            "Wenn du ein Tool brauchst, antworte NUR mit [[tool:NAME]] bzw. [[tool:NAME|ARGUMENT]]. Erfinde keine Tool-Ergebnisse." + learned)


class Agent:
    def __init__(self, llm: LLM, settings: Settings, tools: ToolRegistry,
                 confirm: Callable[[Tool], bool] | None = None,
                 lessons: list[str] | None = None) -> None:
        self.llm, self.settings, self.tools, self.confirm = llm, settings, tools, confirm
        self.history: list[dict] = [{"role": "system", "content": build_system_prompt(settings, tools, lessons)}]

    def _collect(self) -> Iterator[str]:
        for piece in self.llm.chat_stream(self.history):
            yield piece

    def ask(self, text: str) -> Iterator[str]:
        """Streamt die Antwort; fuehrt hoechstens EINEN Tool-Schritt aus."""
        self.history.append({"role": "user", "content": text})
        chunks = list(self._collect())
        full = "".join(chunks)
        m = _TOOL_RE.search(full)
        if m:
            result = self.tools.run(m.group(1), self.confirm, (m.group(2) or "").strip())
            self.history.append({"role": "assistant", "content": full})
            self.history.append({"role": "user", "content": f"Tool-Ergebnis ({m.group(1)}): {result}. "
                                 "Formuliere nun die Antwort an den Nutzer."})
            chunks = list(self._collect())
            full = "".join(chunks)
        self.history.append({"role": "assistant", "content": full})
        yield from chunks
