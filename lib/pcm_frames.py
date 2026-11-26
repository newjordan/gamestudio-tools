"""Integer PCM frames for tools that rearrange samples.

Reading through float32 and writing with a 32767 scale drops 1 LSB on every
non-zero 16-bit sample (and more on 24/32-bit). Operations that only reorder,
copy, or negate samples stay on these integers so a same-width round trip is
bit-exact. A width change is a shift, which keeps the sign bit in place.
"""
import os, wave

import numpy as np

import gst_read


def decode(raw, sw):
    """Interleaved signed integers. 8-bit WAV is offset-binary."""
    if sw == 1:
        return np.frombuffer(raw, dtype=np.uint8).astype(np.int64) - 128
    if sw == 2:
        return np.frombuffer(raw, dtype="<i2").astype(np.int64)
    if sw == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        v = b[:, 0].astype(np.int64) | (b[:, 1].astype(np.int64) << 8) | (b[:, 2].astype(np.int64) << 16)
        return np.where((v & 0x800000) != 0, v - 0x1000000, v)
    if sw == 4:
        return np.frombuffer(raw, dtype="<i4").astype(np.int64)
    raise ValueError("unsupported sample width %s" % sw)


def convert_width(samples, src_bits, dst_bits):
    if src_bits == dst_bits:
        return samples
    shift = int(dst_bits) - int(src_bits)
    s = samples.astype(np.int64, copy=False)
    return s << shift if shift > 0 else s >> (-shift)


def encode(samples, bits):
    flat = np.ascontiguousarray(samples, dtype=np.int64).reshape(-1)
    if bits == 16:
        flat = np.clip(flat, -32768, 32767)
        return flat.astype("<i2").tobytes()
    if bits == 24:
        flat = np.clip(flat, -8388608, 8388607)
        v = np.ascontiguousarray(flat.astype("<i4"))
        return np.ascontiguousarray(v.view(np.uint8).reshape(-1, 4)[:, :3]).tobytes()
    if bits == 32:
        flat = np.clip(flat, -2147483648, 2147483647)
        return flat.astype("<i4").tobytes()
    raise ValueError("unsupported bit depth %s" % bits)


def read_frames(path):
    """Return (samples[frames, channels] int64, sample_rate, bits)."""
    raw, ch, sw, sr, _n = gst_read.read_wav_frames(str(path))
    if sw not in (1, 2, 3, 4):
        raise ValueError("unsupported sample width %s" % sw)
    samples = decode(raw, sw).reshape(-1, ch)
    return samples, int(sr), sw * 8


def write_frames(path, samples, sr, bits):
    raw = encode(samples, bits)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    channels = 1 if np.ndim(samples) == 1 else int(samples.shape[1])
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(bits // 8)
        wf.setframerate(int(sr))
        wf.writeframes(raw)


def negate(samples, bits):
    """Polarity invert. The most-negative code has no positive twin, so it saturates."""
    limit = 1 << (int(bits) - 1)
    return np.clip(-samples.astype(np.int64), -limit, limit - 1)


def to_bits(samples, src_bits, dst_bits):
    src = src_bits if src_bits in (8, 16, 24, 32) else 16
    dst = dst_bits if dst_bits in (16, 24, 32) else 16
    return convert_width(samples, src, dst), dst
