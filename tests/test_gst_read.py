
"""Shared readers raise GstInputError with a specific message for bad input."""
import os, struct, sys, wave, tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError
import gst_read


def _tmp(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data if isinstance(data, (bytes, bytearray)) else data.encode("utf-8"))
    return str(p)


def test_wav_fmt_chunk_missing(tmp_path):
    # RIFF/WAVE with a data chunk only (no fmt)
    data_payload = b"\x00\x00"
    body = b"WAVE" + b"data" + struct.pack("<I", len(data_payload)) + data_payload
    raw = b"RIFF" + struct.pack("<I", len(body)) + body
    with pytest.raises(GstInputError, match="WAV fmt chunk missing"):
        gst_read.wav_fmt_and_data(raw)


def test_wav_chunk_length_exceeds_file(tmp_path):
    body = b"WAVE" + b"fmt " + struct.pack("<I", 100) + b"\x00\x00"  # claims 100, has 2
    raw = b"RIFF" + struct.pack("<I", len(body)) + body
    with pytest.raises(GstInputError, match="WAV chunk length exceeds file"):
        gst_read.wav_chunks(raw)


def test_glb_chunk_length_exceeds_file(tmp_path):
    # Declared length equals the file size, but the JSON chunk claims 5000 bytes.
    chunk = struct.pack("<I4s", 5000, b"JSON") + b"{}"
    data = struct.pack("<4sII", b"glTF", 2, 12 + len(chunk)) + chunk
    with pytest.raises(GstInputError, match="GLB chunk length exceeds file"):
        gst_read.load_glb_bytes(data)


def test_glb_declared_length_exceeds_file():
    data = struct.pack("<4sII", b"glTF", 2, 5000) + b"\x00" * 8
    with pytest.raises(GstInputError, match="GLB declared length exceeds file"):
        gst_read.load_glb_bytes(data)


def test_tiled_layer_data_length_mismatch():
    with pytest.raises(GstInputError, match="Tiled layer data length mismatch"):
        gst_read.check_tiled_layer_length([1, 2, 3], 2, 2, "ground")


def test_json_and_image_guards(tmp_path):
    gst_read.install_guards()
    bad = _tmp(tmp_path, "x.json", b"{not json")
    with pytest.raises(GstInputError, match="JSON is not valid"):
        import json
        json.load(open(bad, encoding="utf-8"))


def test_loc_csv_short_row_none_cells(tmp_path):
    # A short row makes csv.DictReader fill missing cells with None; the
    # reader must normalise those to empty strings so tools can call .strip().
    p = _tmp(tmp_path, "short.csv", "id,en,fr\nhello,Hi\n")
    rows, cols = gst_read.load_loc_csv(p)
    assert cols[:2] == ["id", "en"]
    assert rows[0]["fr"] == ""
    assert None not in rows[0].values()


def test_open_image_unidentified(tmp_path):
    gst_read.install_guards()
    p = _tmp(tmp_path, "x.png", b"not-an-image")
    with pytest.raises(GstInputError, match="image could not be identified"):
        gst_read.open_image(p)
