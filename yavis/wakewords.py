"""Frei einstellbare Namen, auf die YAVIS hoert. Arbeitet auf erkanntem TEXT (Mikrofon-Anbindung folgt)."""
from __future__ import annotations
import difflib, re, unicodedata

_MAX_NAMES = 10


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


def validate_names(raw: list[str]) -> tuple[list[str], list[str]]:
    """-> (gueltige Namen, Fehlermeldungen)."""
    names, errors, seen = [], [], set()
    for n in raw:
        n = " ".join(n.split())
        if not re.fullmatch(r"[^\W_]+(?: [^\W_]+)*", n) or not 2 <= len(n) <= 30:
            errors.append(f"'{n}': 2-30 Zeichen, nur Buchstaben/Ziffern/Leerzeichen"); continue
        if _norm(n) in seen:
            continue
        if len(names) >= _MAX_NAMES:
            errors.append(f"Maximal {_MAX_NAMES} Namen"); break
        seen.add(_norm(n)); names.append(n)
    if not names:
        errors.append("Mindestens ein Name ist noetig")
    return names, errors


def _same(a: str, b: str) -> bool:
    return a == b or (min(len(a), len(b)) >= 5 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.84)


def match_wake(text: str, names: list[str]) -> tuple[str | None, str]:
    """Findet einen Namen am Satzanfang oder -ende. -> (Name | None, restlicher Befehl)."""
    toks = [(_norm(m.group()), m.start(), m.end()) for m in re.finditer(r"\w+", text)]
    for name in sorted(names, key=lambda n: -len(n.split())):
        nt = [_norm(w) for w in name.split()]; k = len(nt)
        if not nt or len(toks) < k:
            continue
        if all(_same(toks[i][0], nt[i]) for i in range(k)):
            return name, text[toks[k - 1][2]:].strip(" ,.!?;:")
        if all(_same(toks[-k + i][0], nt[i]) for i in range(k)):
            return name, text[:toks[-k][1]].strip(" ,.!?;:")
    return None, text
