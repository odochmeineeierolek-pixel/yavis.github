"""Textchat: python -m yavis"""
from __future__ import annotations
import sys
from .agent import Agent
from .config import Settings
from .llm import OllamaClient, LLMError
from .tools import default_registry


def main() -> int:
    s = Settings.load()
    agent = Agent(OllamaClient(s.ollama_url, s.model, s.request_timeout_s), s, default_registry())
    print(f"YAVIS {s.model} - 'exit' beendet.")
    while True:
        try:
            text = input("Du: ").strip()
        except (EOFError, KeyboardInterrupt):
            return 0
        if text.lower() in {"exit", "quit"}:
            return 0
        if not text:
            continue
        print("YAVIS: ", end="", flush=True)
        try:
            for piece in agent.ask(text):
                print(piece, end="", flush=True)
        except LLMError as e:
            print(f"[Fehler] {e}", end="")
        print()


if __name__ == "__main__":
    sys.exit(main())
