"""Pure-Python Zstandard (RFC 8878) frame decoder: stdlib only.

`decompress(data)` decodes one or more concatenated frames (skippable frames
are skipped) made of raw, RLE and compressed blocks: Huffman-coded literals
(direct and FSE-compressed weights, one or four streams, treeless reuse) and
FSE-coded sequences (predefined, RLE, FSE-compressed and repeat tables, with
repeat-offset history). The content checksum is verified when the frame has one.

Not supported, and refused with a `GstInputError`: dictionaries, and frames
whose output would pass `max_output` (default 32 MiB). Every malformed input
raises `GstInputError`; nothing else escapes.

It is a reader of small data (tile layers, config blobs), not a fast codec:
expect a few MB/s.
"""
from __future__ import annotations

import struct

from gst_errors import GstInputError

MAGIC = 0xFD2FB528
SKIP_LO, SKIP_HI = 0x184D2A50, 0x184D2A5F
BLOCK_MAX = 128 * 1024
DEFAULT_MAX_OUTPUT = 32 * 1024 * 1024

# predefined FSE distributions (RFC 8878 section 3.1.1.3.2.2.1); -1 is "less than one"
LL_DEFAULT = (4, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 2, 1, 1, 1, 1, 1, -1, -1, -1, -1)
OF_DEFAULT = (1, 1, 1, 1, 1, 1, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, -1, -1, -1, -1)
ML_DEFAULT = (1, 4, 3, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
              1, 1, 1, 1, 1, 1, 1, 1, -1, -1, -1, -1, -1, -1, -1)

LL_BASE = tuple(range(16)) + (16, 18, 20, 22, 24, 28, 32, 40, 48, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536)
LL_BITS = (0,) * 16 + (1, 1, 1, 1, 2, 2, 3, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)
ML_BASE = tuple(range(3, 35)) + (35, 37, 39, 41, 43, 47, 51, 59, 67, 83, 99, 131, 259, 515, 1027, 2051, 4099, 8195, 16387, 32771, 65539)
ML_BITS = (0,) * 32 + (1, 1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)


def _fail(msg):
    raise GstInputError("zstd: " + msg)


# ---------------------------------------------------------------- xxHash64 (content checksum)
_M64 = (1 << 64) - 1
_P1, _P2, _P3, _P4, _P5 = (11400714785074694791, 14029467366897019727, 1609587929392839161,
                           9650029242287828579, 2870177450012600261)


def _rotl(x, r):
    return ((x << r) | (x >> (64 - r))) & _M64


def _round(acc, inp):
    return (_rotl((acc + inp * _P2) & _M64, 31) * _P1) & _M64


def xxh64(data, seed=0):
    n = len(data)
    i = 0
    if n >= 32:
        v1, v2, v3, v4 = (seed + _P1 + _P2) & _M64, (seed + _P2) & _M64, seed & _M64, (seed - _P1) & _M64
        end = n - 32
        unpack = struct.Struct("<4Q").unpack_from
        while i <= end:
            a, b, c, d = unpack(data, i)
            v1, v2, v3, v4 = _round(v1, a), _round(v2, b), _round(v3, c), _round(v4, d)
            i += 32
        h = (_rotl(v1, 1) + _rotl(v2, 7) + _rotl(v3, 12) + _rotl(v4, 18)) & _M64
        for v in (v1, v2, v3, v4):
            h = ((h ^ _round(0, v)) * _P1 + _P4) & _M64
    else:
        h = (seed + _P5) & _M64
    h = (h + n) & _M64
    while i + 8 <= n:
        k = _round(0, struct.unpack_from("<Q", data, i)[0])
        h = (_rotl(h ^ k, 27) * _P1 + _P4) & _M64
        i += 8
    if i + 4 <= n:
        h = (_rotl(h ^ ((struct.unpack_from("<I", data, i)[0] * _P1) & _M64), 23) * _P2 + _P3) & _M64
        i += 4
    while i < n:
        h = (_rotl(h ^ ((data[i] * _P5) & _M64), 11) * _P1) & _M64
        i += 1
    h ^= h >> 33
    h = (h * _P2) & _M64
    h ^= h >> 29
    h = (h * _P3) & _M64
    h ^= h >> 32
    return h


