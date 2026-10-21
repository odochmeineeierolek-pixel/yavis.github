"""Plugin-System. Plugin = Ordner mit NUR plugin.json + plugin.py (TOOLS = {"name": func(arg) -> str}).
Schutz: nie automatisch aktiv | Code-Pruefung (AST) | Freigabe an Code-Hash gebunden (Aenderung = gesperrt)
| eigener Prozess + Zeitlimit | Plugins mit Berechtigungen fragen bei jedem Aufruf nach.
EHRLICH: Die AST-Pruefung ist eine Huerde, kein echter Sandkasten. Aktiviere nur Code, den du gelesen hast."""
from __future__ import annotations
import ast, hashlib, json, os, re, shutil, subprocess, sys, tempfile, zipfile
from dataclasses import dataclass, field
from pathlib import Path
from .tools import Tool, ToolRegistry

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,30}$")
PERMS = {"network", "files"}
NET = {"socket", "urllib", "http", "requests", "ssl", "ftplib", "smtplib", "httpx"}
FILES = {"pathlib", "shutil", "glob", "tempfile"}
BLOCKED_MODS = {"os", "subprocess", "ctypes", "importlib", "builtins", "pickle", "marshal", "multiprocessing",
                "threading", "signal", "winreg", "msvcrt", "sys", "runpy", "code", "codeop", "pty"}
BLOCKED_CALLS = {"eval", "exec", "compile", "__import__", "input", "breakpoint", "globals", "locals", "vars",
                 "getattr", "setattr", "delattr"}
BLOCKED_ATTRS = {"__class__", "__subclasses__", "__globals__", "__builtins__", "__bases__", "__mro__",
                 "__dict__", "__code__", "__import__", "__loader__", "__spec__"}
MAX_FILE = 200_000


class PluginError(RuntimeError):
    pass


@dataclass
class PluginInfo:
    name: str
    path: Path
    manifest: dict
    problems: list[str] = field(default_factory=list)
    enabled: bool = False
    changed: bool = False       # war freigegeben, Code wurde seitdem geaendert


def lint(code: str, perms: list[str]) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"Syntaxfehler: {e.msg} (Zeile {e.lineno})"]
    allowed = (NET if "network" in perms else set()) | (FILES if "files" in perms else set())
    out = []
    if not any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TOOLS" for t in n.targets)
               for n in tree.body):
        out.append("TOOLS = {...} fehlt auf oberster Ebene")
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            if isinstance(n, ast.ImportFrom) and n.level:
                out.append(f"Relativer Import nicht erlaubt (Zeile {n.lineno})")
            for m in ([a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""]):
                root = m.split(".")[0]
                if root in BLOCKED_MODS or (root in NET | FILES and root not in allowed):
                    out.append(f"Import '{m}' nicht erlaubt (Zeile {n.lineno})")
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            if n.func.id in BLOCKED_CALLS or (n.func.id == "open" and "files" not in perms):
                out.append(f"Aufruf '{n.func.id}()' nicht erlaubt (Zeile {n.lineno})")
        elif (isinstance(n, ast.Attribute) and n.attr in BLOCKED_ATTRS) or (isinstance(n, ast.Name) and n.id in BLOCKED_ATTRS):
            out.append(f"Zugriff auf '{getattr(n, 'attr', None) or n.id}' nicht erlaubt (Zeile {n.lineno})")
    return out


def check_manifest(m: dict) -> list[str]:
    p = []
    if not isinstance(m, dict): return ["plugin.json ist kein Objekt"]
    if not NAME_RE.match(str(m.get("name", ""))): p.append("name: a-z, 0-9, _ (3-31 Zeichen)")
    if not isinstance(m.get("description"), str) or not m["description"].strip(): p.append("description fehlt")
    tools = m.get("tools")
    if not isinstance(tools, dict) or not tools: p.append("tools: Objekt {name: Beschreibung} noetig")
    else:
        for k, v in tools.items():
            if not NAME_RE.match(k) or not isinstance(v, str): p.append(f"Tool '{k}' ungueltig")
    perms = m.get("permissions", [])
    if not isinstance(perms, list) or not set(perms) <= PERMS: p.append(f"permissions nur aus {sorted(PERMS)}")
    if not isinstance(m.get("timeout_s", 10), int) or not 1 <= m.get("timeout_s", 10) <= 30: p.append("timeout_s: 1-30")
    return p


