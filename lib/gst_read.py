"""Validated asset readers for the kit.

Bad or truncated input raises ``GstInputError`` with a specific message
(for example ``WAV fmt chunk missing`` or ``GLB chunk length exceeds file``).
``install_guards()`` wraps ``json.load`` / ``json.loads``, ``PIL.Image.open``,
``wave.open``, ``xml.etree.ElementTree.parse`` and text-mode ``open`` so tools
that call those libraries directly also raise ``GstInputError`` instead of a
raw decoder exception. ``cli_error.run`` installs the guards.
"""
from __future__ import annotations

import csv
import io
import json
import os
import struct
import wave
import xml.etree.ElementTree as ET

from gst_errors import GstInputError

_GUARDS_INSTALLED = False


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------

def open_text(path, encoding="utf-8", errors=None):
    """Read a text file as a string. Invalid encoding raises GstInputError."""
    try:
        with open(path, encoding=encoding, errors=errors) as fh:
            return fh.read()
    except UnicodeDecodeError as e:
        raise GstInputError("file is not valid UTF-8") from e
    except OSError as e:
        raise GstInputError("cannot read file: %s" % e) from e


def parse_json_bytes(data, what="JSON"):
    """Parse JSON from bytes or str. The document may be any JSON value."""
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise GstInputError("%s is not valid UTF-8" % what) from e
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        raise GstInputError("%s is not valid: %s" % (what, e)) from e


def load_json(path, what="JSON"):
    try:
        raw = open(path, "rb").read()
    except OSError as e:
        raise GstInputError("cannot read file: %s" % e) from e
    return parse_json_bytes(raw, what)


def require_object(doc, what="JSON"):
    if not isinstance(doc, dict):
        raise GstInputError("%s document is not an object" % what)
    return doc


# Stay under the fuzz child's 512 MiB address-space cap for RGBA
# (Pillow's default is ~179e6 pixels, which is over 512 MiB at 4 bytes/pixel).
DEFAULT_MAX_IMAGE_PIXELS = 64_000_000

# Decoder failures we wrap into GstInputError (plus DecompressionBombError by name).
_IMAGE_DECODER_EXC = (OSError, ValueError, SyntaxError, struct.error, EOFError, IndexError, MemoryError)


def _image_input_error(exc):
    name = type(exc).__name__
    if name == "DecompressionBombError" or isinstance(exc, MemoryError):
        raise GstInputError("image is too large") from exc
    raise GstInputError("image file is not valid: %s" % exc) from exc


def open_image(path):
    """Open an image with Pillow. Unreadable files raise GstInputError."""
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as e:
        raise GstInputError("Pillow is not installed") from e
    try:
        return Image.open(path)
    except UnidentifiedImageError as e:
        raise GstInputError("image could not be identified") from e
    except GstInputError:
        raise
    except _IMAGE_DECODER_EXC as e:
        _image_input_error(e)
    except Exception as e:
        if type(e).__name__ == "DecompressionBombError":
            _image_input_error(e)
        raise


def parse_xml(path, what="XML"):
    try:
        return ET.parse(path)
    except ET.ParseError as e:
        raise GstInputError("%s is not well-formed: %s" % (what, e)) from e
    except OSError as e:
        raise GstInputError("cannot read file: %s" % e) from e


# ---------------------------------------------------------------------------
# WAV
# ---------------------------------------------------------------------------

def _wav_error_message(exc):
    msg = str(exc).strip() or type(exc).__name__
    low = msg.lower()
    if "fmt chunk and/or data chunk missing" in low or "fmt chunk" in low and "missing" in low:
        # wave often reports both together; prefer the named fmt case
        if "data chunk before fmt" in low:
            return "WAV data chunk before fmt chunk"
        if "data" in low and "fmt" in low:
            return "WAV fmt chunk missing"
        return "WAV fmt chunk missing"
    if "data chunk before fmt" in low:
        return "WAV data chunk before fmt chunk"
    if "not a riff" in low or "unknown format" in low or "unknown wave" in low:
        return "not a RIFF/WAVE file"
    return "WAV is not valid: %s" % msg


