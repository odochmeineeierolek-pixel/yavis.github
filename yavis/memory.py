"""Lokales Langzeitgedaechtnis (SQLite): anzeigen, bearbeiten, loeschen."""
from __future__ import annotations
import sqlite3
from pathlib import Path


class Memory:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.db = sqlite3.connect(str(path))
        self.db.execute("CREATE TABLE IF NOT EXISTS notes ("
                        "id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, "
                        "created TEXT DEFAULT CURRENT_TIMESTAMP)")
        self.db.commit()

    def add(self, text: str) -> int:
        cur = self.db.execute("INSERT INTO notes(text) VALUES (?)", (text.strip(),))
        self.db.commit()
        return cur.lastrowid

    def list(self) -> list[tuple[int, str]]:
        return list(self.db.execute("SELECT id, text FROM notes ORDER BY id"))

    def edit(self, note_id: int, text: str) -> bool:
        cur = self.db.execute("UPDATE notes SET text=? WHERE id=?", (text.strip(), note_id))
        self.db.commit()
        return cur.rowcount > 0

    def delete(self, note_id: int) -> bool:
        cur = self.db.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.db.commit()
        return cur.rowcount > 0

    def add_lesson(self, text: str) -> int:
        """Vom Nutzer FREIGEGEBENE Praeferenz (kontrolliertes Lernen, kein Selbstumbau)."""
        return self.add("LEKTION: " + text.strip())

    def lessons(self) -> list[str]:
        return [t[9:] for _, t in self.list() if t.startswith("LEKTION: ")]

    def close(self) -> None:
        self.db.close()