# ---------------------------------------------------------------- bit readers
class _Forward:
    """LSB-first reader (FSE table descriptions)."""

    def __init__(self, data, start=0):
        self.data = data
        self.bitpos = start * 8

    def read(self, n):
        if n == 0:
            return 0
        pos = self.bitpos
        lo, hi = pos >> 3, (pos + n + 7) >> 3
        if hi > len(self.data):
            _fail("FSE table description is truncated")
        value = int.from_bytes(self.data[lo:hi], "little") >> (pos & 7)
        self.bitpos = pos + n
        return value & ((1 << n) - 1)

    def bytes_used(self):
        return (self.bitpos + 7) >> 3


class _Backward:
    """Reader over a stream written backwards: the last byte holds a '1' sentinel bit, data lies below it."""

    def __init__(self, data):
        if not data or data[-1] == 0:
            _fail("bitstream has no end marker")
        self.data = data
        self.pos = (len(data) - 1) * 8 + data[-1].bit_length() - 1      # bits left to read

    def read(self, n):
        """Read n bits (most recent first). Reading past the start yields zeros and leaves pos negative."""
        if n == 0:
            return 0
        pos = self.pos - n
        self.pos = pos
        if pos >= 0:
            lo, hi = pos >> 3, (self.pos + n + 7) >> 3
            return (int.from_bytes(self.data[lo:hi], "little") >> (pos & 7)) & ((1 << n) - 1)
        if pos + n <= 0:
            return 0
        top = self.data[: (pos + n + 7) >> 3]
        value = int.from_bytes(top, "little") & ((1 << (pos + n)) - 1)
        return value << (-pos)

    def peek(self, n):
        """Look at the next n bits without consuming; missing bits below the start read as zero."""
        pos = self.pos
        if pos >= n:
            lo, hi = (pos - n) >> 3, (pos + 7) >> 3
            return (int.from_bytes(self.data[lo:hi], "little") >> ((pos - n) & 7)) & ((1 << n) - 1)
        if pos <= 0:
            return 0
        value = int.from_bytes(self.data[: (pos + 7) >> 3], "little") & ((1 << pos) - 1)
        return value << (n - pos)


# ---------------------------------------------------------------- FSE
def _read_ncount(data, start, max_symbol, max_log):
    """Read an FSE normalised-count description. Returns (counts, accuracy_log, bytes_used)."""
    r = _Forward(data, start)
    al = r.read(4) + 5
    if al > max_log:
        _fail("FSE accuracy log %d is larger than the allowed %d" % (al, max_log))
    remaining = (1 << al) + 1
    threshold = 1 << al
    nbits = al + 1
    counts = []
    previous0 = False
    while remaining > 1 and len(counts) <= max_symbol:
        if previous0:
            while True:
                rep = r.read(2)
                counts.extend([0] * rep)
                if len(counts) > max_symbol + 1:
                    _fail("FSE table lists too many symbols")
                if rep != 3:
                    break
            previous0 = False
            if len(counts) > max_symbol:
                break
        mx = (2 * threshold - 1) - remaining
        low = r.read(nbits - 1)
        if low < mx:
            count = low
        else:
            count = low | (r.read(1) << (nbits - 1))
            if count >= threshold:
                count -= mx
        count -= 1
        remaining -= -count if count < 0 else count
        counts.append(count)
        previous0 = count == 0
        while remaining < threshold:
            nbits -= 1
            threshold >>= 1
        if remaining < 1:
            _fail("FSE counts overflow the table")
    if remaining != 1:
        _fail("FSE counts do not fill the table")
    if len(counts) > max_symbol + 1:
        _fail("FSE table lists too many symbols")
    return counts, al, r.bytes_used() - start


