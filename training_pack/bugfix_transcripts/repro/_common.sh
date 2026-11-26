# usage: GST_ROOT=<kit checkout> bash bugN.sh   (prints what the user would see)
set -u
: "${GST_ROOT:?set GST_ROOT to a kit checkout}"
gst() { python3 "$GST_ROOT/gst" "$@"; }
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT; cd "$T"
