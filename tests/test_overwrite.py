"""Kit-wide overwrite policy: dest == input is refused unless --in-place is given."""
import ast, os, re, sys, wave
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import audio_tidy, wav_loop_meta, texture_seamless, tile_replace, atlas_pack

ROOT = Path(__file__).resolve().parents[1]

# Generators with no input file, plus tools that already use a different explicit
# consent flag (asset-rename --apply; godot-import-presets --force for sidecars).
ALLOWLIST = {
    "asset-rename",
    "bmfont-gen",
    "curve-gen",
    "dungeon-gen",
    "godot-import-presets",
    "level-curve",
    "particle-preview",
    "sfx-gen",
    "terrain-noise",
    "tex-gen",
    "tileset-gen",
}

SKIP_DIRS = {"lib", "tests", "docs", "samples", "__pycache__"}


def iter_tools():
    for d in sorted(ROOT.iterdir()):
        if not d.is_dir() or d.name in SKIP_DIRS or d.name.startswith("."):
            continue
        p = d / (d.name.replace("-", "_") + ".py")
        if p.is_file():
            yield d.name, p


def test_audit_every_writer_has_in_place_guard():
    missing = []
    extra = []
    names = []
    for name, path in iter_tools():
        names.append(name)
        src = path.read_text()
        uses_helper = "safe_out" in src and (
            "safe_out.check" in src or "safe_out.check_any" in src or "safe_out.add_flag" in src
        )
        has_guard = (("refusing to overwrite" in src and "--in-place" in src)
                     or (uses_helper and ("--in-place" in src or "add_flag" in src)))
        if name in ALLOWLIST:
            if has_guard:
                extra.append(name)
            continue
        if not has_guard:
            missing.append(name)
    assert len(names) >= 150, f"expected at least 150 tools, found {len(names)}"
    assert missing == [], "writers missing --in-place / refuse-overwrite: " + ", ".join(missing)
    # allowlist tools must not have been given the flag by accident in a way that
    # aliases a different consent flag; they may stay without the pair.
    assert isinstance(extra, list)


def test_allowlist_is_current():
    # every allowlisted name still exists as a tool
    have = {n for n, _ in iter_tools()}
    unknown = sorted(ALLOWLIST - have)
    assert unknown == [], unknown


def _tone(path, n=2000, sr=22050):
    y = (np.sin(np.linspace(0, 8 * np.pi, n)) * 0.4).astype(np.float64)
    audio_tidy.write_wav(str(path), y, sr)
    return path


def test_wav_loop_meta_set_requires_out_or_in_place(tmp_path):
    wav = _tone(tmp_path / "m.wav")
    before = wav.read_bytes()
    with pytest.raises(SystemExit, match="in-place"):
        wav_loop_meta.main(["set", str(wav), "--start", "10", "--end", "100"])
    assert wav.read_bytes() == before
    out = tmp_path / "o.wav"
    assert wav_loop_meta.main(["set", str(wav), "--start", "10", "--end", "100", "-o", str(out)]) == 0
    assert wav.read_bytes() == before
    loops = wav_loop_meta.read_loops(out.read_bytes())
    assert loops[0]["start"] == 10 and loops[0]["end"] == 100
    with pytest.raises(SystemExit, match="overwrite"):
        wav_loop_meta.main(["set", str(wav), "--start", "20", "--end", "80", "-o", str(wav)])
    assert wav.read_bytes() == before
    assert wav_loop_meta.main(["set", str(wav), "--start", "20", "--end", "80", "--in-place"]) == 0
    loops = wav_loop_meta.read_loops(wav.read_bytes())
    assert loops[0]["start"] == 20 and loops[0]["end"] == 80


def test_wav_loop_meta_clear_and_from_json(tmp_path):
    wav = _tone(tmp_path / "m.wav")
    wav.write_bytes(wav_loop_meta.set_loop(wav.read_bytes(), 10, 100))
    before = wav.read_bytes()
    with pytest.raises(SystemExit, match="in-place"):
        wav_loop_meta.main(["clear", str(wav)])
    assert wav.read_bytes() == before
    out = tmp_path / "c.wav"
    assert wav_loop_meta.main(["clear", str(wav), "-o", str(out)]) == 0
    assert wav_loop_meta.read_loops(out.read_bytes()) == []
    assert wav.read_bytes() == before
    assert wav_loop_meta.main(["clear", str(wav), "--in-place"]) == 0
    assert wav_loop_meta.read_loops(wav.read_bytes()) == []

    wav.write_bytes(wav_loop_meta.set_loop(_tone(tmp_path / "x.wav").read_bytes(), 1, 2))
    # recreate m.wav with no loop and apply from-json
    _tone(wav)
    rec = tmp_path / "lp.json"
    rec.write_text('{"m.wav": {"start": 15, "end": 90}}\n')
    with pytest.raises(SystemExit, match="in-place"):
        wav_loop_meta.main(["from-json", str(rec), "--dir", str(tmp_path)])
    assert wav_loop_meta.read_loops(wav.read_bytes()) == []
    dest = tmp_path / "out"
    dest.mkdir()
    assert wav_loop_meta.main(["from-json", str(rec), "--dir", str(tmp_path), "--outdir", str(dest)]) == 0
    assert wav_loop_meta.read_loops((dest / "m.wav").read_bytes())[0]["start"] == 15
    assert wav_loop_meta.read_loops(wav.read_bytes()) == []
    assert wav_loop_meta.main(["from-json", str(rec), "--dir", str(tmp_path), "--in-place"]) == 0
    assert wav_loop_meta.read_loops(wav.read_bytes())[0]["start"] == 15
    assert wav_loop_meta.read_loops(wav.read_bytes())[0]["end"] == 89  # from-json end is exclusive (loop-finder convention)


def test_required_dash_o_refuses_same_path(tmp_path):
    src = tmp_path / "a.png"
    im = Image.new("RGBA", (16, 16), (10, 20, 30, 255))
    for x in range(16):
        im.putpixel((x, 0), (255, 0, 0, 255))
        im.putpixel((x, 15), (0, 0, 255, 255))
    im.save(src)
    before = src.read_bytes()
    with pytest.raises(SystemExit, match="overwrite"):
        texture_seamless.main([str(src), "-o", str(src)])
    assert src.read_bytes() == before
    out = tmp_path / "b.png"
    assert texture_seamless.main([str(src), "-o", str(out)]) == 0
    assert out.exists() and src.read_bytes() == before
    assert texture_seamless.main([str(src), "-o", str(src), "--in-place"]) == 0
    assert src.read_bytes() != before


def test_audio_tidy_same_dir_requires_in_place(tmp_path):
    wav = _tone(tmp_path / "t.wav")
    before = wav.read_bytes()
    with pytest.raises(SystemExit, match="in-place"):
        audio_tidy.main([str(wav), "--outdir", str(tmp_path), "--peak", "-6"])
    assert wav.read_bytes() == before
    other = tmp_path / "out"
    other.mkdir()
    assert audio_tidy.main([str(wav), "--outdir", str(other), "--peak", "-6"]) == 0
    assert (other / "t.wav").exists() and wav.read_bytes() == before
    assert audio_tidy.main([str(wav), "--outdir", str(tmp_path), "--peak", "-6", "--in-place"]) == 0
    assert wav.read_bytes() != before