def _build_fse(counts, al):
    """Decoding table: lists of symbol, nbits, base for every state."""
    size = 1 << al
    symbol = [0] * size
    nxt = {}
    high = size - 1
    for s, c in enumerate(counts):
        if c == -1:
            symbol[high] = s
            high -= 1
            nxt[s] = 1
        elif c > 0:
            nxt[s] = c
    step = (size >> 1) + (size >> 3) + 3
    mask = size - 1
    pos = 0
    for s, c in enumerate(counts):
        for _ in range(c if c > 0 else 0):
            symbol[pos] = s
            pos = (pos + step) & mask
            while pos > high:
                pos = (pos + step) & mask
    if pos != 0:
        _fail("FSE table could not be laid out")
    nbits, base = [0] * size, [0] * size
    for u in range(size):
        s = symbol[u]
        ns = nxt[s]
        nxt[s] = ns + 1
        nb = al - (ns.bit_length() - 1)
        if nb < 0:
            _fail("FSE state count is corrupt")
        nbits[u] = nb
        base[u] = (ns << nb) - size
    return {"al": al, "symbol": symbol, "nbits": nbits, "base": base}


def _rle_table(symbol):
    return {"al": 0, "symbol": [symbol], "nbits": [0], "base": [0]}


_PREDEFINED = {}


def _predefined(kind):
    if kind not in _PREDEFINED:
        counts, al = {"ll": (LL_DEFAULT, 6), "of": (OF_DEFAULT, 5), "ml": (ML_DEFAULT, 6)}[kind]
        _PREDEFINED[kind] = _build_fse(counts, al)
    return _PREDEFINED[kind]


