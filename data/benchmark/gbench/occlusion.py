"""Occlusion / partial-visibility filter for T2 crops.

Only fields the capture code actually writes are used. Boxes are NOT occlusion-tested for engine captures
(gamedata/DATASET.md), so for most sources no visibility signal exists and nothing can be filtered except the
geometric in-frame test. Per-source coverage is reported in every run (hparams.occ_stats)."""

DEFAULT_MIN_VISIBLE = 0.5      # drop entities visible less than this
DEFAULT_MIN_IN_FRAME = 0.8     # drop boxes with less than this share of their area inside the frame
REASONS = ("vanished", "truncated", "low_visible_frac", "occluded_flag", "occluded_frac", "off_frame")


def in_frame_fraction(box, w, h):
    x, y, bw, bh = box
    if bw <= 0 or bh <= 0:
        return 0.0
    ix = max(0.0, min(x + bw, w) - max(x, 0.0))
    iy = max(0.0, min(y + bh, h) - max(y, 0.0))
    return (ix * iy) / (bw * bh)


def occlusion_info(ent):
    """True if this entity carries any occlusion/visibility field we understand."""
    return any(k in ent for k in ("vanished", "truncated", "visible_frac", "visibility", "occluded"))


def occlusion_reason(ent, box, w, h, min_visible=DEFAULT_MIN_VISIBLE, min_in_frame=DEFAULT_MIN_IN_FRAME):
    """Return None to keep the entity, or the reason string it is dropped for.
    synth: vanished / truncated flags, visible_frac (reconstructed) else visibility (analytic estimate).
    godot 3D: occluded in [0,1] = share of sample points hidden behind colliders. luanti: occluded bool.
    all: share of the box inside the frame."""
    if ent.get("vanished") is True:
        return "vanished"
    if ent.get("truncated") is True:
        return "truncated"
    vf = ent.get("visible_frac")
    if vf is None:
        vf = ent.get("visibility")
    if isinstance(vf, (int, float)) and not isinstance(vf, bool) and vf < min_visible:
        return "low_visible_frac"
    oc = ent.get("occluded")
    if oc is True:
        return "occluded_flag"
    if isinstance(oc, (int, float)) and not isinstance(oc, bool) and oc > 1 - min_visible:
        return "occluded_frac"
    if in_frame_fraction(box, w, h) < min_in_frame:
        return "off_frame"
    return None
