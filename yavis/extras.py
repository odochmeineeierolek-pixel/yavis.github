"""Zusatzfunktionen (nuetzlich + lustig). Alles offline, keine Shell, keine Dateizugriffe."""
from __future__ import annotations
import ast, operator, platform, random, re, secrets, shutil, string, time
from datetime import date, datetime
from .tools import Tool, ToolRegistry

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}


def _ev(n):
    if isinstance(n, ast.Expression): return _ev(n.body)
    if isinstance(n, ast.Constant) and type(n.value) in (int, float): return n.value
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
        return -_ev(n.operand) if isinstance(n.op, ast.USub) else _ev(n.operand)
    if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
        a, b = _ev(n.left), _ev(n.right)
        if isinstance(n.op, ast.Pow) and abs(b) > 100: raise ValueError("Exponent zu gross")
        return _OPS[type(n.op)](a, b)
    raise ValueError("Nicht erlaubter Ausdruck")


def calculate(expr: str) -> str:
    try:
        r = _ev(ast.parse(expr.replace(",", ".").replace("^", "**").strip(), mode="eval"))
    except ZeroDivisionError: return "Durch null kann ich nicht teilen, Master."
    except (ValueError, SyntaxError): return "Das kann ich nicht berechnen."
    return str(round(r, 10) if isinstance(r, float) else r)


def roll_dice(arg: str) -> str:
    m = re.fullmatch(r"\s*(\d*)\s*[dDwW]\s*(\d+)\s*", arg or "w6")
    if not m: return "Format: 2w6 oder d20"
    n, sides = min(int(m.group(1) or 1), 20), min(max(int(m.group(2)), 2), 1000)
    rolls = [random.randint(1, sides) for _ in range(n)]
    return f"{rolls} = {sum(rolls)}"


JOKES = ["Warum nehmen Programmierer die Treppe nicht? Sie suchen immer den Fahrstuhl-Fehler... 404: Lift not found.",
 "Was ist ein Keks unter einem Baum? Ein schattiges Plaetzchen.",
 "Wie nennt man einen Bumerang, der nicht zurueckkommt? Stock.",
 "Warum ging der Computer zum Arzt? Er hatte einen Virus und fuehlte sich nicht mehr ganz bei Byte.",
 "Treffen sich zwei Magnete. Sagt der eine: Ich finde dich echt anziehend.",
 "Was sagt ein grosser Stift zum kleinen Stift? Wachs-mal-stift!"]
ORACLE = ["Ja, definitiv.", "Sehr wahrscheinlich.", "Die Zeichen stehen gut.", "Frag spaeter nochmal.",
          "Das bleibt im Dunkeln.", "Eher nicht.", "Auf keinen Fall.", "Die Sterne sagen: Mach erst Kaffee."]


def make_password(arg: str) -> str:
    n = min(max(int(arg), 8), 64) if (arg or "").strip().isdigit() else 16
    pool = string.ascii_letters + string.digits + "!$%&*+-?"
    return "".join(secrets.choice(pool) for _ in range(n))


def days_until(arg: str, today: date | None = None) -> str:
    try: d = datetime.strptime(arg.strip(), "%d.%m.%Y").date()
    except ValueError: return "Datum bitte als TT.MM.JJJJ."
    n = (d - (today or date.today())).days
    return "Das ist heute!" if n == 0 else f"Noch {n} Tage." if n > 0 else f"Das war vor {-n} Tagen."


def system_info() -> str:
    free = shutil.disk_usage(".").free / 1e9
    return f"{platform.system()} {platform.release()}, Python {platform.python_version()}, frei: {free:.0f} GB"


class Timers:
    def __init__(self, clock=time.monotonic) -> None:
        self.clock, self.items = clock, []          # (deadline, label)

    def set(self, arg: str) -> str:
        m = re.match(r"\s*(\d+(?:[.,]\d+)?)\s*(.*)", arg or "")
        if not m: return "Format: '5 Pudding' (Minuten + Name)"
        mins = min(float(m.group(1).replace(",", ".")), 24 * 60); label = m.group(2) or "Timer"
        self.items.append((self.clock() + mins * 60, label)); return f"Timer '{label}': {mins:g} Min. gestartet."

    def status(self) -> str:
        if not self.items: return "Keine Timer aktiv."
        return "; ".join(f"{l}: {max(0, int((d - self.clock()) // 60))} Min." for d, l in self.items)

    def due(self) -> list[str]:
        now = self.clock(); done = [l for d, l in self.items if d <= now]
        self.items = [(d, l) for d, l in self.items if d > now]; return done


def register_extras(reg: ToolRegistry, memory=None) -> Timers:
    t = Timers(); T = Tool
    for tool in (T("calculate", "Rechnet einen Ausdruck, z.B. 12*(3+4)", calculate, takes_arg=True),
        T("roll_dice", "Wuerfelt, z.B. 2w6", roll_dice, takes_arg=True),
        T("coin_flip", "Muenzwurf", lambda: random.choice(["Kopf", "Zahl"])),
        T("tell_joke", "Erzaehlt einen Witz", lambda: random.choice(JOKES)),
        T("ask_oracle", "Magische Antwort auf eine Ja/Nein-Frage", lambda: random.choice(ORACLE)),
        T("make_password", "Sicheres Passwort erzeugen (Laenge optional)", make_password, takes_arg=True),
        T("days_until", "Tage bis zu einem Datum TT.MM.JJJJ", days_until, takes_arg=True),
        T("system_info", "System- und Speicherinfo", system_info),
        T("set_timer", "Timer stellen: '10 Nudeln'", t.set, takes_arg=True),
        T("list_timers", "Aktive Timer anzeigen", t.status)):
        reg.register(tool)
    if memory is not None:
        reg.register(T("add_note", "Notiz speichern", lambda a: f"Notiz {memory.add(a)} gespeichert." if a.strip() else "Leere Notiz.", takes_arg=True))
        reg.register(T("list_notes", "Alle Notizen anzeigen", lambda: "\n".join(f"{i}: {x}" for i, x in memory.list()) or "Keine Notizen."))
    return t