# ---------------------------------------------------------------- Huffman literals
def _huffman_table(block, max_weights=255):
    """Parse a Huffman tree description at the start of block. Returns (table, max_bits, bytes_used)."""
    if not block:
        _fail("Huffman tree description is missing")
    head = block[0]
    if head >= 128:
        n = head - 127
        used = 1 + (n + 1) // 2
        if used > len(block):
            _fail("Huffman weights are truncated")
        weights = []
        for i in range(n):
            byte = block[1 + i // 2]
            weights.append((byte >> 4) if i % 2 == 0 else (byte & 15))
    else:
        used = 1 + head
        if head == 0 or used > len(block):
            _fail("FSE-compressed Huffman weights are truncated")
        counts, al, hdr = _read_ncount(block[:used], 1, 255, 6)
        table = _build_fse(counts, al)
        stream = _Backward(block[1 + hdr:used])
        s1 = stream.read(al)
        s2 = stream.read(al)
        if stream.pos < 0:
            _fail("FSE weight stream is truncated")
        weights = []
        sym, nb, base = table["symbol"], table["nbits"], table["base"]
        while True:
            weights.append(sym[s1])
            s1 = base[s1] + stream.read(nb[s1])
            if stream.pos < 0:
                weights.append(sym[s2])
                break
            weights.append(sym[s2])
            s2 = base[s2] + stream.read(nb[s2])
            if stream.pos < 0:
                weights.append(sym[s1])
                break
            if len(weights) > 255:
                _fail("too many Huffman weights")
    if len(weights) > 255 or not weights:
        _fail("Huffman tree has an unusable number of weights")
    total = 0
    for w in weights:
        if w > 11:
            _fail("Huffman weight is out of range")
        if w:
            total += 1 << (w - 1)
    if total == 0:
        _fail("Huffman tree has no symbols")
    max_bits = total.bit_length()                      # next power of two above total
    left = (1 << max_bits) - total
    if left == 0 or left & (left - 1):
        _fail("Huffman weights do not complete a prefix code")
    weights.append(left.bit_length())                  # the implied last weight
    if max_bits > 11:
        _fail("Huffman code is longer than 11 bits")
    size = 1 << max_bits
    sym_of, bits_of = [0] * size, [0] * size
    pos = 0
    for w in range(1, max_bits + 1):
        n = 1 << (w - 1)
        for s, ws in enumerate(weights):
            if ws == w:
                if pos + n > size:
                    _fail("Huffman table overflow")
                sym_of[pos:pos + n] = [s] * n
                bits_of[pos:pos + n] = [max_bits + 1 - w] * n
                pos += n
    if pos != size:
        _fail("Huffman table is not complete")
    return (sym_of, bits_of), max_bits, used


def _huffman_stream(data, count, table, max_bits):
    sym_of, bits_of = table
    r = _Backward(data)
    out = bytearray()
    peek = r.peek
    for _ in range(count):
        idx = peek(max_bits)
        r.pos -= bits_of[idx]
        out.append(sym_of[idx])
        if r.pos < 0:
            _fail("Huffman stream is truncated")
    if r.pos != 0:
        _fail("Huffman stream has unused bits")
    return bytes(out)


def _literals(block, state):
    """Parse the literals section. Returns (literal bytes, bytes used)."""
    if not block:
        _fail("empty block has no literals section")
    b0 = block[0]
    ltype, sf = b0 & 3, (b0 >> 2) & 3
    if ltype in (0, 1):
        if sf in (0, 2):
            size, hdr = b0 >> 3, 1
        elif sf == 1:
            if len(block) < 2:
                _fail("literals header is truncated")
            size, hdr = (b0 | (block[1] << 8)) >> 4, 2
        else:
            if len(block) < 3:
                _fail("literals header is truncated")
            size, hdr = (b0 | (block[1] << 8) | (block[2] << 16)) >> 4, 3
        if size > BLOCK_MAX:
            _fail("literals section is larger than a block")
        if ltype == 0:
            if hdr + size > len(block):
                _fail("raw literals are truncated")
            return block[hdr:hdr + size], hdr + size
        if hdr + 1 > len(block):
            _fail("RLE literal is missing")
        return block[hdr:hdr + 1] * size, hdr + 1
    hdr = {0: 3, 1: 3, 2: 4, 3: 5}[sf]
    if len(block) < hdr:
        _fail("literals header is truncated")
    v = int.from_bytes(block[:hdr], "little")
    bits = {0: 10, 1: 10, 2: 14, 3: 18}[sf]
    regen = (v >> 4) & ((1 << bits) - 1)
    comp = (v >> (4 + bits)) & ((1 << bits) - 1)
    streams = 1 if sf == 0 else 4
    if regen > BLOCK_MAX or hdr + comp > len(block):
        _fail("compressed literals are truncated or too large")
    body = block[hdr:hdr + comp]
    if ltype == 2:
        table, max_bits, used = _huffman_table(body)
        state["huff"] = (table, max_bits)
        body = body[used:]
    else:
        if state.get("huff") is None:
            _fail("treeless literals without a previous Huffman tree")
        table, max_bits = state["huff"]
    if streams == 1:
        return _huffman_stream(body, regen, table, max_bits), hdr + comp
    if len(body) < 6:
        _fail("four-stream jump table is truncated")
    s1, s2, s3 = struct.unpack_from("<HHH", body, 0)
    if 6 + s1 + s2 + s3 >= len(body):
        _fail("four-stream sizes exceed the literals")
    seg = (regen + 3) // 4
    counts = [seg, seg, seg, regen - 3 * seg]
    if counts[3] < 0:
        _fail("four-stream literal sizes are inconsistent")
    cuts = [6, 6 + s1, 6 + s1 + s2, 6 + s1 + s2 + s3, len(body)]
    out = b"".join(_huffman_stream(body[cuts[i]:cuts[i + 1]], counts[i], table, max_bits) for i in range(4))
    return out, hdr + comp


# ---------------------------------------------------------------- sequences
def _seq_table(mode, kind, block, off, state, max_symbol, max_log):
    if mode == 0:
        table = _predefined(kind)
    elif mode == 1:
        if off >= len(block):
            _fail("RLE sequence symbol is missing")
        if block[off] > max_symbol:
            _fail("RLE sequence symbol is out of range")
        table = _rle_table(block[off])
        off += 1
    elif mode == 2:
        counts, al, used = _read_ncount(block, off, max_symbol, max_log)
        table = _build_fse(counts, al)
        off += used
    else:
        table = state.get(kind)
        if table is None:
            _fail("repeat sequence table without a previous one")
    state[kind] = table
    return table, off


def _block_sequences(block, off, literals, out, state, rep, window, limit):
    """Execute the sequences section (block[off:]) appending to bytearray out. Returns the new rep history."""
    if off >= len(block):
        _fail("sequences section is missing")
    n = block[off]
    off += 1
    if n == 0:
        out += literals
        return rep
    if n >= 128:
        if n == 255:
            if off + 2 > len(block):
                _fail("sequence count is truncated")
            n = block[off] + (block[off + 1] << 8) + 0x7F00
            off += 2
        else:
            if off + 1 > len(block):
                _fail("sequence count is truncated")
            n = ((n - 128) << 8) + block[off]
            off += 1
    if off >= len(block):
        _fail("sequence modes byte is missing")
    modes = block[off]
    off += 1
    if modes & 3:
        _fail("reserved bits of the sequence modes are set")
    ll_t, off = _seq_table((modes >> 6) & 3, "ll", block, off, state, 35, 9)
    of_t, off = _seq_table((modes >> 4) & 3, "of", block, off, state, 31, 8)
    ml_t, off = _seq_table((modes >> 2) & 3, "ml", block, off, state, 52, 9)
    stream = _Backward(block[off:])
    rd = stream.read
    sl, so, sm = rd(ll_t["al"]), rd(of_t["al"]), rd(ml_t["al"])
    if stream.pos < 0:
        _fail("sequence bitstream is truncated")
    lit_pos = 0
    nlit = len(literals)
    r0, r1, r2 = rep
    start = len(out)
    for i in range(n):
        ofc, mlc, llc = of_t["symbol"][so], ml_t["symbol"][sm], ll_t["symbol"][sl]
        if ofc > 31 or mlc > 52 or llc > 35:
            _fail("sequence code is out of range")
        ofv = (1 << ofc) + rd(ofc)
        ml = ML_BASE[mlc] + rd(ML_BITS[mlc])
        ll = LL_BASE[llc] + rd(LL_BITS[llc])
        if i + 1 < n:
            sl = ll_t["base"][sl] + rd(ll_t["nbits"][sl])
            sm = ml_t["base"][sm] + rd(ml_t["nbits"][sm])
            so = of_t["base"][so] + rd(of_t["nbits"][so])
        if stream.pos < 0:
            _fail("sequence bitstream is truncated")
        if ofv > 3:
            offset = ofv - 3
            r0, r1, r2 = offset, r0, r1
        else:
            idx = ofv if ll else ofv + 1
            if idx == 1:
                offset = r0
            elif idx == 2:
                offset, r0, r1 = r1, r1, r0
            elif idx == 3:
                offset, r0, r1, r2 = r2, r2, r0, r1
            else:
                offset = r0 - 1
                r0, r1, r2 = offset, r0, r1
        if offset <= 0:
            _fail("sequence has a zero offset")
        if lit_pos + ll > nlit:
            _fail("sequence uses more literals than the block has")
        if ll:
            out += literals[lit_pos:lit_pos + ll]
            lit_pos += ll
        if len(out) - start + ml > BLOCK_MAX or len(out) + ml > limit:
            _fail("output is larger than the %d byte limit or the block passes 128 KiB" % limit)
        have = len(out)
        if offset > have or offset > window:
            _fail("match offset reaches before the start of the data")
        src = have - offset
        if offset >= ml:
            out += out[src:src + ml]
        else:
            chunk = bytes(out[src:have])
            out += (chunk * (ml // offset + 1))[:ml]
    if stream.pos != 0:
        _fail("sequence bitstream has unused bits")
    out += literals[lit_pos:]
    return (r0, r1, r2)


# ---------------------------------------------------------------- frames
def _frame(data, off, limit, verify):
    n = len(data)
    if off + 5 > n:
        _fail("frame header is truncated")
    fhd = data[off + 4]
    off += 5
    fcs_flag, single, checksum, dict_flag = fhd >> 6, (fhd >> 5) & 1, (fhd >> 2) & 1, fhd & 3
    if fhd & 0x08:
        _fail("reserved frame header bit is set")
    window = 0
    if not single:
        if off >= n:
            _fail("frame header is truncated")
        wd = data[off]
        off += 1
        base = 1 << (10 + (wd >> 3))
        window = base + (base >> 3) * (wd & 7)
    dsz = (0, 1, 2, 4)[dict_flag]
    if off + dsz > n:
        _fail("frame header is truncated")
    if dsz and int.from_bytes(data[off:off + dsz], "little"):
        _fail("this frame needs a dictionary, which is not supported")
    off += dsz
    fsz = {0: 1 if single else 0, 1: 2, 2: 4, 3: 8}[fcs_flag]
    if off + fsz > n:
        _fail("frame header is truncated")
    content = None
    if fsz:
        content = int.from_bytes(data[off:off + fsz], "little")
        if fsz == 2:
            content += 256
        off += fsz
    if single:
        window = content
    if content is not None and content > limit:
        _fail("frame declares %d bytes of output, over the %d byte limit" % (content, limit))
    out = bytearray()
    state = {}
    rep = (1, 4, 8)
    while True:
        if off + 3 > n:
            _fail("block header is truncated")
        bh = data[off] | (data[off + 1] << 8) | (data[off + 2] << 16)
        off += 3
        last, btype, bsize = bh & 1, (bh >> 1) & 3, bh >> 3
        if btype == 3:
            _fail("reserved block type")
        if btype == 1:
            if off >= n:
                _fail("RLE block is truncated")
            if bsize > BLOCK_MAX:
                _fail("RLE block is larger than 128 KiB")
            if len(out) + bsize > limit:
                _fail("output is larger than the %d byte limit" % limit)
            out += data[off:off + 1] * bsize
            off += 1
        else:
            if bsize > BLOCK_MAX:
                _fail("block is larger than 128 KiB")
            if off + bsize > n:
                _fail("block is truncated")
            body = data[off:off + bsize]
            off += bsize
            if btype == 0:
                if len(out) + bsize > limit:
                    _fail("output is larger than the %d byte limit" % limit)
                out += body
            else:
                literals, used = _literals(body, state)
                before = len(out)
                # sequences may reach back into earlier blocks of the frame, so they work on the whole output
                rep = _block_sequences(body, used, literals, out, state, rep, window or (1 << 31), limit)
                if len(out) - before > BLOCK_MAX:
                    _fail("block output is larger than 128 KiB")
        if len(out) > limit:
            _fail("output is larger than the %d byte limit" % limit)
        if last:
            break
    if content is not None and content != len(out):
        _fail("frame content size says %d bytes but %d were decoded" % (content, len(out)))
    if checksum:
        if off + 4 > n:
            _fail("content checksum is truncated")
        if verify and struct.unpack_from("<I", data, off)[0] != (xxh64(bytes(out)) & 0xFFFFFFFF):
            _fail("content checksum mismatch (the data is corrupt)")
        off += 4
    return bytes(out), off


def decompress(data, max_output=DEFAULT_MAX_OUTPUT, verify_checksum=True):
    """Decode Zstandard data (one or more frames). Raises GstInputError on anything malformed."""
    data = bytes(data)
    out, off = [], 0
    total = 0
    if not data:
        _fail("input is empty")
    while off < len(data):
        if off + 4 > len(data):
            _fail("trailing bytes after the last frame")
        magic = struct.unpack_from("<I", data, off)[0]
        if SKIP_LO <= magic <= SKIP_HI:
            if off + 8 > len(data):
                _fail("skippable frame is truncated")
            size = struct.unpack_from("<I", data, off + 4)[0]
            if off + 8 + size > len(data):
                _fail("skippable frame is truncated")
            off += 8 + size
            continue
        if magic != MAGIC:
            _fail("not a Zstandard frame (bad magic number)")
        piece, off = _frame(data, off, max_output - total, verify_checksum)
        total += len(piece)
        out.append(piece)
    return b"".join(out)


def decompress_auto(data, max_output=DEFAULT_MAX_OUTPUT):
    """Use a fast native decoder when one is importable (Python 3.14 `compression.zstd`, `pyzstd`, `zstd`),
    otherwise this module's pure-Python decoder. Always raises GstInputError on bad data."""
    for mod, attr in (("compression.zstd", "decompress"), ("pyzstd", "decompress"), ("zstd", "decompress")):
        try:
            parts = mod.split(".")
            fn = getattr(__import__(mod, fromlist=[parts[-1]] if len(parts) > 1 else []), attr)
        except (ImportError, AttributeError):
            continue
        try:
            out = fn(bytes(data))
        except Exception as e:
            raise GstInputError("zstd: decompress failed (%s)" % e) from e
        if len(out) > max_output:
            raise GstInputError("zstd: output is larger than the %d byte limit" % max_output)
        return out
    return decompress(data, max_output)
