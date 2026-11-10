"""Мягкая интеграция с CharmPkk: цветной вывод, если библиотека есть; обычный, если нет."""
import sys

_charm = None
_c = None
_available = False

try:
    from charmpkk import console as _c
    _charm = __import__("charmpkk")
    _available = True
except Exception:
    _available = False


def has_charm():
    return _available


def console():
    return _c


def theme(name="halloween"):
    if not _available:
        return None
    try:
        return _c.get_theme(name)
    except Exception:
        return None


def _fg(color):
    if not _available or not color:
        return None
    if isinstance(color, str) and color.startswith("#"):
        try:
            return _c.fg_hex(color)
        except Exception:
            return None
    return color


def colorize(text, color=None, style=None):
    if _available:
        try:
            return _c.colorize(text, fg=_fg(color), style=style)
        except Exception:
            return text
    return text


def banner(title, subtitle=None, color="#7aa2ff"):
    if _available:
        try:
            return _c.banner(title, subtitle, fg=_fg(color))
        except Exception:
            pass
    out = f"\n=== {title} ==="
    if subtitle:
        out += f"\n{subtitle}"
    return out + "\n"


def box(content, title=None, color="#7aa2ff"):
    if _available:
        try:
            return _c.box(content, title=title, border_fg=_fg(color))
        except Exception:
            pass
    lines = content.split("\n") if isinstance(content, str) else [str(x) for x in content]
    max_w = max((len(line) for line in lines), default=0)
    if title:
        max_w = max(max_w, len(title) + 2)
    max_w = min(max_w, 100)
    top = "+" + "-" * (max_w + 2) + "+"
    out = [top]
    if title:
        out.append(f"| {title.center(max_w)} |")
        out.append("+" + "-" * (max_w + 2) + "+")
    for line in lines:
        out.append(f"| {line.ljust(max_w)[:max_w]} |")
    out.append(top)
    return "\n".join(out)


def table(headers, rows, header_color="#7aa2ff"):
    if _available:
        try:
            return _c.Table(headers=headers, rows=rows, header_fg=_fg(header_color)).render()
        except Exception:
            pass
    all_rows = [list(headers)] + [list(r) for r in rows]
    n_cols = len(headers)
    widths = [max(len(str(r[i])) if i < len(r) else 0 for r in all_rows) for i in range(n_cols)]
    lines = []
    for i, row in enumerate(all_rows):
        cells = [str(row[j]) if j < len(row) else "" for j in range(n_cols)]
        lines.append(" | ".join(c.ljust(widths[j]) for j, c in enumerate(cells)))
        if i == 0:
            lines.append("-+-".join("-" * w for w in widths))
    return "\n".join(lines)


def section(title, color="#7aa2ff"):
    if _available:
        try:
            return _c.rule(width=60, title=title, fg=_fg(color), title_align="left")
        except Exception:
            pass
    return f"\n{'-' * 60}\n  {title}\n{'-' * 60}"


def kv(pairs, key_color="#7aa2ff"):
    if _available:
        try:
            data = dict(pairs) if not isinstance(pairs, dict) else pairs
            return _c.key_value(data, key_fg=_fg(key_color))
        except Exception:
            pass
    if isinstance(pairs, dict):
        items = list(pairs.items())
    else:
        items = list(pairs)
    if not items:
        return ""
    max_k = max(len(str(k)) for k, _ in items)
    return "\n".join(f"  {str(k).ljust(max_k)} : {v}" for k, v in items)


def info(msg):
    if _available:
        try:
            print(_c.info(msg))
            return
        except Exception:
            pass
    print(f"[i] {msg}")


def success(msg):
    if _available:
        try:
            print(_c.success(msg))
            return
        except Exception:
            pass
    print(f"[+] {msg}")


def warning(msg):
    if _available:
        try:
            print(_c.warning(msg))
            return
        except Exception:
            pass
    print(f"[!] {msg}")


def error(msg):
    if _available:
        try:
            print(_c.error(msg))
            return
        except Exception:
            pass
    print(f"[x] {msg}")


def _decode_raw(raw):
    """utf-8 → cp866 → cp1251. Для консольных утилит на русской Windows."""
    if not raw:
        return ""
    if isinstance(raw, str):
        return raw
    for enc in ("utf-8", "cp866", "cp1251"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, AttributeError):
            continue
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return str(raw)


__all__ = [
    "has_charm", "console", "theme", "colorize",
    "banner", "box", "table", "section", "kv",
    "info", "success", "warning", "error",
    "_decode_raw",
]