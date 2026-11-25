#!/usr/bin/env bash
# install.sh: drop the gamestudio-tools kit onto a machine. Nothing here runs until you run it, and nothing
# talks to any other machine. Safe by default: --dry-run prints every action without doing any of them.
#
#   ./install.sh [--prefix DIR] [--link-dir DIR] [--venv] [--with-tests] [--tarball FILE] [--dry-run]
#   ./install.sh --uninstall [--prefix DIR] [--link-dir DIR] [--dry-run]
#
#   --prefix DIR     where the kit goes (default: $HOME/.local/share/gamestudio-tools)
#   --link-dir DIR   put a `gst` launcher in DIR (for example $HOME/.local/bin). Without it nothing goes on PATH.
#   --venv           create PREFIX/venv and pip install requirements.txt into it (needs network access to PyPI);
#                    with --with-tests it also installs requirements-dev.txt (pytest) so `gst test` works in the venv.
#                    Without it the installer only checks that Pillow and numpy import and tells you what is missing.
#   --with-tests     also copy tests/ and requirements-dev.txt (so `gst test` works)
#   --tarball FILE   install from a `gst bundle` tarball instead of this folder (FILE.sha256 is verified when present)
#   --uninstall      remove PREFIX (only if it holds this installer's marker file) and launchers in --link-dir that point into it
#   --dry-run        show what would happen
set -euo pipefail

PREFIX="${HOME:-/tmp}/.local/share/gamestudio-tools"; LINK_DIR=""; VENV=0; TESTS=0; TARBALL=""; DRY=0; UNINSTALL=0
MARKER=".gst-install"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() { echo "install.sh: $*" >&2; exit 1; }
say() { echo "$*"; }
act() { if [ "$DRY" = 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }   # runs the argv as given, never through eval

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix) [ $# -ge 2 ] || die "--prefix needs a directory"; PREFIX="$2"; shift 2;;
    --link-dir) [ $# -ge 2 ] || die "--link-dir needs a directory"; LINK_DIR="$2"; shift 2;;
    --venv) VENV=1; shift;;
    --with-tests) TESTS=1; shift;;
    --tarball) [ $# -ge 2 ] || die "--tarball needs a file"; TARBALL="$2"; shift 2;;
    --uninstall) UNINSTALL=1; shift;;
    --dry-run) DRY=1; shift;;
    -h|--help) sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0;;
    *) die "unknown option: $1 (see --help)";;
  esac
done
case "$PREFIX" in ""|"/"|"$HOME"|"${HOME:-}/") die "refusing to use $PREFIX as the install prefix";; esac

if [ "$UNINSTALL" = 1 ]; then
  [ -f "$PREFIX/$MARKER" ] || die "$PREFIX has no $MARKER file, so it was not installed by this script; leaving it alone"
  if [ -n "$LINK_DIR" ] && [ -e "$LINK_DIR/gst" ]; then
    if grep -qF "$PREFIX" "$LINK_DIR/gst" 2>/dev/null || [ "$(readlink "$LINK_DIR/gst" 2>/dev/null || true)" = "$PREFIX/gst" ]; then act rm -f "$LINK_DIR/gst"
    else say "leaving $LINK_DIR/gst alone: it does not point into $PREFIX"; fi
  fi
  act rm -rf "$PREFIX"; say "uninstalled $PREFIX"; exit 0
fi

# ---- source
WORK=""
cleanup() { [ -n "$WORK" ] && rm -rf "$WORK"; return 0; }; trap cleanup EXIT
if [ -n "$TARBALL" ]; then
  [ -f "$TARBALL" ] || die "no such tarball: $TARBALL"
  if [ -f "$TARBALL.sha256" ]; then
    want="$(cut -d' ' -f1 "$TARBALL.sha256")"; got="$(sha256sum "$TARBALL" | cut -d' ' -f1)"
    [ "$want" = "$got" ] || die "sha256 mismatch for $TARBALL"; say "sha256 verified"
  else say "warning: $TARBALL.sha256 not found, tarball not verified"; fi
  WORK="$(mktemp -d)"; tar -xzf "$TARBALL" -C "$WORK"; SRC="$(find "$WORK" -mindepth 1 -maxdepth 1 -type d | head -n1)"
  [ -f "$SRC/gst" ] || die "tarball does not look like a gamestudio-tools bundle"