def open_wav(path):
    """Return a wave.Wave_read (caller must close). Raises GstInputError."""
    try:
        return wave.open(path, "rb")
    except GstInputError:
        raise
    except (wave.Error, EOFError, RuntimeError, struct.error, ValueError) as e:
        if isinstance(e, (EOFError,)) or "truncated" in str(e).lower():
            raise GstInputError("WAV file is truncated") from e
        raise GstInputError(_wav_error_message(e)) from e


def read_wav_frames(path):
    """Return (raw_bytes, nchannels, sampwidth, framerate, nframes)."""
    try:
        wf = open_wav(path)
        try:
            ch, sw, sr, n = wf.getnchannels(), wf.getsampwidth(), wf.getframerate(), wf.getnframes()
            raw = wf.readframes(n)
        finally:
            wf.close()
    except GstInputError:
        raise
    except MemoryError as e:
        raise GstInputError("WAV is too large or has an invalid header") from e
    except (wave.Error, EOFError, RuntimeError, struct.error, ValueError) as e:
        if isinstance(e, EOFError) or "truncated" in str(e).lower():
            raise GstInputError("WAV file is truncated") from e
        raise GstInputError(_wav_error_message(e)) from e
    if sw not in (1, 2, 3, 4):
        raise GstInputError("WAV unsupported sample width %s" % sw)
    if ch < 1:
        raise GstInputError("WAV has no channels")
    if not isinstance(sr, int) or sr < 1 or sr > 768000:
        raise GstInputError("WAV sample rate is invalid")
    if len(raw) % (ch * sw) != 0:
        raise GstInputError("WAV data length is not a multiple of sample width")
    return raw, ch, sw, sr, n


def wav_chunks(data):
    """Parse a RIFF/WAVE file into ``[(chunk_id, payload), ...]``.

    Raises GstInputError when the signature is wrong or a chunk length
    runs past the end of the buffer.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise GstInputError("not a RIFF/WAVE file")
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise GstInputError("not a RIFF/WAVE file")
    pos, out = 12, []
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = struct.unpack_from("<I", data, pos + 4)[0]
        end = pos + 8 + size
        if end > len(data):
            raise GstInputError("WAV chunk length exceeds file")
        out.append((cid, data[pos + 8:end]))
        pos = end + (size & 1)
        if pos > len(data):
            # trailing pad byte missing: tolerate if we already have the payload
            break
    return out


def wav_fmt_and_data(data):
    """Return (fmt_payload, data_payload)."""
    chs = wav_chunks(data)
    fmt = next((p for c, p in chs if c == b"fmt "), None)
    if fmt is None:
        raise GstInputError("WAV fmt chunk missing")
    dat = next((p for c, p in chs if c == b"data"), None)
    if dat is None:
        raise GstInputError("WAV data chunk missing")
    if len(fmt) < 16:
        raise GstInputError("WAV fmt chunk is truncated")
    return fmt, dat


# ---------------------------------------------------------------------------
# GLB / glTF
# ---------------------------------------------------------------------------

def load_glb_bytes(data):
    """Parse a GLB buffer into (gltf_dict, bin_bytes, version, chunks).

    ``chunks`` is ``[(ctype, payload), ...]`` in file order. The JSON
    document is required and must be an object.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise GstInputError("not a binary GLB (missing glTF magic)")
    if len(data) < 12 or data[:4] != b"glTF":
        raise GstInputError("not a binary GLB (missing glTF magic)")
    try:
        version, length = struct.unpack_from("<II", data, 4)
    except struct.error as e:
        raise GstInputError("GLB header is truncated") from e
    if length > len(data):
        raise GstInputError("GLB declared length exceeds file")
    if length < 12:
        raise GstInputError("GLB declared length is too small")
    off, js, bin_, chunks = 12, None, b"", []
    limit = min(length, len(data))
    while off < limit:
        if off + 8 > limit:
            raise GstInputError("GLB chunk header exceeds file")
        try:
            clen, ctype = struct.unpack_from("<I4s", data, off)
        except struct.error as e:
            raise GstInputError("GLB chunk header exceeds file") from e
        start, end = off + 8, off + 8 + clen
        if end > len(data) or end > length:
            raise GstInputError("GLB chunk length exceeds file")
        chunk = data[start:end]
        chunks.append((ctype, chunk))
        if ctype == b"JSON":
            js = parse_json_bytes(chunk, "GLB JSON chunk")
        elif ctype == b"BIN\x00":
            bin_ = chunk
        off = end
    if js is None:
        raise GstInputError("GLB JSON chunk missing")
    return require_object(js, "glTF"), bin_, version, chunks


