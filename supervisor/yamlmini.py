"""Minimal YAML-subset parser.

The framework must work from a bare ``git clone`` with no ``pip install``, so it
cannot depend on PyYAML. This module parses the restricted subset the framework's
own configuration files use.

Supported:
    - nested mappings (indentation based)
    - block lists (``- item``) of scalars or of single-level mappings
    - inline lists (``[a, b, c]``)
    - scalars: str, int, float, bool, null
    - single and double quoted strings
    - ``#`` comments and blank lines

Deliberately NOT supported, and raising :class:`YamlError` rather than silently
misparsing: anchors, aliases, multi-document streams, block scalars (``|``/``>``),
flow mappings (``{...}``), complex keys, and tabs used for indentation.

The previous PowerShell configuration reader matched on key name alone while
ignoring nesting, so every ``max_turns`` in a file resolved to the first one.
This parser preserves structure, which the profile blocks depend on.
"""

from __future__ import annotations

__all__ = ["YamlError", "parse", "parse_file"]

_TRUE = {"true", "yes", "on"}
_FALSE = {"false", "no", "off"}
_NULL = {"", "~", "null"}


class YamlError(ValueError):
    """Raised when input falls outside the supported YAML subset."""


def _strip_comment(line: str) -> str:
    """Remove a trailing ``#`` comment that sits outside quotes."""
    out: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote is not None:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
            out.append(ch)
        elif ch == "#" and (not out or out[-1].isspace()):
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).rstrip()


def _scalar(token: str):
    text = token.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        return text[1:-1]
    lowered = text.lower()
    if lowered in _NULL:
        return None
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def _split_commas(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    for ch in text:
        if quote is not None:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
            buf.append(ch)
        elif ch == ",":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p for p in (p.strip() for p in parts) if p != ""]


def _inline_value(text: str):
    if text.startswith("{"):
        raise YamlError(f"flow mappings are not supported: {text!r}")
    if text.startswith("[") and text.endswith("]"):
        return [_scalar(part) for part in _split_commas(text[1:-1].strip())]
    if text in ("|", ">") or text.startswith(("|", ">")):
        raise YamlError(f"block scalars are not supported: {text!r}")
    if text.startswith(("&", "*")):
        raise YamlError(f"anchors and aliases are not supported: {text!r}")
    return _scalar(text)


def _key_split(content: str) -> tuple[str, str] | None:
    """Split ``key: value`` outside quotes. Returns None when there is no key."""
    quote: str | None = None
    for i, ch in enumerate(content):
        if quote is not None:
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
        elif ch == ":" and (i + 1 == len(content) or content[i + 1] in " \t"):
            return content[:i].strip(), content[i + 1 :].strip()
    return None


def _looks_like_mapping(content: str) -> bool:
    return _key_split(content) is not None


def _parse_map(lines, i, indent):
    result: dict = {}
    while i < len(lines):
        ind, content = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise YamlError(f"unexpected indentation at: {content!r}")
        if content.startswith("- "):
            break
        split = _key_split(content)
        if split is None:
            raise YamlError(f"expected 'key: value' but found: {content!r}")
        key, rest = split
        if not key:
            raise YamlError(f"empty key at: {content!r}")
        if rest != "":
            result[key] = _inline_value(rest)
            i += 1
            continue
        # Value lives on following, more-indented lines (or is null).
        if i + 1 < len(lines):
            nind, ncontent = lines[i + 1]
            if ncontent.startswith("- ") and nind >= ind:
                result[key], i = _parse_list(lines, i + 1, nind)
                continue
            if nind > ind:
                result[key], i = _parse_block(lines, i + 1, nind)
                continue
        result[key] = None
        i += 1
    return result, i


def _parse_list(lines, i, indent):
    items: list = []
    while i < len(lines):
        ind, content = lines[i]
        if ind != indent or not content.startswith("- "):
            break
        body = content[2:].strip()
        if body == "":
            raise YamlError("empty list item")
        # Collect any lines belonging to this item.
        sub = []
        j = i + 1
        while j < len(lines) and lines[j][0] > ind:
            sub.append(lines[j])
            j += 1
        if _looks_like_mapping(body):
            child_indent = sub[0][0] if sub else ind + 2
            block = [(child_indent, body)] + sub
            value, _ = _parse_map(block, 0, child_indent)
            items.append(value)
        elif sub:
            raise YamlError(f"unexpected nested block under list item: {body!r}")
        else:
            items.append(_inline_value(body))
        i = j
    return items, i


def _parse_block(lines, i, indent):
    if lines[i][1].startswith("- "):
        return _parse_list(lines, i, indent)
    return _parse_map(lines, i, indent)


def parse(text: str) -> dict:
    """Parse a YAML-subset document into a dict. Empty input yields ``{}``."""
    lines: list[tuple[int, str]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if raw.lstrip().startswith("---"):
            raise YamlError(f"line {lineno}: multi-document streams are not supported")
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        if "\t" in stripped[:indent] or stripped.lstrip(" ").startswith("\t"):
            raise YamlError(f"line {lineno}: tabs cannot be used for indentation")
        lines.append((indent, stripped.strip()))

    if not lines:
        return {}

    value, consumed = _parse_block(lines, 0, lines[0][0])
    if consumed != len(lines):
        raise YamlError(f"could not parse from: {lines[consumed][1]!r}")
    if not isinstance(value, dict):
        raise YamlError("top level of a configuration file must be a mapping")
    return value


def parse_file(path) -> dict:
    """Parse a YAML-subset file, reported against its path on failure."""
    import pathlib

    p = pathlib.Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise YamlError(f"could not read {p}: {exc}") from exc
    try:
        return parse(text)
    except YamlError as exc:
        raise YamlError(f"{p}: {exc}") from exc
