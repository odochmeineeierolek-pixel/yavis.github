"""Sichere Tools mit expliziter Registrierung und Berechtigungsstufen."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

_WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    func: Callable[..., str]
    needs_confirmation: bool = False   # kritische Aktionen: True
    takes_arg: bool = False            # True: func(arg: str)


def get_time() -> str:
    n = datetime.now()
    return f"{_WOCHENTAGE[n.weekday()]}, {n:%d.%m.%Y}, {n:%H:%M} Uhr"


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def unregister_prefix(self, prefix: str) -> None:
        for n in [n for n in self._tools if n.startswith(prefix)]: del self._tools[n]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def describe(self) -> str:
        return "\n".join(f"- {t.name}{'|ARGUMENT' if t.takes_arg else ''}: {t.description}" for t in self._tools.values())

    def run(self, name: str, confirm: Callable[[Tool], bool] | None = None, arg: str = "") -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Unbekanntes Tool: {name}"          # keine freie Befehlsausfuehrung
        if tool.needs_confirmation and not (confirm and confirm(tool)):
            return f"Aktion '{name}' wurde nicht bestaetigt."
        try:
            return tool.func(arg) if tool.takes_arg else tool.func()
        except Exception as e:  # Tool-Fehler duerfen den Agenten nie crashen
            return f"Tool '{name}' fehlgeschlagen: {e}"


def default_registry() -> ToolRegistry:
    r = ToolRegistry()
    r.register(Tool("get_time", "Aktuelles Datum und Uhrzeit abrufen", get_time))
    return r
