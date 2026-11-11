"""Problem 6 defenses that run in code, before and after the model.

CODE layer   read_visible(): keep only the text a person would see in a browser,
             PDF viewer, or email app. Everything removed is reported.
DESIGN layer decide(): the purchasing checks run in Python from the handbook tables,
             and ground(): every extracted fact must appear in the visible text.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import ContentStream

ROOT = Path(__file__).resolve().parent
HANDBOOK = ROOT / "data" / "shop_handbook.md"

ZERO_WIDTH = re.compile(r"[​-‏‪-‮⁠-⁤﻿­]")
MIN_FONT_PT = 4.0     # smaller than this is not readable on screen or paper
NEAR_WHITE = 235      # all of R, G, B at or above this on a white page = invisible


@dataclass
class Cleaned:
    text: str
    removed: list[dict] = field(default_factory=list)   # [{"why": ..., "text": ...}]
    flags: list[str] = field(default_factory=list)       # suspicious visible text


def _clean_str(s: str) -> str:
    return ZERO_WIDTH.sub("", unicodedata.normalize("NFKC", s))


def _short(s: str, n: int = 200) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n] + "..."


# ---------------------------------------------------------------- HTML

_BLOCK = {"tr", "p", "br", "div", "li", "h1", "h2", "h3", "h4", "header", "footer", "table", "section"}
_VOID = {"br", "img", "hr", "meta", "link", "input", "wbr", "col", "area", "base", "source"}


def _parse_color(v: str):
    v = v.strip().lower()
    names = {"white": (255, 255, 255), "transparent": (255, 255, 255), "snow": (255, 250, 250),
             "ivory": (255, 255, 240), "whitesmoke": (245, 245, 245)}
    if v in names:
        return names[v]
    m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", v)
    if m:
        h = m.group(1)
        h = "".join(c * 2 for c in h) if len(h) == 3 else h
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = re.match(r"rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)(?:[,\s/]+([\d.]+))?", v)
    if m:
        if m.group(4) is not None and float(m.group(4)) < 0.1:
            return (255, 255, 255)  # see-through text
        return tuple(int(m.group(i)) for i in (1, 2, 3))
    return None


def _size_px(v: str):
    m = re.match(r"\s*([\d.]+)\s*(px|pt|em|rem|%)?", v)
    if not m:
        return None
    n, unit = float(m.group(1)), (m.group(2) or "px")
    return {"px": n, "pt": n * 4 / 3, "em": n * 16, "rem": n * 16, "%": n * 0.16}[unit]


def _hidden_reason(style: str) -> str | None:
    """Why an inline style hides its text from a person, or None."""
    decl = {}
    for part in style.split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            decl[k.strip().lower()] = v.strip().lower()
    if decl.get("display") == "none":
        return "display:none"
    if decl.get("visibility") in ("hidden", "collapse"):
        return "visibility:hidden"
    if "opacity" in decl:
        try:
            if float(decl["opacity"]) < 0.1:
                return "opacity:0"
        except ValueError:
            pass
    if "font-size" in decl:
        px = _size_px(decl["font-size"])
        if px is not None and px < MIN_FONT_PT * 4 / 3:
            return f"font-size:{decl['font-size']}"
    if "color" in decl:
        c = _parse_color(decl["color"])
        if c and min(c) >= NEAR_WHITE:
            return f"white text ({decl['color']})"
    for k in ("height", "max-height", "width", "max-width"):
        if k in decl and _size_px(decl[k]) == 0 and "hidden" in decl.get("overflow", ""):
            return f"{k}:0 with overflow hidden"
    for k in ("left", "top", "text-indent", "margin-left"):
        if k in decl and re.match(r"\s*-\s*\d{3,}", decl[k]):
            return f"moved off screen ({k}:{decl[k]})"
    if "clip" in decl and "rect(0" in decl["clip"].replace(" ", ""):
        return "clip:rect(0)"
    if re.search(r"scale\(\s*0(\.0+)?\s*\)", decl.get("transform", "")):
        return "transform:scale(0)"
    return None


class _VisibleHTML(HTMLParser):
    """Rebuilds the text a browser shows. Hidden elements, comments, scripts and
    styles are dropped and recorded. Simple class/id rules in <style> blocks count."""

    def __init__(self, css_rules: dict[str, str]):
        super().__init__(convert_charrefs=True)
        self.css = css_rules
        self.stack: list[tuple[str, str | None]] = []   # (tag, hidden reason)
        self.out: list[str] = []
        self.removed: list[dict] = []
        self._hidden_buf: dict[int, list[str]] = {}

    def _hidden_now(self):
        for i, (_, why) in enumerate(self.stack):
            if why:
                return i, why
        return None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        why = None
        if tag in ("script", "style", "template", "noscript", "head", "title"):
            why = f"<{tag}>"
        elif "hidden" in a:
            why = "hidden attribute"
        else:
            style = a.get("style") or ""
            for cls in (a.get("class") or "").split():
                style += ";" + self.css.get("." + cls, "")
            if a.get("id"):
                style += ";" + self.css.get("#" + a["id"], "")
            style += ";" + self.css.get(tag, "")
            why = _hidden_reason(style)
        if tag in _VOID:
            if tag == "br":
                self.out.append("\n")
            return
        self.stack.append((tag, why))
        if why:
            self._hidden_buf.setdefault(len(self.stack) - 1, [])
        if tag in _BLOCK and not self._hidden_now()[1]:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in _VOID:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for j in range(len(self.stack) - 1, i - 1, -1):
                    buf = self._hidden_buf.pop(j, None)
                    why = self.stack[j][1]
                    if buf is not None and why not in ("<style>", "<head>", "<title>"):
                        text = "".join(buf).strip()
                        if text:
                            self.removed.append({"why": why, "text": _short(text)})
                del self.stack[i:]
                break
        if tag in ("td", "th") and not self._hidden_now()[1]:
            self.out.append(" | ")

    def handle_data(self, data):
        idx, why = self._hidden_now()
        if why:
            self._hidden_buf[idx].append(data)
        else:
            self.out.append(data)

    def handle_comment(self, data):
        if data.strip():
            self.removed.append({"why": "HTML comment", "text": _short(data)})


def _css_rules(html: str) -> dict[str, str]:
    rules = {}
    for block in re.findall(r"<style[^>]*>(.*?)</style>", html, re.S | re.I):
        for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", block):
            for s in sel.split(","):
                s = s.strip()
                if re.fullmatch(r"[.#]?[\w-]+", s):
                    rules[s] = rules.get(s, "") + ";" + body
    return rules


def visible_html(html: str) -> Cleaned:
    html = _clean_str(html)
    p = _VisibleHTML(_css_rules(html))
    p.feed(html)
    lines = (" ".join(line.split()) for line in "".join(p.out).splitlines())
    return Cleaned("\n".join(line for line in lines if line), p.removed)


# ---------------------------------------------------------------- PDF

def _pdf_string(operand) -> str:
    if isinstance(operand, bytes):
        return operand.decode("latin-1")
    return str(operand)


def visible_pdf(path: Path) -> Cleaned:
    """Walk each page's drawing commands and keep only text a viewer would show:
    on the page, at least MIN_FONT_PT tall, not white, not render mode 3 (invisible)."""
    reader = PdfReader(path)
    kept, removed = [], []
    for page in reader.pages:
        box = page.mediabox
        x0, y0, x1, y1 = float(box.left), float(box.bottom), float(box.right), float(box.top)
        ops = ContentStream(page.get_contents(), reader).operations
        fill = (0.0, 0.0, 0.0)
        size, render, tm, leading = 12.0, 0, [1, 0, 0, 1, 0, 0], 0.0
        line = [1, 0, 0, 1, 0, 0]
        stack = []
        for operands, op in ops:
            op = op.decode() if isinstance(op, bytes) else op
            if op == "q":
                stack.append((fill, size, render))
            elif op == "Q" and stack:
                fill, size, render = stack.pop()
            elif op == "rg" and len(operands) == 3:
                fill = tuple(float(v) for v in operands)
            elif op == "g" and operands:
                fill = (float(operands[0]),) * 3
            elif op == "k" and len(operands) == 4:
                c, m, y, k = (float(v) for v in operands)
                fill = tuple((1 - min(1, v + k)) for v in (c, m, y))
            elif op == "Tf" and len(operands) == 2:
                size = float(operands[1])
            elif op == "TL" and operands:
                leading = float(operands[0])
            elif op == "Tr" and operands:
                render = int(operands[0])
            elif op == "BT":
                tm, line = [1, 0, 0, 1, 0, 0], [1, 0, 0, 1, 0, 0]
            elif op == "Tm" and len(operands) == 6:
                tm = [float(v) for v in operands]
                line = tm[:]
            elif op in ("Td", "TD") and len(operands) == 2:
                line[4] += float(operands[0]) * line[0]
                line[5] += float(operands[1]) * line[3]
                tm = line[:]
            elif op == "T*":
                line[5] -= leading
                tm = line[:]
            elif op in ("Tj", "TJ", "'", '"'):
                if op == "TJ":
                    text = "".join(_pdf_string(x) for x in operands[0] if not isinstance(x, (int, float)))
                else:
                    text = _pdf_string(operands[-1])
                text = _clean_str(text)
                if not text.strip():
                    continue
                eff = size * abs(tm[3] or tm[0] or 1)
                x, y = tm[4], tm[5]
                why = None
                if render == 3:
                    why = "invisible render mode"
                elif eff < MIN_FONT_PT:
                    why = f"{eff:g}-point text"
                elif min(fill) * 255 >= NEAR_WHITE:
                    why = "white text"
                elif not (x0 - 1 <= x <= x1 and y0 - 1 <= y <= y1):
                    why = f"off the page (x={x:g}, y={y:g})"
                if why:
                    removed.append({"why": why, "text": _short(text)})
                else:
                    kept.append(text)
    if not kept and not removed:   # fonts we cannot decode: fall back, flag it
        text = "\n".join(p.extract_text() or "" for p in reader.pages)
        return Cleaned(_clean_str(text), [], ["PDF text could not be checked for hidden content"])
    return Cleaned("\n".join(kept), removed)


# ---------------------------------------------------------------- email

def visible_eml(path: Path) -> Cleaned:
    """An email app shows the HTML part when there is one, so that is what we read,
    through the same visible-HTML filter. Attachments are not read."""
    msg = BytesParser(policy=policy.default).parse(path.open("rb"))
    head = "\n".join(f"{k}: {_clean_str(str(msg[k]))}" for k in ("From", "To", "Subject", "Date") if msg[k])
    html_part = msg.get_body(preferencelist=("html",))
    plain_part = msg.get_body(preferencelist=("plain",))
    flags = []
    if html_part is not None:
        c = visible_html(html_part.get_content())
        body, removed = c.text, c.removed
        if plain_part is not None:
            removed.append({"why": "plain-text part not shown by email apps (HTML part used)",
                            "text": _short(plain_part.get_content())})
    elif plain_part is not None:
        body, removed = _clean_str(plain_part.get_content()), []
    else:
        body, removed = "", []
    attachments = [p.get_filename() for p in msg.iter_attachments()]
    if attachments:
        flags.append(f"attachments not read: {attachments}")
    return Cleaned(f"{head}\n\n{body}".strip(), removed, flags)


# ---------------------------------------------------------------- entry point

SUSPICIOUS = [
    (r"https?://\S+|www\.\S+", "link"),
    (r"(?i)\b(ignore|disregard)\b.{0,40}\b(instruction|previous|above|rules)", "asks to ignore instructions"),
    (r"(?i)send_email|approve_payment|\btool\b", "names an agent tool"),
    (r"(?i)\b(AI|assistant|agent|language model|LLM)\b", "talks to the AI"),
    (r"(?i)\b(replaces?|supersedes?|overrides?)\b.{0,60}\b(price|lead time|above|shown)", "claims to replace a stated value"),
]


def read_visible(path: Path) -> Cleaned:
    suffix = path.suffix.lower()
    if suffix in (".html", ".htm"):
        c = visible_html(path.read_text(encoding="utf-8", errors="replace"))
    elif suffix == ".pdf":
        c = visible_pdf(path)
    elif suffix == ".eml":
        c = visible_eml(path)
    else:
        raise ValueError(f"unsupported file type {suffix}")
    for pattern, label in SUSPICIOUS:
        m = re.search(pattern, c.text)
        if m:
            c.flags.append(f"{label}: {_short(m.group(0), 80)!r}")
    return c


# ---------------------------------------------------------------- design layer: rules in code

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _table_rows(section: str) -> list[list[str]]:
    rows = []
    for line in section.splitlines():
        if line.startswith("|") and not re.match(r"\|\s*-", line):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows[1:]  # drop header


def load_rules() -> dict:
    hb = HANDBOOK.read_text(encoding="utf-8")
    sections = dict(re.findall(r"^## (\d+)\. [^\n]*\n(.*?)(?=^## \d+\.|\Z)", hb, re.S | re.M))
    approved = {r[1] for r in _table_rows(sections["5"])}
    removed = {r[0]: r[1] for r in _table_rows(sections["6"])}
    catalogue = {r[0]: float(r[4].lstrip("$")) for r in _table_rows(sections["9"])}
    m = re.search(r"lead time is (\d+) days or less", sections["4"])
    n = re.search(r"minimum order is (\d+) units or less", sections["4"])
    return {"approved": approved, "removed": removed, "max_cost": catalogue,
            "max_lead": int(m.group(1)), "max_moq": int(n.group(1))}


RULES = load_rules()


def _match_vendor(name: str | None, names) -> str | None:
    if not name:
        return None
    n = _norm(name)
    for v in names:
        nv = _norm(v)
        if nv == n or (len(n) > 4 and (nv in n or n in nv)):
            return v
    return None


def ground(facts: dict, visible_text: str) -> tuple[dict, list[str]]:
    """Blank out any extracted value that does not appear in the visible text."""
    # "1,000 units" / "$1,250.00" -> 1000 / 1250.00, so real numbers with thousands
    # separators match (Problem 7 found this blanking a real 1,000-unit minimum).
    txt = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", visible_text)
    flat = _norm(visible_text)
    out, notes = dict(facts), []
    if out.get("vendor") and _norm(out["vendor"]) not in flat:
        notes.append(f"vendor {out['vendor']!r} not in visible text"); out["vendor"] = None
    if out.get("sku") and out["sku"].upper() not in txt.upper():
        notes.append(f"sku {out['sku']!r} not in visible text"); out["sku"] = None
    p = out.get("unit_price")
    if p is not None and not re.search(rf"\$?\s*{p:.2f}\b|\${p:g}\b", txt):
        notes.append(f"unit_price {p} not in visible text"); out["unit_price"] = None
    for k in ("lead_time_days", "min_order"):
        v = out.get(k)
        if v is not None and not re.search(rf"(?<![\d.]){v}(?![\d.])", txt):
            notes.append(f"{k} {v} not in visible text"); out[k] = None
    return out, notes


def decide(f: dict) -> tuple[str, str]:
    """The four handbook purchasing checks, in order. Returns (decision, reason)."""
    r = RULES
    vendor = f.get("vendor")
    if _match_vendor(vendor, r["removed"]):
        return "do_not_recommend", (f"Approved vendor check fails: {vendor} is on the removed or pending "
                                    f"vendor list in handbook section 6.")
    if not _match_vendor(vendor, r["approved"]):
        return "do_not_recommend", (f"Approved vendor check fails: {vendor or 'the vendor'} is "
                                    f"{'unknown' if not vendor else 'not on the approved vendor list'}.")
    sku, price = f.get("sku"), f.get("unit_price")
    if sku not in r["max_cost"] or price is None:
        return "do_not_recommend", ("Price check fails: the " + ("SKU is not in the catalogue"
                                    if sku not in r["max_cost"] else "unit price is unknown") + ".")
    cap = r["max_cost"][sku]
    if price > cap:
        return "do_not_recommend", (f"Price check fails: ${price:.2f} is above the ${cap:.2f} max unit "
                                    f"cost for {sku}.")
    lead = f.get("lead_time_days")
    if lead is None or lead > r["max_lead"]:
        return "do_not_recommend", ("Lead time check fails: " + ("lead time is unknown." if lead is None
                                    else f"{lead} days is over the {r['max_lead']}-day limit."))
    moq = f.get("min_order")
    if moq is None or moq > r["max_moq"]:
        return "do_not_recommend", ("Minimum order check fails: " + ("minimum order is unknown." if moq is None
                                    else f"{moq} units is over the {r['max_moq']}-unit limit."))
    return "recommend", (f"All four purchasing checks pass: approved vendor, ${price:.2f} is at or below the "
                         f"${cap:.2f} max for {sku}, {lead}-day lead time, and {moq}-unit minimum order.")
