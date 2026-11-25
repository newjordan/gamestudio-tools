"""Shared overwrite guard for gamestudio-tools.

A tool may overwrite an input file only when the user passes --in-place.
Import with:

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import safe_out
"""
import os

MSG = "refusing to overwrite the input; pick a different output path or pass --in-place"


def same_path(a, b):
    if not a or not b:
        return False
    try:
        return os.path.abspath(a) == os.path.abspath(b)
    except (TypeError, ValueError, OSError):
        return False


def check(src, dest, in_place=False, what="input"):
    """Raise SystemExit if dest is src and --in-place was not given. Returns dest."""
    if dest and src and same_path(src, dest) and not in_place:
        raise SystemExit(f"refusing to overwrite the {what}; pick a different output path or pass --in-place")
    return dest


def check_any(sources, dest, in_place=False, what="input"):
    for src in sources or []:
        check(src, dest, in_place, what)
    return dest


def add_flag(ap, **kwargs):
    ap.add_argument("--in-place", action="store_true",
                    help="allow overwriting the input file", **kwargs)
    return ap