class PluginManager:
    def __init__(self, root: Path, host: Path | None = None) -> None:
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.host = host or Path(__file__).with_name("plugin_host.py"); self.state_file = self.root / "state.json"

    def _state(self) -> dict:
        try: return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): return {}

    def _save(self, st: dict) -> None:
        self.state_file.write_text(json.dumps(st, indent=2), encoding="utf-8")

    def code_hash(self, name: str) -> str:
        d = self.root / name; h = hashlib.sha256()
        for f in ("plugin.json", "plugin.py"): h.update((d / f).read_bytes())
        return h.hexdigest()

    def info(self, name: str) -> PluginInfo:
        d = self.root / name
        try: m = json.loads((d / "plugin.json").read_text(encoding="utf-8")); code = (d / "plugin.py").read_text(encoding="utf-8")
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
            return PluginInfo(name, d, {}, [f"Nicht lesbar: {e}"])
        probs = check_manifest(m) or lint(code, m.get("permissions", []))
        if not probs and m["name"] != name: probs = ["Ordnername und name im Manifest stimmen nicht ueberein"]
        st = self._state().get(name); good = bool(st and st.get("enabled"))
        same = good and st.get("hash") == self.code_hash(name)
        return PluginInfo(name, d, m, probs, enabled=same and not probs, changed=good and not same)

    def discover(self) -> list[PluginInfo]:
        return [self.info(d.name) for d in sorted(self.root.iterdir()) if (d / "plugin.json").exists()]

    def enable(self, name: str) -> None:
        i = self.info(name)
        if i.problems: raise PluginError("Nicht aktivierbar: " + "; ".join(i.problems))
        st = self._state(); st[name] = {"enabled": True, "hash": self.code_hash(name)}; self._save(st)

    def disable(self, name: str) -> None:
        st = self._state(); st.pop(name, None); self._save(st)

    def remove(self, name: str) -> None:
        self.disable(name)
        if NAME_RE.match(name): shutil.rmtree(self.root / name, ignore_errors=True)

    def install_dir(self, src: Path) -> str:
        """Kopiert NUR plugin.json + plugin.py. Neu installierte Plugins sind IMMER deaktiviert."""
        src = Path(src)
        try: m = json.loads((src / "plugin.json").read_text(encoding="utf-8")); code = (src / "plugin.py").read_bytes()
        except (OSError, json.JSONDecodeError) as e: raise PluginError(f"plugin.json/plugin.py nicht lesbar: {e}")
        if len(code) > MAX_FILE: raise PluginError("plugin.py zu gross")
        bad = check_manifest(m)
        if bad: raise PluginError("Manifest ungueltig: " + "; ".join(bad))
        dest = self.root / m["name"]
        if dest.exists(): raise PluginError(f"Plugin '{m['name']}' existiert schon (erst entfernen)")
        dest.mkdir(); (dest / "plugin.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
        (dest / "plugin.py").write_bytes(code); return m["name"]

    def install_zip(self, zpath: Path) -> str:
        try:
            with zipfile.ZipFile(zpath) as z, tempfile.TemporaryDirectory() as tmp:
                if {i.filename for i in z.infolist()} != {"plugin.json", "plugin.py"}:
                    raise PluginError("ZIP darf nur plugin.json und plugin.py enthalten (im Hauptordner)")
                if any(i.file_size > MAX_FILE for i in z.infolist()): raise PluginError("Datei im ZIP zu gross")
                for f in ("plugin.json", "plugin.py"): (Path(tmp) / f).write_bytes(z.read(f))
                return self.install_dir(Path(tmp))
        except (zipfile.BadZipFile, OSError) as e: raise PluginError(f"ZIP nicht lesbar: {e}")

    def stage_generated(self, manifest: dict, code: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "plugin.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            (Path(tmp) / "plugin.py").write_text(code, encoding="utf-8"); return self.install_dir(Path(tmp))

    def run(self, name: str, tool: str, arg: str) -> str:
        i = self.info(name)
        if not i.enabled: raise PluginError(f"Plugin '{name}' ist nicht aktiviert (oder Code wurde geaendert)")
        if tool not in i.manifest["tools"]: raise PluginError(f"Unbekanntes Tool '{tool}'")
        keep = ("SYSTEMROOT", "TEMP", "TMP", "windir")
        env = {"PYTHONIOENCODING": "utf-8", **{k: os.environ[k] for k in keep if k in os.environ}}
        # In der EXE ist sys.executable = YAVIS.exe -> dort startet "--plugin-host" statt der Oberflaeche
        base = [sys.executable, "--plugin-host"] if getattr(sys, "frozen", False) else [sys.executable, "-I", str(self.host)]
        with tempfile.TemporaryDirectory() as cwd:
            fin, fout = Path(cwd) / "in.json", Path(cwd) / "out.json"
            fin.write_text(json.dumps({"arg": arg}), encoding="utf-8")
            try:
                subprocess.run(base + [str(i.path / "plugin.py"), tool, str(fin), str(fout)], capture_output=True,
                               env=env, cwd=cwd, timeout=i.manifest.get("timeout_s", 10),
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except subprocess.TimeoutExpired: raise PluginError("Zeitlimit ueberschritten")
            try: data = json.loads(fout.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError): raise PluginError("Plugin lieferte kein Ergebnis (abgestuerzt?)")
        if not data.get("ok"): raise PluginError(data.get("error", "Fehler"))
        return data["result"]

    def sync(self, registry: ToolRegistry) -> None:
        """Registriert genau die aktuell freigegebenen Plugin-Tools."""
        registry.unregister_prefix("plugin_")
        for i in self.discover():
            if not i.enabled: continue
            ask = bool(i.manifest.get("permissions"))
            for t, desc in i.manifest["tools"].items():
                registry.register(Tool(f"plugin_{i.name}_{t}", f"[Plugin {i.name}] {desc}",
                                       lambda a, n=i.name, tt=t: self.run(n, tt, a), needs_confirmation=ask, takes_arg=True))


GEN_PROMPT = """Schreibe ein YAVIS-Plugin. Antworte NUR mit zwei Codebloecken.
1) ```json mit: {"name": "kleinbuchstaben_mit_unterstrich", "description": "...", "tools": {"toolname": "Beschreibung"}, "permissions": [], "timeout_s": 10}
2) ```python mit reinem Python (nur Standardbibliothek) und am Ende TOOLS = {"toolname": funktion}; jede Funktion bekommt einen String und gibt einen String zurueck.
VERBOTEN: os, sys, subprocess, eval, exec, open, getattr, Netzwerk. permissions leer lassen, ausser es ist zwingend noetig.
Wunsch: """


def parse_generated(text: str) -> tuple[dict, str]:
    j = re.search(r"```json\s*(.*?)```", text, re.S); p = re.search(r"```python\s*(.*?)```", text, re.S)
    if not j or not p: raise PluginError("Antwort enthielt nicht beide Codebloecke (json + python)")
    try: return json.loads(j.group(1)), p.group(1)
    except json.JSONDecodeError as e: raise PluginError(f"Manifest kein gueltiges JSON: {e}")


def generate_plugin(llm, manager: PluginManager, request: str) -> str:
    """LLM schreibt ein Plugin -> wird nur DEAKTIVIERT abgelegt. Aktivieren musst du nach Durchsicht selbst."""
    text = "".join(llm.chat_stream([{"role": "user", "content": GEN_PROMPT + request}]))
    manifest, code = parse_generated(text)
    return manager.stage_generated(manifest, code)