def load_glb(path):
    """Load a .glb file. Returns (gltf_dict, bin_bytes)."""
    try:
        data = open(path, "rb").read()
    except OSError as e:
        raise GstInputError("cannot read file: %s" % e) from e
    js, bin_, _ver, _chunks = load_glb_bytes(data)
    return js, bin_


def load_gltf_or_glb(path):
    """Load a .glb or .gltf. Returns (gltf_dict, bin_bytes_or_None, version, chunks_or_None).

    For a .gltf (or any non-GLB buffer) ``chunks`` is None and ``bin_`` is
    None (uri buffers are left to the caller). Version defaults to 2.
    """
    try:
        data = open(path, "rb").read()
    except OSError as e:
        raise GstInputError("cannot read file: %s" % e) from e
    if data[:4] == b"glTF":
        return load_glb_bytes(data)
    doc = parse_json_bytes(data, "glTF")
    return require_object(doc, "glTF"), None, 2, None


# ---------------------------------------------------------------------------
# OBJ
# ---------------------------------------------------------------------------

def _obj_floats(parts, need, what):
    if len(parts) < need:
        raise GstInputError("OBJ %s line has too few numbers" % what)
    try:
        return [float(x) for x in parts[:need]]
    except ValueError as e:
        raise GstInputError("OBJ %s line has invalid numbers" % what) from e


def _obj_index(raw, pool_len, what):
    try:
        n = int(raw)
    except ValueError as e:
        raise GstInputError("OBJ face has an invalid %s index" % what) from e
    return (pool_len + n) if n < 0 else n - 1


def load_obj(path, check_indices=True):
    """Parse an OBJ into (v, vt, vn, cmds, prelude) matching obj_weld.load_obj.

    ``v`` is a list of [x,y,z] (the caller may wrap it in numpy). Invalid
    numbers or out-of-range face indices raise GstInputError.
    """
    v, vt, vn, cmds, prelude = [], [], [], [], []
    started = False
    text = open_text(path, errors="replace")
    for line in text.splitlines():
        raw = line
        s = raw.strip()
        if s.startswith("v "):
            started = True
            v.append(_obj_floats(s.split()[1:], 3, "vertex"))
            continue
        if s.startswith("vt "):
            started = True
            vt.append(_obj_floats(s.split()[1:], 2, "UV"))
            continue
        if s.startswith("vn "):
            started = True
            vn.append(_obj_floats(s.split()[1:], 3, "normal"))
            continue
        if s.startswith("f ") or s.startswith("l "):
            started = True
            kind = "f" if s.startswith("f ") else "l"
            vert_only = kind == "l"
            corners = []
            tokens = s.split()[1:]
            if not tokens:
                raise GstInputError("OBJ %s line has no corners" % kind)
            for tok in tokens:
                parts = tok.split("/")
                if not parts or parts[0] == "":
                    raise GstInputError("OBJ face is missing a vertex index")
                vi = _obj_index(parts[0], len(v), "vertex")
                if vert_only:
                    corners.append((vi, None, None))
                    continue
                vti = _obj_index(parts[1], len(vt), "UV") if len(parts) > 1 and parts[1] else None
                vni = _obj_index(parts[2], len(vn), "normal") if len(parts) > 2 and parts[2] else None
                corners.append((vi, vti, vni))
            cmds.append((kind, corners))
            continue
        if not started:
            prelude.append(raw)
        else:
            cmds.append(("raw", raw))
    if check_indices:
        nv, nvt, nvn = len(v), len(vt), len(vn)
        for kind, payload in cmds:
            if kind not in ("f", "l"):
                continue
            for vi, vti, vni in payload:
                if vi < 0 or vi >= nv:
                    raise GstInputError("OBJ face vertex index is out of range")
                if vti is not None and (vti < 0 or vti >= nvt):
                    raise GstInputError("OBJ face UV index is out of range")
                if vni is not None and (vni < 0 or vni >= nvn):
                    raise GstInputError("OBJ face normal index is out of range")
    return v, vt, vn, cmds, prelude


