"""Lenient JSON loader for Minecraft Bedrock content files.

Bedrock content is JSON with BOMs, // and /* */ comments and trailing commas;
some files even contain several concatenated documents.  This module turns all
of that into plain Python objects.
"""
from __future__ import annotations

import json
import re

_LINE_COMMENT = re.compile(r"//[^\n\r]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode("utf-8", "replace")


def loads(text: str):
    """Parse JSONC-ish text; returns the first value found."""
    text = _BLOCK_COMMENT.sub("", text)
    text = _LINE_COMMENT.sub("", text)
    text = _TRAILING_COMMA.sub(r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # fall back: brace matching from the first '{' or '['
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    if start < 0:
        raise ValueError("no JSON value found")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unbalanced JSON")


def load(path) -> object:
    with open(path, "rb") as fh:
        return loads(decode(fh.read()))
