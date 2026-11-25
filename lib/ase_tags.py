"""Aseprite tag expansion shared by ase-to-godot and ase-json-import (one implementation, one behaviour)."""

MAX_CLIP_FRAMES = 2048


def expand_tag(frm, to, direction, repeat):
    """Frame indices Aseprite plays for one tag, and whether the clip loops.

    forward: frm..to. reverse: to..frm. pingpong: forward then back without
    doubling either end (frm..to..frm+1), so a looping clip is seamless.
    pingpong_reverse starts from the last frame. A repeat of 0 means "forever"
    (loop); a repeat of N plays N cycles once (no loop), each cycle ending on
    its start frame when it is a ping-pong. Clips are clamped to
    MAX_CLIP_FRAMES unrolled frames.
    """
    fwd = list(range(frm, to + 1))
    if direction == "reverse":
        cycle = fwd[::-1]
    elif direction in ("pingpong", "pingpong_reverse"):
        base = fwd if direction == "pingpong" else fwd[::-1]
        cycle = base + base[-2:0:-1] if len(base) > 2 else list(base)
    else:
        cycle = fwd
    if not repeat or repeat < 0:
        return cycle, True
    pingpong = direction in ("pingpong", "pingpong_reverse")
    n = max(1, min(int(repeat), MAX_CLIP_FRAMES // max(1, len(cycle))))
    seq = cycle * n
    if pingpong and len(cycle) > 1:
        seq = seq + [cycle[0]]                # a finite ping-pong returns to where it started
    return seq, False