# ---------------------------------------------------------------------------
# Tiled
# ---------------------------------------------------------------------------

def check_tiled_layer_length(gids, width, height, layer_name=""):
    """Raise if a decoded GID list does not match width*height (when both set)."""
    if width is None or height is None:
        return
    try:
        w, h = int(width), int(height)
    except (TypeError, ValueError) as e:
        raise GstInputError("Tiled layer %r has a non-integer size" % layer_name) from e
    if w < 0 or h < 0:
        raise GstInputError("Tiled layer %r has a negative size" % layer_name)
    expect = w * h
    if len(gids) != expect:
        raise GstInputError("Tiled layer data length mismatch")


def load_loc_csv(path, encoding="utf-8-sig"):
    """Return (rows, fieldnames) from a localisation CSV.

    An empty file or a file with no header raises GstInputError.
    """
    try:
        text = open_text(path, encoding=encoding)
    except GstInputError:
        # also accept latin-1? no — loc files are UTF-8
        raise
    # DictReader on a StringIO so we don't depend on a live file handle
    fh = io.StringIO(text)
    rd = csv.DictReader(fh)
    if rd.fieldnames is None:
        raise GstInputError("CSV has no header row")
    # None can appear if a header cell is missing
    cols = [("" if c is None else c) for c in rd.fieldnames]
    if any(c is None for c in rd.fieldnames) or cols == [""]:
        # keep going if there is at least one named column
        if not any(cols):
            raise GstInputError("CSV has no header row")
    try:
        rows = list(rd)
    except csv.Error as e:
        raise GstInputError("CSV is not valid: %s" % e) from e
    # DictReader fills missing cells with None on short rows
    for r in rows:
        for k, v in list(r.items()):
            if v is None:
                r[k] = ""
    return rows, cols


def load_bmfont(path):
    """Return the set of character code points declared in a BMFont .fnt file."""
    import re
    text = open_text(path)
    return {int(m.group(1)) for m in re.finditer(r"^char id=(\d+)", text, re.M)}


# ---------------------------------------------------------------------------
# library guards (installed by cli_error.run)
# ---------------------------------------------------------------------------

def _guard_json():
    _load, _loads = json.load, json.loads

    def load(*args, **kwargs):
        try:
            return _load(*args, **kwargs)
        except json.JSONDecodeError as e:
            raise GstInputError("JSON is not valid: %s" % e) from e
        except UnicodeDecodeError as e:
            raise GstInputError("JSON is not valid UTF-8") from e

    def loads(*args, **kwargs):
        try:
            return _loads(*args, **kwargs)
        except json.JSONDecodeError as e:
            raise GstInputError("JSON is not valid: %s" % e) from e
        except UnicodeDecodeError as e:
            raise GstInputError("JSON is not valid UTF-8") from e
        except TypeError as e:
            # json.loads(None) etc.
            raise GstInputError("JSON is not valid: %s" % e) from e

    json.load = load
    json.loads = loads