fi
[ -f "$SRC/gst" ] || die "cannot find gst next to install.sh"

# ---- python
PY="$(command -v python3 || true)"; [ -n "$PY" ] || die "python3 is required"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || die "Python 3.10+ is required (found $("$PY" -V 2>&1))"
say "python: $("$PY" -V 2>&1) at $PY"

# ---- existing install
if [ -e "$PREFIX" ] && [ ! -f "$PREFIX/$MARKER" ] && [ -n "$(ls -A "$PREFIX" 2>/dev/null || true)" ]; then die "$PREFIX exists, is not empty and was not installed by this script"; fi
if [ -f "$PREFIX/$MARKER" ]; then say "upgrading the existing install at $PREFIX (venv, if any, is kept)"; fi

# ---- copy
say "installing $(cat "$SRC/VERSION" 2>/dev/null || echo '?') to $PREFIX"
act mkdir -p "$PREFIX"
EXCL=(--exclude=samples --exclude=__pycache__ --exclude=.pytest_cache --exclude=release-bundles --exclude='*.tar.gz' --exclude='*.sha256' --exclude=contact_sheet.png --exclude=venv --exclude=.godot --exclude='*.uid')
if [ "$TESTS" = 0 ]; then EXCL+=(--exclude=tests --exclude=requirements-dev.txt --exclude=run_tests.sh); fi
if [ "$DRY" = 1 ]; then
  n=$(cd "$SRC" && tar -cf - "${EXCL[@]}" . | tar -tf - | grep -vc '/$' || true); echo "[dry-run] copy $n files from $SRC to $PREFIX"
else
  (cd "$SRC" && tar -cf - "${EXCL[@]}" .) | (cd "$PREFIX" && tar -xf -)
  printf 'gamestudio-tools %s\ninstalled %s\nsource %s\n' "$(cat "$SRC/VERSION" 2>/dev/null || echo '?')" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$SRC" > "$PREFIX/$MARKER"
fi
act chmod +x "$PREFIX/gst" "$PREFIX/install.sh"

# ---- dependencies
RUNPY="$PY"
if [ "$VENV" = 1 ]; then
  act "$PY" -m venv "$PREFIX/venv"
  act "$PREFIX/venv/bin/pip" install --quiet -r "$PREFIX/requirements.txt"
  if [ "$TESTS" = 1 ] && [ -f "$SRC/requirements-dev.txt" ]; then   # pytest (and optional fonttools) so `gst test` runs inside the venv
    act "$PREFIX/venv/bin/pip" install --quiet -r "$PREFIX/requirements-dev.txt"
  fi
  RUNPY="$PREFIX/venv/bin/python"
elif ! "$PY" -c 'import PIL, numpy' 2>/dev/null; then
  say "warning: Pillow and/or numpy are missing for $PY. Re-run with --venv, or: $PY -m pip install -r '$PREFIX/requirements.txt'"
fi

# ---- launcher
if [ -n "$LINK_DIR" ]; then
  act mkdir -p "$LINK_DIR"
  if [ "$DRY" = 1 ]; then echo "[dry-run] write launcher $LINK_DIR/gst -> $PREFIX/gst (python: $RUNPY)"
  else
    [ ! -e "$LINK_DIR/gst" ] || grep -qF "$PREFIX" "$LINK_DIR/gst" 2>/dev/null || [ "$(readlink "$LINK_DIR/gst" 2>/dev/null || true)" = "$PREFIX/gst" ] || die "$LINK_DIR/gst already exists and is not from this prefix; not overwriting"
    printf '#!/bin/sh\nexec "%s" "%s/gst" "$@"\n' "$RUNPY" "$PREFIX" > "$LINK_DIR/gst"; chmod +x "$LINK_DIR/gst"
  fi
  say "launcher: $LINK_DIR/gst (make sure $LINK_DIR is on PATH)"
else
  say "no --link-dir given: nothing was added to PATH. Run it as: $RUNPY $PREFIX/gst list"
fi

# ---- check
if [ "$DRY" = 0 ]; then "$RUNPY" "$PREFIX/gst" doctor || say "doctor reported problems (see above)"; fi
say "done."
