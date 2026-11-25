"""Romanian for text produced by marinekit (cards, validation, seasonal gate, Methods content, zones).

marinekit writes English. The viewer translates it here, without touching marinekit, by matching the English
sentence templates and refilling the Romanian template with the same values (numbers, dates, classes).

    from viewer.i18n_data import tr, md
    tr("Estimated Secchi depth 2.5 m on 2026-11-23 ...")   -> Romanian, or "[EN] <original>" if no template fits
    md(uncertainty_markdown)                               -> paragraph by paragraph (tables, lists, bold leads)

In English mode both return the input unchanged.

How a string is translated (first hit wins):
1. EXACT: the whole string.
2. TEMPLATES: an English template with typed placeholders, matched against the whole string.
3. Sentence by sentence (split after ". " before a capital letter), then clause by clause ("; "), each part through
   1 and 2. Every part must translate, otherwise the whole block stays English with an "[EN]" marker: never half
   and half.

Writing a template (in the i18n_ro_*.py tables):
    T("Estimated Secchi depth {a:n} m on {d:d} (normal for the date {b:n} m)",
      "Adâncimea Secchi estimată {a} m pe {d} (normal pentru această dată {b} m)")
Placeholder kinds (English side; the Romanian side uses the bare {name}):
    n  number              -> decimal comma in Romanian (12.45 -> 12,45; +0.56 -> +0,56)
    i  integer / year      -> kept
    d  ISO date            -> Romanian date (2026-11-23 -> 23 nov. 2026)
    t  text                -> translated recursively (must translate, else the template does not match)
    l  text                -> like t, first letter lowercased
    s  text kept as is     -> names, dataset IDs, station codes (numbers inside get the decimal comma)
    k  text kept verbatim  -> nothing changed
    m  month name (Jan, Aug, August) -> Romanian month
Templates are tried in registration order; put specific ones before general ones.
"""

from __future__ import annotations

import re
from functools import lru_cache

from viewer.i18n import MONTHS, MONTHS_SHORT, lang

EXACT: dict[str, str] = {}
TEMPLATES: list[tuple[re.Pattern, str, dict]] = []
MISSES: set[str] = set()  # English blocks shown with the [EN] marker in this process (read by the RO checker)
EN_MARK = "[EN] "

_KIND_RE = {
    "n": r"[-+−]?(?:\d+(?:\.\d+)?|\.\d+)",
    "i": r"\d+",
    "d": r"\d{4}-\d{2}-\d{2}",
    "t": r".+?",
    "l": r".+?",
    "s": r".+?",
    "k": r".+?",
    "m": r"[A-Z][a-z]{2,8}",
}
_PH = re.compile(r"\{(\w+)(?::([ntidlskm]))?\}")
_EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
              "November", "December"]
_MON = {m[:3]: i for i, m in enumerate(_EN_MONTHS)} | {m: i for i, m in enumerate(_EN_MONTHS)} | {"Sept": 8}


def E(en: str, ro: str):
    """Register a whole-string translation."""
    EXACT[en] = ro


def T(en: str, ro: str):
    """Register a template (see module doc)."""
    parts, kinds, pos = [], {}, 0
    for m in _PH.finditer(en):
        parts.append(re.escape(en[pos:m.start()]))
        name, kind = m.group(1), m.group(2) or "s"
        kinds[name] = kind
        parts.append(f"(?P<{name}>{_KIND_RE[kind]})")
        pos = m.end()
    parts.append(re.escape(en[pos:]))
    TEMPLATES.append((re.compile("".join(parts), re.S), ro, kinds))


# ------------------------------------------------------------------------------------------ value helpers
def ro_num(s: str) -> str:
    """Decimal comma: '12.45' -> '12,45'. Thousands separators (1,234) become dots."""
    return re.sub(r"(?<=\d)[.,](?=\d)", lambda m: "," if m.group(0) == "." else ".", s)


def ro_date(s: str) -> str:
    """'2026-11-23' -> '23 nov. 2026'."""
    y, mo, d = s.split("-")
    return f"{int(d)} {MONTHS_SHORT[int(mo) - 1]} {y}"


def ro_month(s: str) -> str:
    i = _MON.get(s)
    if i is None:
        return s
    return MONTHS[i] if len(s) > 4 else MONTHS_SHORT[i]


def ro_text_dates(s: str) -> str:
    """ISO dates and 'D Mon' dates inside free text -> Romanian."""
    s = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", lambda m: ro_date(m.group(0)), s)
    return re.sub(r"\b(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
                  lambda m: f"{m.group(1)} {MONTHS_SHORT[_MON[m.group(2)]]}", s)


def _fill(kind: str, v: str) -> str | None:
    if kind == "n":
        return ro_num(v)
    if kind in ("i", "k"):
        return v
    if kind == "d":
        return ro_date(v)
    if kind == "m":
        return ro_month(v)
    if kind == "s":
        return ro_num(v)
    out = _tr(v)
    if out is None:
        return None
    if kind == "l" and out:
        out = out[0].lower() + out[1:]
    return out