def _guard_image():
    try:
        from PIL import Image, ImageFile, UnidentifiedImageError
    except ImportError:
        return
    if getattr(Image, "MAX_IMAGE_PIXELS", None) is None or Image.MAX_IMAGE_PIXELS > DEFAULT_MAX_IMAGE_PIXELS:
        Image.MAX_IMAGE_PIXELS = DEFAULT_MAX_IMAGE_PIXELS
    _open = Image.open
    _img_load = ImageFile.ImageFile.load
    _seek = getattr(Image.Image, "seek", None)

    def open_img(*args, **kwargs):
        try:
            return _open(*args, **kwargs)
        except UnidentifiedImageError as e:
            raise GstInputError("image could not be identified") from e
        except GstInputError:
            raise
        except _IMAGE_DECODER_EXC as e:
            _image_input_error(e)
        except Exception as e:
            if type(e).__name__ == "DecompressionBombError":
                _image_input_error(e)
            raise

    def load_img(self, *args, **kwargs):
        try:
            return _img_load(self, *args, **kwargs)
        except GstInputError:
            raise
        except _IMAGE_DECODER_EXC as e:
            _image_input_error(e)
        except Exception as e:
            if type(e).__name__ == "DecompressionBombError":
                _image_input_error(e)
            raise

    def seek_img(self, *args, **kwargs):
        try:
            return _seek(self, *args, **kwargs)
        except GstInputError:
            raise
        except EOFError:
            # Pillow uses EOFError to end an animation; do not wrap it.
            raise
        except _IMAGE_DECODER_EXC as e:
            _image_input_error(e)
        except Exception as e:
            if type(e).__name__ == "DecompressionBombError":
                _image_input_error(e)
            raise

    Image.open = open_img
    ImageFile.ImageFile.load = load_img
    if _seek is not None:
        Image.Image.seek = seek_img


def _guard_wave():
    _open = wave.open

    def open_w(f, mode="rb"):
        try:
            return _open(f, mode)
        except GstInputError:
            raise
        except (wave.Error, EOFError, RuntimeError, struct.error, ValueError) as e:
            if str(mode).startswith("w"):
                raise
            if isinstance(e, EOFError) or "truncated" in str(e).lower():
                raise GstInputError("WAV file is truncated") from e
            raise GstInputError(_wav_error_message(e)) from e

    wave.open = open_w


def _guard_et():
    _parse = ET.parse
    _fromstring = ET.fromstring

    def parse(*args, **kwargs):
        try:
            return _parse(*args, **kwargs)
        except ET.ParseError as e:
            raise GstInputError("XML is not well-formed: %s" % e) from e

    def fromstring(*args, **kwargs):
        try:
            return _fromstring(*args, **kwargs)
        except ET.ParseError as e:
            raise GstInputError("XML is not well-formed: %s" % e) from e

    ET.parse = parse
    ET.fromstring = fromstring
    # XML is an alias of fromstring in some versions
    if getattr(ET, "XML", None) is _fromstring or getattr(ET, "XML", None) is ET.fromstring:
        ET.XML = fromstring


def _guard_text_open():
    import builtins
    _open = builtins.open

    class _GuardedTextFile:
        def __init__(self, fh):
            self._fh = fh

        def read(self, *a, **k):
            try:
                return self._fh.read(*a, **k)
            except UnicodeDecodeError as e:
                raise GstInputError("file is not valid UTF-8") from e

        def readline(self, *a, **k):
            try:
                return self._fh.readline(*a, **k)
            except UnicodeDecodeError as e:
                raise GstInputError("file is not valid UTF-8") from e

        def readlines(self, *a, **k):
            try:
                return self._fh.readlines(*a, **k)
            except UnicodeDecodeError as e:
                raise GstInputError("file is not valid UTF-8") from e

        def __iter__(self):
            try:
                for line in self._fh:
                    yield line
            except UnicodeDecodeError as e:
                raise GstInputError("file is not valid UTF-8") from e

        def __enter__(self):
            self._fh.__enter__()
            return self

        def __exit__(self, *exc):
            return self._fh.__exit__(*exc)

        def __getattr__(self, name):
            return getattr(self._fh, name)

    def open_guarded(file, mode="r", *args, **kwargs):
        fh = _open(file, mode, *args, **kwargs)
        mode_s = str(mode) if mode is not None else "r"
        if "b" not in mode_s and "r" in mode_s:
            return _GuardedTextFile(fh)
        return fh

    builtins.open = open_guarded


def install_guards():
    """Wrap stdlib / Pillow decoders so they raise GstInputError. Idempotent."""
    global _GUARDS_INSTALLED
    if _GUARDS_INSTALLED:
        return
    _GUARDS_INSTALLED = True
    _guard_json()
    _guard_image()
    _guard_wave()
    _guard_et()
    _guard_text_open()
