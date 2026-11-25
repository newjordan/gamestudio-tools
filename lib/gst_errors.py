"""Typed input errors for kit readers.

Tools and shared readers raise `GstInputError` for malformed or incomplete
asset input. `cli_error.run` prints one line and exits 1. Set GST_DEBUG=1
to re-raise (full traceback) so a fuzz or developer can classify the cause.
"""
from __future__ import annotations


class GstInputError(Exception):
    """Bad asset input. The message should name what was wrong (for example
    'WAV fmt chunk missing' or 'GLB chunk length exceeds file')."""

    def __init__(self, message: str):
        super().__init__(message)
