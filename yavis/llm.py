"""LLM-Clients. Standard: lokales Ollama (kostenlos). Nur Standardbibliothek."""
from __future__ import annotations
import json, urllib.request, urllib.error
from typing import Iterator, Protocol


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    def chat_stream(self, messages: list[dict]) -> Iterator[str]: ...


class OllamaClient:
    def __init__(self, url: str, model: str, timeout_s: int = 60) -> None:
        self.url, self.model, self.timeout = url.rstrip("/"), model, timeout_s

    def chat_stream(self, messages: list[dict]) -> Iterator[str]:
        body = json.dumps({"model": self.model, "messages": messages, "stream": True}).encode()
        req = urllib.request.Request(f"{self.url}/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if "error" in data:
                        raise LLMError(data["error"])
                    piece = data.get("message", {}).get("content", "")
                    if piece:
                        yield piece
                    if data.get("done"):
                        return
        except urllib.error.URLError as e:
            raise LLMError(f"Ollama nicht erreichbar ({self.url}): {e.reason}") from e
        except TimeoutError as e:
            raise LLMError("Zeitlimit bei Ollama ueberschritten") from e
