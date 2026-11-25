"""One-line error wrapper for tool entry points.

Tools must exit 0, 1 or 2 and must not print a Python traceback. Wrap the
`main` function:

    if __name__ == "__main__":
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
        import cli_error
        sys.exit(cli_error.run(main))

`run` catches every Exception (not SystemExit or KeyboardInterrupt), prints a
single line (`TypeName: first line of the message`, truncated) to stderr, and
returns 1. argparse usage errors still exit 2.

GST_DEBUG=1 re-raises the exception so the full traceback is visible (used by
the fuzz classifier and by developers). GstInputError from shared readers is a
validated input failure, not a generic-wrapper hit.
"""
from __future__ import annotations

import os, sys

LIMIT = 240


def debug_enabled() -> bool:
    v = os.environ.get("GST_DEBUG", "")
    return v not in ("", "0", "false", "False", "no", "NO")


def format_error(exc, limit=LIMIT) -> str:
    typ = type(exc).__name__
    raw = str(exc).strip() if exc is not None else ""
    msg = raw.splitlines()[0].strip() if raw else ""
    line = ("%s: %s" % (typ, msg)) if msg else typ
    if len(line) > limit:
        line = line[: limit - 3] + "..."
    return line


def _is_input_error(exc) -> bool:
    try:
        from gst_errors import GstInputError
    except ImportError:
        return type(exc).__name__ == "GstInputError"
    return isinstance(exc, GstInputError)


def run(main, argv=None) -> int:
    try:
        from gst_read import install_guards
        install_guards()
    except ImportError:
        pass
    try:
        rc = main() if argv is None else main(argv)
        if rc is None:
            return 0
        if isinstance(rc, int):
            return rc
        print(rc, file=sys.stderr)
        return 1
    except SystemExit as e:
        if e.code is None:
            return 0
        if isinstance(e.code, int):
            return e.code
        print(e.code, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("KeyboardInterrupt", file=sys.stderr)
        return 130
    except Exception as e:
        if debug_enabled():
            raise
        print(format_error(e), file=sys.stderr)
        # 1 = validated input error or generic wrapper; callers inspect the type
        # name on stderr. GstInputError is printed as "GstInputError: ...".
        return 1
