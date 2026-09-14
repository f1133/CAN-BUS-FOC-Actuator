"""Minimal S-expression reader/writer for KiCad files."""
from __future__ import annotations


class Sym(str):
    """A bare token (not a quoted string)."""


def parse(text: str):
    """Parse one or more top-level s-expressions; returns a list of nodes."""
    i, n = 0, len(text)
    out, stack = [], []
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c == "(":
            node = []
            (stack[-1] if stack else out).append(node)
            stack.append(node)
            i += 1
        elif c == ")":
            stack.pop()
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while text[j] != '"':
                if text[j] == "\\":
                    buf.append(text[j + 1]); j += 2
                else:
                    buf.append(text[j]); j += 1
            (stack[-1] if stack else out).append("".join(buf))
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()":
                j += 1
            (stack[-1] if stack else out).append(Sym(text[i:j]))
            i = j
    return out


def dumps(node, indent=0) -> str:
    if isinstance(node, Sym):
        return str(node)
    if isinstance(node, str):
        return '"' + node.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(node, (int, float)):
        return str(node)
    parts = [dumps(x, indent + 1) for x in node]
    one = "(" + " ".join(parts) + ")"
    # keep short nodes on one line, break long ones
    if len(one) <= 200 or not any(isinstance(x, list) for x in node[1:]):
        return one
    head = dumps(node[0], indent + 1)
    pad = "  " * (indent + 1)
    body = "\n".join(pad + dumps(x, indent + 1) for x in node[1:])
    return f"({head}\n{body}\n" + "  " * indent + ")"


def find(node, tag):
    """All direct children of `node` whose head is `tag`."""
    return [x for x in node if isinstance(x, list) and x and x[0] == tag]


def first(node, tag):
    r = find(node, tag)
    return r[0] if r else None
