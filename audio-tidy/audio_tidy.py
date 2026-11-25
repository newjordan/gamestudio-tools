#!/usr/bin/env python3
"""audio-tidy: batch-clean WAVs for the game: trim silence, normalise (peak or RMS), fade edges,
force mono/sample-rate, and report loudness. Pure Python + numpy, reads 8/16/24/32-bit PCM WAV.
Handy after MiniMax Music / VO exports before import into Godot/Wwise/FMOD.
"""
import argparse, glob, json, os, wave
import numpy as np
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402


def read_wav(path):
    raw, ch, sw, sr, n = gst_read.read_wav_frames(path)
    try:
        if sw == 1:
            x = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
        elif sw == 2:
            x = np.frombuffer(raw, "<i2").astype(np.float32) / 32768
        elif sw == 3:
            b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
            v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
            v = np.where(v & 0x800000, v - 0x1000000, v)
            x = v.astype(np.float32) / 8388608
        elif sw == 4:
            x = np.frombuffer(raw, "<i4").astype(np.float32) / 2147483648
        else:
            raise GstInputError("WAV unsupported sample width %s" % sw)
        return x.reshape(-1, ch), sr
    except GstInputError:
        raise
    except MemoryError as e:
        raise GstInputError("WAV is too large or has an invalid header") from e
    except (ValueError, RuntimeError) as e:
        raise GstInputError("WAV sample data is truncated or misaligned") from e


def write_wav(path, x, sr, bits=16):
    x = np.clip(x, -1, 1)
    if x.ndim == 1:
        x = x[:, None]
    with wave.open(path, "wb") as wf:
        wf.setnchannels(x.shape[1])
        wf.setsampwidth(bits // 8)
        wf.setframerate(sr)
        if bits == 16:
            wf.writeframes((x * 32767).astype("<i2").tobytes())
        elif bits == 24:                                       # 3 little-endian bytes per sample (the old code wrote 4 under a 3-byte header)
            v = np.round(x * 8388607).astype("<i4")
            wf.writeframes(v.view(np.uint8).reshape(-1, 4)[:, :3].tobytes())
        elif bits == 32:
            wf.writeframes((x * 2147483647).astype("<i4").tobytes())
        else:
            raise ValueError(f"unsupported bit depth {bits} (use 16, 24 or 32)")


def db(v):
    return float(20 * np.log10(max(v, 1e-9)))


def stats(x):
    m = np.abs(x).max() if x.size else 0
    r = float(np.sqrt(np.mean(x ** 2))) if x.size else 0
    return {"peak_db": round(db(m), 2), "rms_db": round(db(r), 2)}


def trim_silence(x, sr, thresh_db=-50, pad_ms=10):
    th = 10 ** (thresh_db / 20)
    loud = np.where(np.abs(x).max(axis=1) > th)[0]
    if loud.size == 0:
        return x[:0]
    pad = int(sr * pad_ms / 1000)
    return x[max(0, loud[0] - pad): min(len(x), loud[-1] + 1 + pad)]


def resample(x, sr, new_sr):
    if sr == new_sr:
        return x
    n = int(round(len(x) * new_sr / sr))
    old_t = np.arange(len(x)) / sr
    new_t = np.arange(n) / new_sr
    return np.stack([np.interp(new_t, old_t, x[:, c]) for c in range(x.shape[1])], 1).astype(np.float32)


def process(x, sr, trim=True, thresh=-50, peak=None, rms=None, fade_ms=5, mono=False, rate=None):
    if mono and x.shape[1] > 1:
        x = x.mean(axis=1, keepdims=True)
    if rate:
        x = resample(x, sr, rate)
        sr = rate
    if trim:
        x = trim_silence(x, sr, thresh)
    if x.size:
        if rms is not None:
            cur = np.sqrt(np.mean(x ** 2))
            x = x * (10 ** (rms / 20) / max(cur, 1e-9))
        if peak is not None:
            x = x * (10 ** (peak / 20) / max(np.abs(x).max(), 1e-9))
        x = np.clip(x, -1, 1)
        nf = min(int(sr * fade_ms / 1000), len(x) // 2)
        if nf:
            ramp = np.linspace(0, 1, nf)[:, None]
            x[:nf] *= ramp
            x[-nf:] *= ramp[::-1]
    return x, sr


def main(argv=None):
    ap = argparse.ArgumentParser(description="Trim, normalise and report WAV files.")
    ap.add_argument("inputs", nargs="+", help="files or globs")
    ap.add_argument("-o", "--outdir", help="write processed copies here (omit = report only)")
    ap.add_argument("--peak", type=float, help="normalise peak to this dBFS, e.g. -1")
    ap.add_argument("--rms", type=float, help="normalise RMS to this dBFS, e.g. -18")
    ap.add_argument("--no-trim", action="store_true")
    ap.add_argument("--thresh", type=float, default=-50, help="silence threshold dBFS")
    ap.add_argument("--fade-ms", type=float, default=5)
    ap.add_argument("--mono", action="store_true")
    ap.add_argument("--rate", type=int, help="resample to this rate (linear)")
    ap.add_argument("--json", help="write report JSON here")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    files = [f for pat in a.inputs for f in (sorted(glob.glob(pat)) or [pat]) if f.lower().endswith(".wav")]
    report = []
    for f in files:
        x, sr = read_wav(f)
        row = {"file": f, "sr": sr, "channels": x.shape[1], "seconds": round(len(x) / sr, 3), **stats(x)}
        if a.outdir:
            os.makedirs(a.outdir, exist_ok=True)
            y, nsr = process(x, sr, not a.no_trim, a.thresh, a.peak, a.rms, a.fade_ms, a.mono, a.rate)
            out = os.path.join(a.outdir, os.path.basename(f))
            if os.path.abspath(out) == os.path.abspath(f) and not a.in_place:
                sys.exit("refusing to overwrite the input; pick a different --outdir or pass --in-place")
            write_wav(out, y, nsr)
            row.update({"out": out, "out_seconds": round(len(y) / nsr, 3), **{"out_" + k: v for k, v in stats(y).items()}})
        report.append(row)
        print(f"{f}: {row['seconds']}s peak {row['peak_db']} dB rms {row['rms_db']} dB" +
              (f" -> {row['out']} {row['out_seconds']}s peak {row['out_peak_db']} dB" if a.outdir else ""))
    if a.json:
        json.dump(report, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