# ------------------------------------------------------------------------------------------ matching
def _template(s: str) -> str | None:
    for pat, ro, kinds in TEMPLATES:
        m = pat.fullmatch(s)
        if not m:
            continue
        vals = {}
        for name, kind in kinds.items():
            v = _fill(kind, m.group(name))
            if v is None:
                break
            vals[name] = v
        else:
            try:
                return ro.format(**vals)
            except (KeyError, IndexError, ValueError):
                continue
    return None


_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'*])")
_ABBR = re.compile(r"(?:\be\.g|\bi\.e|\bvs|\bapprox|\bca|\bcf|\bNo|\bp)\.$")


def _sentences(s: str) -> list[str]:
    out = []
    for part in _SENT.split(s):
        if out and _ABBR.search(out[-1]):
            out[-1] = f"{out[-1]} {part}"
        else:
            out.append(part)
    return out


@lru_cache(maxsize=20000)
def _tr(s: str) -> str | None:
    """Romanian for one English string, or None."""
    if s is None:
        return None
    core = s.strip()
    if not core:
        return s
    lead, trail = s[: len(s) - len(s.lstrip())], s[len(s.rstrip()):]
    if core in EXACT:
        return lead + EXACT[core] + trail
    hit = _template(core)
    if hit is not None:
        return lead + hit + trail
    if not re.search(r"[A-Za-z]{2}", core):  # numbers, units, codes only
        return lead + ro_num(core) + trail
    sents = _sentences(core)
    if len(sents) > 1:
        outs = [_tr(x) for x in sents]
        if all(o is not None for o in outs):
            return lead + " ".join(outs) + trail
        return None
    for sep in ("; ", " | "):
        if sep in core:
            outs = [_tr(x) for x in core.split(sep)]
            if all(o is not None for o in outs):
                return lead + sep.join(outs) + trail
            return None
    # a sentence ending with "." that is registered without it (or the other way round)
    if core.endswith(".") and core[:-1] in EXACT:
        return lead + EXACT[core[:-1]] + "." + trail
    if core.endswith("."):
        hit = _template(core[:-1])
        if hit is not None:
            return lead + hit + "." + trail
    return None


def tr(s, mark: bool = True):
    """Romanian for a marinekit string in RO mode (the input itself in EN). Untranslatable -> '[EN] ' + input."""
    if lang() != "ro" or not isinstance(s, str) or not s.strip():
        return s
    out = _tr(s)
    if out is not None:
        return out
    MISSES.add(s)
    return (EN_MARK + s) if mark else s


def has(s: str) -> bool:
    """True when the string has a Romanian version (for choosing between two texts)."""
    return isinstance(s, str) and _tr(s) is not None


# ------------------------------------------------------------------------------------------ markdown
def _md_cell(c: str) -> str:
    c2 = c.strip()
    if not c2 or set(c2) <= set("-:"):
        return c
    out = _tr(c2)
    if out is None:
        MISSES.add(c2)
        out = EN_MARK + c2
    return f" {out} "


def _md_par(p: str) -> str:
    lines = p.split("\n")
    if all(x.lstrip().startswith("|") for x in lines if x.strip()):
        rows = []
        for x in lines:
            cells = x.strip().strip("|").split("|")
            rows.append("|" + "|".join(_md_cell(c) for c in cells) + "|")
        return "\n".join(rows)
    if len(lines) > 1 and all(x.lstrip().startswith(("- ", "* ")) or not x.strip() for x in lines[1:]):
        return "\n".join([_md_par(lines[0])] + [x[: len(x) - len(x.lstrip())] + "- " + _md_par(x.lstrip()[2:])
                                                for x in lines[1:] if x.strip()])
    if all(x.lstrip().startswith(("- ", "* ")) for x in lines if x.strip()):
        return "\n".join("- " + _md_par(x.lstrip()[2:]) for x in lines if x.strip())
    whole = " ".join(x.strip() for x in lines)
    out = _tr(whole)
    if out is not None:
        return out
    m = re.match(r"^(\*\*[^*]+\*\*)\s*(.*)$", whole, re.S)
    if m:
        head = _tr(m.group(1).strip("*"))
        rest = _tr(m.group(2)) if m.group(2) else ""
        if head is not None and rest is not None:
            return f"**{head}** {rest}".strip()
    MISSES.add(whole)
    return EN_MARK + whole


def md(s):
    """Markdown from marinekit (paragraphs, bold leads, lists, tables) in Romanian."""
    if lang() != "ro" or not isinstance(s, str) or not s.strip():
        return s
    return "\n\n".join(_md_par(p) for p in re.split(r"\n\s*\n", s.strip()))


def load():
    """Import the template tables (they register themselves through E() and T())."""
    import importlib
    for name in ("viewer.i18n_ro_cards", "viewer.i18n_ro_data"):
        try:
            importlib.import_module(name)
        except ImportError:
            pass
