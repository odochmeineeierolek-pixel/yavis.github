"""Freigabe-Inbox: YAVIS darf Entwuerfe (Angebote, Posts, Nachrichten) NUR vorbereiten.
Nichts verlaesst den PC ohne dein ausdrueckliches OK; es gibt hier bewusst keinen Auto-Versand."""
from __future__ import annotations
import sqlite3
from pathlib import Path


class ApprovalQueue:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.db = sqlite3.connect(str(path))
        self.db.execute("CREATE TABLE IF NOT EXISTS q (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, "
                        "title TEXT, body TEXT, status TEXT DEFAULT 'pending')"); self.db.commit()

    def submit(self, kind: str, title: str, body: str) -> int:
        cur = self.db.execute("INSERT INTO q(kind,title,body) VALUES (?,?,?)", (kind, title, body))
        self.db.commit(); return cur.lastrowid

    def _decide(self, i: int, status: str) -> bool:
        cur = self.db.execute("UPDATE q SET status=? WHERE id=? AND status='pending'", (status, i))
        self.db.commit(); return cur.rowcount > 0       # nur offene Eintraege, keine Umentscheidung

    def approve(self, i: int) -> bool: return self._decide(i, "approved")
    def reject(self, i: int) -> bool: return self._decide(i, "rejected")

    def items(self, status: str = "pending") -> list[tuple[int, str, str, str]]:
        return list(self.db.execute("SELECT id,kind,title,body FROM q WHERE status=? ORDER BY id", (status,)))
