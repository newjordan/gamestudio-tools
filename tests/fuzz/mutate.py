"""Stdlib mutations: empty, truncated, bit-flipped, random-byte."""
from __future__ import annotations

import os, random


def empty(data: bytes) -> bytes:
    return b""


def truncated(data: bytes, rng: random.Random) -> bytes:
    if not data:
        return b""
    n = rng.randint(0, max(0, len(data) - 1))
    return data[:n]


def bit_flipped(data: bytes, rng: random.Random, nflip=None) -> bytes:
    if not data:
        return b"\x00"
    buf = bytearray(data)
    n = nflip if nflip is not None else max(1, min(8, len(buf) // 8 or 1))
    for _ in range(n):
        i = rng.randrange(len(buf))
        buf[i] ^= 1 << rng.randrange(8)
    return bytes(buf)


def random_byte(data: bytes, rng: random.Random, frac=0.15) -> bytes:
    length = len(data) if data else rng.randint(0, 64)
    if not data:
        return bytes(rng.randrange(256) for _ in range(length))
    buf = bytearray(data)
    n = max(1, int(round(len(buf) * frac)))
    for _ in range(n):
        buf[rng.randrange(len(buf))] = rng.randrange(256)
    return bytes(buf)


def fully_random(data: bytes, rng: random.Random) -> bytes:
    """A buffer of random bytes with no leftover structure from the seed."""
    n = rng.randint(32, 256)
    return bytes(rng.randrange(256) for _ in range(n))


MUTATORS = {
    "empty": empty,
    "truncated": truncated,
    "bit-flipped": bit_flipped,
    "random-byte": random_byte,
    "fully-random": fully_random,
}


def apply(kind, data, rng):
    return MUTATORS[kind](data, rng) if kind != "empty" else empty(data)
