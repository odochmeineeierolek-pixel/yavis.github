"""Startpunkt fuer die EXE."""
import sys


def _main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--plugin-host":      # Plugin-Prozess, keine Oberflaeche
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        from yavis.plugin_host import main
        main()
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":         # Selbsttest der fertigen EXE (fuer GitHub)
        from yavis.selftest import run
        return run(sys.argv[2] if len(sys.argv) > 2 else "selftest.txt")
    from yavis.gui import main
    return main()


if __name__ == "__main__":
    sys.exit(_main())
