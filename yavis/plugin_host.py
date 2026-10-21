"""Eigener Prozess fuer EIN Plugin-Tool. Aufruf: <plugin.py> <tool> <in.json> <out.json>
(Dateien statt stdin/stdout: funktioniert auch in der fensterlosen EXE.)"""
import contextlib, importlib.util, io, json, sys


def main() -> None:
    path, tool, fin, fout = sys.argv[1:5]
    try:
        with open(fin, encoding="utf-8") as f:
            arg = json.load(f).get("arg", "")
        spec = importlib.util.spec_from_file_location("yavis_plugin", path)
        mod = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()):          # print() im Plugin wird verworfen
            spec.loader.exec_module(mod)
            res = mod.TOOLS[tool](arg)
        out = {"ok": True, "result": str(res)[:4000]}
    except BaseException as e:
        out = {"ok": False, "error": f"{type(e).__name__}: {e}"[:500]}
    with open(fout, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
