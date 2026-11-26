"""Version 2.6.0: PCM tools that only rearrange samples must be bit-exact,
and sfx-mix --help must name the normalize recipe key."""
import os, struct, subprocess, sys, wave

import numpy as np
import pytest

import anim_retarget_fps
import audio_concat
import loop_finder
import sfx_mix
import wav_dc_remove
import sfx_reverse
import wav_chan_split
import wav_chan_swap
import wav_gain
import wav_invert
import wav_mono

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _write(path, samples, sr=8000, channels=1, bits=16):
    sw = bits // 8
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sw)
        w.setframerate(sr)
        if bits == 16:
            w.writeframes(struct.pack("<%dh" % len(samples), *samples))
        elif bits == 24:
            buf = bytearray()
            for s in samples:
                v = int(s) & 0xFFFFFF
                buf += bytes((v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF))
            w.writeframes(bytes(buf))
        elif bits == 32:
            w.writeframes(struct.pack("<%di" % len(samples), *[int(s) for s in samples]))
        else:
            raise AssertionError(bits)


def _read(path):
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        samples = list(struct.unpack("<%dh" % (len(raw) // 2), raw))
    elif sw == 3:
        samples = []
        for i in range(0, len(raw), 3):
            v = int.from_bytes(raw[i:i + 3], "little", signed=False)
            if v & 0x800000:
                v -= 0x1000000
            samples.append(v)
    elif sw == 4:
        samples = list(struct.unpack("<%di" % (len(raw) // 4), raw))
    else:
        samples = list(raw)
    return samples, ch, sw * 8, sr, n


def test_sfx_reverse_is_bit_exact_for_every_pcm_width(tmp_path):
    cases = {
        16: [0, 1, -1, 2, -3, 32767, -32768, 100, -100, 0, 7, -8],
        24: [0, 1, -1, 2, -3, 8388607, -8388608, 100000, -100000, 0],
        32: [0, 1, -1, 2, -3, 2147483647, -2147483648, 100000, -100000, 0],
    }
    for bits, samples in cases.items():
        src, rev, back = tmp_path / f"s{bits}.wav", tmp_path / f"r{bits}.wav", tmp_path / f"b{bits}.wav"
        _write(src, samples, bits=bits)
        assert sfx_reverse.main([str(src), "-o", str(rev)]) == 0
        got, ch, out_bits, sr, n = _read(rev)
        assert (ch, out_bits, sr, n) == (1, bits, 8000, len(samples))
        assert got == list(reversed(samples)), bits
        assert sfx_reverse.main([str(rev), "-o", str(back)]) == 0
        assert _read(back)[0] == samples, bits
    stereo = [1, 2, 3, 4, -5, 6, 0, 0]
    src = tmp_path / "st.wav"
    _write(src, stereo, channels=2)
    out = tmp_path / "st_r.wav"
    assert sfx_reverse.main([str(src), "-o", str(out)]) == 0
    assert _read(out)[0] == [0, 0, -5, 6, 3, 4, 1, 2]
    # widening is a shift, so the sign bit stays put
    wide = tmp_path / "wide.wav"
    assert sfx_reverse.main([str(tmp_path / "s16.wav"), "-o", str(wide), "--bits", "24"]) == 0
    assert _read(wide)[0] == [s << 8 for s in reversed(cases[16])]


def test_wav_invert_negates_pcm_exactly(tmp_path):
    samples = [0, 1, -1, 2, -3, 32767, -32768, 100, -100, 7]
    src, out, back = tmp_path / "a.wav", tmp_path / "b.wav", tmp_path / "c.wav"
    _write(src, samples)
    assert wav_invert.main([str(src), "-o", str(out)]) == 0
    once = _read(out)[0]
    assert once == [0, -1, 1, -2, 3, -32767, 32767, -100, 100, -7]
    assert wav_invert.main([str(out), "-o", str(back)]) == 0
    # only the saturated full-scale code fails to return; every other sample does
    assert _read(back)[0] == [0, 1, -1, 2, -3, 32767, -32767, 100, -100, 7]


def test_wav_chan_swap_is_bit_exact(tmp_path):
    samples = [1, 2, 3, 4, -5, 6, 32767, -32768]
    src, once, twice = tmp_path / "st.wav", tmp_path / "a.wav", tmp_path / "b.wav"
    _write(src, samples, channels=2)
    assert wav_chan_swap.main([str(src), "-o", str(once), "--swap"]) == 0
    assert _read(once)[0] == [2, 1, 4, 3, 6, -5, -32768, 32767]
    assert wav_chan_swap.main([str(once), "-o", str(twice), "--swap"]) == 0
    assert _read(twice)[0] == samples


def test_wav_chan_split_join_is_bit_exact(tmp_path):
    samples = [1, 2, 3, 4, -5, 6, 0, -32768]
    src = tmp_path / "st.wav"
    _write(src, samples, channels=2)
    stems = tmp_path / "stems"
    assert wav_chan_split.main([str(src), "-o", str(stems)]) == 0
    assert _read(stems / "st_L.wav")[0] == [1, 3, -5, 0]
    assert _read(stems / "st_R.wav")[0] == [2, 4, 6, -32768]
    joined = tmp_path / "back.wav"
    assert wav_chan_split.main([str(stems / "st_L.wav"), str(stems / "st_R.wav"), "--join", str(joined)]) == 0
    assert _read(joined)[0] == samples


def test_wav_gain_zero_is_bit_exact(tmp_path):
    samples = [0, 1, -1, 32767, -32768, 100, -7]
    src, out = tmp_path / "a.wav", tmp_path / "g.wav"
    _write(src, samples)
    assert wav_gain.main([str(src), "-o", str(out), "--gain", "0"]) == 0
    assert _read(out)[0] == samples


def test_wav_mono_copy_is_bit_exact(tmp_path):
    mono = [0, 1, -1, 32767, -32768, 9]
    src, out = tmp_path / "m.wav", tmp_path / "o.wav"
    _write(src, mono)
    assert wav_mono.main([str(src), "-o", str(out)]) == 0
    assert _read(out)[0] == mono
    stereo = [1, 2, 3, 4, -5, 6, 32767, -32768]
    st, left, right = tmp_path / "st.wav", tmp_path / "l.wav", tmp_path / "r.wav"
    _write(st, stereo, channels=2)
    assert wav_mono.main([str(st), "-o", str(left), "--mode", "left"]) == 0
    assert wav_mono.main([str(st), "-o", str(right), "--mode", "right"]) == 0
    assert _read(left)[0] == [1, 3, -5, 32767]
    assert _read(right)[0] == [2, 4, 6, -32768]


def test_audio_concat_unscaled_is_bit_exact(tmp_path):
    a, b = [0, 1, -1, 100, -100, 7], [3, -4, 5, 0]
    fa, fb, out = tmp_path / "a.wav", tmp_path / "b.wav", tmp_path / "reel.wav"
    _write(fa, a)
    _write(fb, b)
    assert audio_concat.main([str(fa), str(fb), "-o", str(out), "--peak-db", "0", "--gap-ms", "0"]) == 0
    assert _read(out)[0] == a + b
    gapped = tmp_path / "gap.wav"
    assert audio_concat.main([str(fa), str(fb), "-o", str(gapped), "--peak-db", "0", "--gap-ms", "1"]) == 0
    # 1 ms at 8000 Hz is 8 exact zero samples
    assert _read(gapped)[0] == a + [0] * 8 + b


def test_wav_dc_remove_zero_mean_is_bit_exact(tmp_path):
    samples = [0, 1, -1, 2, -2, 100, -100, 0]
    src, outdir = tmp_path / "z.wav", tmp_path / "out"
    _write(src, samples)
    assert wav_dc_remove.main([str(src), "-o", str(outdir)]) == 0
    assert _read(outdir / "z.wav")[0] == samples
    biased = [1000, 1002, 998, 1000]
    src2 = tmp_path / "b.wav"
    _write(src2, biased)
    assert wav_dc_remove.main([str(src2), "-o", str(outdir)]) == 0
    assert _read(outdir / "b.wav")[0] == [0, 2, -2, 0]


def test_anim_retarget_accepts_name_keyed_clips(tmp_path):
    src = tmp_path / "clips.json"
    src.write_text('{"clips": {"walk": {"frames": ["a", "b", "c", "d"], "fps": 12, "loop": true}}}')
    out = tmp_path / "rt.json"
    assert anim_retarget_fps.main([str(src), "-o", str(out), "--fps", "24"]) == 0
    clip = __import__("json").load(open(out))["clips"]["walk"]
    assert clip["fps"] == 24 and clip["frames"] == ["a", "b", "c", "d"]
    assert isinstance(__import__("json").load(open(out))["clips"], dict)


def test_sfx_mix_help_documents_normalize():
    script = os.path.join(ROOT, "sfx-mix", "sfx_mix.py")
    r = subprocess.run([sys.executable, script, "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    text = r.stdout
    for key in ("normalize", "peak_db", "tail_ms", "layers", "offset_ms", "gain_db"):
        assert key in text, key
    assert "ceiling" in text.lower()


def test_audio_concat_help_documents_peak_ceiling():
    script = os.path.join(ROOT, "audio-concat", "audio_concat.py")
    r = subprocess.run([sys.executable, script, "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "peak ceiling" in r.stdout.lower()
    assert "default -1" in r.stdout


def test_sfx_mix_normalize_raises_a_quiet_layer(tmp_path):
    src = tmp_path / "q.wav"
    _write(src, [1000, -1000, 500, 0])
    recipe = tmp_path / "mix.json"
    recipe.write_text('{"sample_rate": 8000, "channels": 1, "normalize": true, "peak_db": -1.0,'
                      ' "layers": [{"file": "q.wav"}]}')
    out = tmp_path / "m.wav"
    assert sfx_mix.main([str(recipe), "-o", str(out)]) == 0
    samples = _read(out)[0]
    peak = max(abs(s) for s in samples) / 32768.0
    # -1 dBFS is about 29204/32768; the quiet source peaked at 1000
    assert peak == pytest.approx(10 ** (-1 / 20), rel=0.02)
    plain = tmp_path / "plain.json"
    plain.write_text('{"sample_rate": 8000, "channels": 1, "peak_db": -1.0, "layers": [{"file": "q.wav"}]}')
    ceiling = tmp_path / "c.wav"
    assert sfx_mix.main([str(plain), "-o", str(ceiling)]) == 0
    # peak_db without normalize is a ceiling: a quiet layer is not turned up
    assert max(abs(s) for s in _read(ceiling)[0]) < 2000


def test_loop_finder_tied_scores_pick_earliest_then_shortest():
    # Differences past 4 decimal places are the same rank. The later start's
    # slightly higher raw score must not win, and the same start keeps the shorter loop.
    chosen = loop_finder.pick_candidate([
        (1.00004, 500, 8000),
        (0.99996, 100, 12000),
        (0.99995, 100, 4000),
        (0.5, 0, 100),
    ])
    assert chosen[0] == 10000
    assert (chosen[1], chosen[2]) == (100, 4000)
    # A genuinely higher score still beats an earlier, shorter loop.
    higher = loop_finder.pick_candidate([(0.9, 0, 10), (1.0, 50, 8000)])
    assert (higher[1], higher[2]) == (50, 8000)
    # A repeated buffer has many perfect loops. The search must settle on one
    # pair, and a second run must return that same pair.
    sr, period = 8000, 400
    cycle = np.sin(2 * np.pi * np.arange(period) / period)
    x = np.tile(cycle, 80).astype(np.float32)[:, None]
    first = loop_finder.find_loop(x, sr, window_s=0.2, min_len_s=0.4, tail_s=1.0, head_frac=0.5, candidates=12)
    second = loop_finder.find_loop(x, sr, window_s=0.2, min_len_s=0.4, tail_s=1.0, head_frac=0.5, candidates=12)
    assert first == second
    assert first["score"] == 1.0
    assert first["start"] < first["end"]
    assert (first["end"] - first["start"]) % period == 0
