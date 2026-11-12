#!/usr/bin/env python3
"""Generate the GitHub profile README (danielmoralesc/danielmoralesc) from resume.json.

Standard library only. The output is deterministic: it depends solely on the
JSON content (``meta.lastModified`` is used instead of the current date), so the
workflow only commits when the data actually changes.

Usage:
    python scripts/generate_readme.py [--input _data/resume.json] [--output README.md] [--check]

Exit codes:
    0  README written, unchanged, or up to date (--check)
    1  README out of date (--check only)
    2  invalid or unreadable input
"""

from __future__ import annotations

import argparse
import calendar
import html
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

# Interface labels (the profile README is written in English).
LABELS = {
    "lines": "What I work on",
    "now": "Now",
    "selected": "Selected publications",
    "all_pubs": "All publications",
    "phd": "PhD candidate",
    "toolbox": "Toolbox",
    "methods": "Methods",
    "web": "Also on the web",
    "full_cv": "Full CV",
    "talks": "Talks",
    "email": "Email",
    "website": "Website",
    "et_al": "et al.",
    "footer": "Generated automatically from resume.json · last updated {date}",
}

# Brand metadata: lower-case name -> (Simple Icons slug or None, hex colour).
# LinkedIn has no logo because Simple Icons removed it.
BRANDS = {
    "orcid": ("orcid", "A6CE39"),
    "google scholar": ("googlescholar", "4285F4"),
    "scopus": ("scopus", "E9711C"),
    "researchgate": ("researchgate", "00CCBB"),
    "github": ("github", "181717"),
    "linkedin": (None, "0A66C2"),
    "email": (None, "555555"),
    "website": (None, "8E1F2F"),
    "r": ("r", "276DC3"),
    "python": ("python", "3776AB"),
    "quarto": ("quarto", "39729E"),
    "git": ("git", "F05032"),
    "latex": ("latex", "008080"),
    "zotero": ("zotero", "CC2936"),
    "obsidian": ("obsidian", "7C3AED"),
    "wordpress": ("wordpress", "21759B"),
    "php": ("php", "777BB4"),
    "vue.js": ("vuedotjs", "4FC08D"),
    "nuxt.js": ("nuxt", "00DC82"),
    "jekyll": ("jekyll", "CC0000"),
    "docker": ("docker", "2496ED"),
    "grist": (None, "16B378"),
}
DEFAULT_COLOUR = "555555"
DOI_COLOUR = "1F6FEB"
MAX_AUTHORS = 3

PARTIAL_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

def strip_doi(doi: str) -> str:
    """Remove resolver prefixes, keeping the DOI's original case."""
    doi = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            return doi[len(prefix):]
    return doi


def normalise_doi(doi: str) -> str:
    """Canonical form for comparisons (DOIs are case-insensitive)."""
    return strip_doi(doi).lower()


def validate(data: object) -> list[str]:
    """Return a list of human-readable problems; empty means valid."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["top level: expected an object"]

    meta = data.get("meta") or {}
    if not PARTIAL_DATE.match(str(meta.get("lastModified", ""))):
        errors.append("meta.lastModified: expected an ISO date such as '2026-09-15'")

    basics = data.get("basics")
    if not isinstance(basics, dict) or not str(basics.get("name", "")).strip():
        errors.append("basics.name: required")

    for key in ("affiliations", "education", "publications", "researchProjects", "funding", "skills"):
        if key in data and not isinstance(data[key], list):
            errors.append(f"{key}: expected an array")

    for key in ("affiliations", "education", "researchProjects", "funding"):
        for i, item in enumerate(data.get(key) or []):
            for field in ("startDate", "endDate"):
                value = item.get(field)
                if value is None and field == "endDate":
                    continue
                if value is not None and not PARTIAL_DATE.match(str(value)):
                    errors.append(f"{key}[{i}].{field}: expected 'YYYY', 'YYYY-MM' or null, got {value!r}")

    for key, items in data.items():
        if isinstance(items, list):
            for i, item in enumerate(items):
                if isinstance(item, dict) and item.get("placeholder"):
                    errors.append(f"{key}[{i}]: placeholder entry (example data); replace it or remove it before publishing")

    seen_dois: dict[str, int] = {}
    for i, pub in enumerate(data.get("publications") or []):
        where = f"publications[{i}]"
        if not str(pub.get("title", "")).strip():
            errors.append(f"{where}.title: required")
        if not isinstance(pub.get("year"), int):
            errors.append(f"{where}.year: expected an integer")
        authors = pub.get("authors")
        if not isinstance(authors, list) or not authors or not all(
            isinstance(a, dict) and str(a.get("name", "")).strip() for a in authors
        ):
            errors.append(f"{where}.authors: expected a non-empty array of {{name}} objects")
        if pub.get("doi"):
            doi = normalise_doi(pub["doi"])
            if doi in seen_dois:
                errors.append(f"{where}.doi: duplicates publications[{seen_dois[doi]}] ({doi})")
            seen_dois[doi] = i
    return errors


# --------------------------------------------------------------------------- #
# Markdown helpers
# --------------------------------------------------------------------------- #



def md_link(text: str, url: str) -> str:
    """[text](<url>) keeps URLs with parentheses (common in DOIs) intact."""
    text = str(text).replace("[", "\\[").replace("]", "\\]")
    url = url.replace(" ", "%20").replace("<", "%3C").replace(">", "%3E")
    return f"[{text}](<{url}>)"


def doi_url(doi: str) -> str:
    return "https://doi.org/" + strip_doi(doi)


def logo_colour(hex_colour: str) -> str:
    """Black or white logo, whichever contrasts better with the badge colour."""
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255 for i in (0, 2, 4))
    luminance = 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
    return "black" if luminance > 0.179 else "white"


def shield_escape(text: str) -> str:
    """Escape text for a shields.io static badge path segment."""
    return quote(str(text).replace("-", "--").replace("_", "__"), safe="")


def badge_url(label: str, colour: str, logo: str | None, style: str = "flat-square") -> str:
    url = f"https://img.shields.io/badge/{shield_escape(label)}-{colour}?style={style}"
    if logo:
        url += f"&logo={logo}&logoColor={logo_colour(colour)}"
    return url


def brand(name: str) -> tuple[str | None, str]:
    return BRANDS.get(name.strip().lower(), (None, DEFAULT_COLOUR))


def html_badge(label: str, link: str, style: str = "flat-square") -> str:
    logo, colour = brand(label)
    return (f'<a href="{html.escape(link)}"><img alt="{html.escape(label)}" '
            f'src="{html.escape(badge_url(label, colour, logo, style))}"></a>')


def md_badge(label: str) -> str:
    logo, colour = brand(label)
    return f"![{label}]({badge_url(label, colour, logo)})"




# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #

def format_authors(authors: list[dict]) -> str:
    """Short author list with the profile owner in bold, always shown."""
    def fmt(a: dict) -> str:
        return f"**{a['name']}**" if a.get("isSelf") else a["name"]

    if len(authors) <= MAX_AUTHORS + 1:
        names = [fmt(a) for a in authors]
        return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " & " + names[-1]

    shown = authors[:MAX_AUTHORS]
    self_author = next((a for a in authors if a.get("isSelf")), None)
    if self_author is not None and self_author not in shown:
        shown = authors[:MAX_AUTHORS - 1] + [self_author]
    return ", ".join(fmt(a) for a in shown) + f" *{LABELS['et_al']}*"




def section_header(data: dict) -> str:
    basics = data["basics"]
    current = [a for a in data.get("affiliations") or [] if a.get("endDate") is None]
    where = " · ".join(dict.fromkeys(short_org(a) for a in current))
    lines = [f'<h1 align="center">{html.escape(basics["name"])}</h1>', ""]
    tagline = f"{LABELS['phd']} · {where}" if where else ""
    if tagline:
        lines += ['<p align="center">', f"  <em>{html.escape(tagline)}</em>", "</p>", ""]
    if basics.get("headline"):
        lines += ['<p align="center">', f"  {html.escape(basics['headline'])}", "</p>", ""]

    big = "for-the-badge"
    badges = []
    if basics.get("website"):
        badges.append(html_badge(LABELS["website"], basics["website"], big))
    badges += [html_badge(p["network"], p["url"], big) for p in basics.get("profiles") or []
               if p.get("url") and p["network"].lower() != "github"]
    if basics.get("email"):
        badges.append(html_badge(LABELS["email"], "mailto:" + basics["email"], big))
    if badges:
        lines += ['<p align="center">', *("  " + b for b in badges), "</p>"]
    return "\n".join(lines)


def short_org(affiliation: dict) -> str:
    """'Institute for ... (INARBE)' -> 'INARBE'; otherwise the organisation name."""
    m = re.search(r"\(([^)]+)\)\s*$", affiliation["organization"])
    return m.group(1) if m else affiliation["organization"]


def section_lines(data: dict) -> str:
    lines_data = data["basics"].get("researchLines") or []
    if not lines_data:
        return ""
    width = f"{100 // len(lines_data)}%"
    cells = []
    for line in lines_data:
        emoji = f"{line['emoji']} " if line.get("emoji") else ""
        tags = " ".join(f"<code>{html.escape(k)}</code>" for k in line.get("keywords") or [])
        body = [f'<td width="{width}" valign="top">', "",
                f"### {emoji}{line['title']}", "", line.get("description", "")]
        if tags:
            body += ["", tags]
        body += ["", "</td>"]
        cells.append("\n".join(body))
    return "\n".join([f"## {LABELS['lines']}", "", "<table>", "<tr>", *cells, "</tr>", "</table>"])


def month_year(date: str | None) -> str:
    if not date or len(str(date)) < 7:
        return str(date or "")[:4]
    year, month = str(date)[:4], int(str(date)[5:7])
    return f"{calendar.month_abbr[month]} {year}"


def section_now(data: dict) -> str:
    items = []
    for e in data.get("education") or []:
        thesis = e.get("thesis") or {}
        if e.get("endDate") is None and (thesis.get("title") or thesis.get("topic")):
            supervisors = " and ".join(thesis.get("advisors") or [])
            sup = f" (supervised by {supervisors})" if supervisors else ""
            items.append(f"🎓 **PhD thesis** at the {e['institution']}{sup}: "
                         f"*{thesis.get('title') or thesis.get('topic')}*")
    for pub in data.get("publications") or []:
        if pub.get("status") == "forthcoming":
            url = doi_url(pub["doi"]) if pub.get("doi") else pub.get("url")
            title = pub.get("originalTitle") or pub["title"]
            title = md_link(title, url) if url else f"*{title}*"
            when = month_year(f"{pub['year']}-{pub['month']:02d}") if isinstance(pub.get("month"), int) else str(pub["year"])
            items.append(f"📄 **Forthcoming** in *{pub['venue']['name']}* ({when}): {title}")
    talks = [t for t in data.get("presentations") or [] if t.get("status") == "upcoming"]
    if talks:
        parts = [f"{short_event(t)}, {t['location'].split(',')[0]} ({month_year(t.get('date'))})" for t in talks]
        items.append("🎤 **Upcoming talks:** " + " · ".join(parts))
    if not items:
        return ""
    return "\n".join([f"## {LABELS['now']}", "", *(f"- {i}" for i in items)])


def short_event(talk: dict) -> str:
    """Acronym in brackets if the event has one (e.g. 'ESSHC'), otherwise the event name."""
    m = re.search(r"\(([A-Z][A-Za-z]{2,})\)", talk.get("event", ""))
    return m.group(1) if m else talk.get("event", "")


def section_selected(data: dict) -> str:
    # Forthcoming work is already listed under "Now".
    pubs = [p for p in data.get("publications") or [] if p.get("featured") and p.get("status") != "forthcoming"]
    if not pubs:
        return ""
    lines = [f"## {LABELS['selected']}", ""]
    for pub in pubs:
        title = pub.get("originalTitle") or pub["title"]
        url = doi_url(pub["doi"]) if pub.get("doi") else pub.get("url")
        title_md = f"**{md_link(title, url)}**" if url else f"**{title}**"
        year = str(pub["year"])
        venue = f"*{pub['venue']['name']}*" if (pub.get("venue") or {}).get("name") else ""
        meta = " · ".join(x for x in (format_authors(pub["authors"]), venue, year) if x)
        lines.append(f"- {title_md}  \n  {meta}")
    site = data["basics"].get("website")
    if site:
        lines += ["", f"→ {md_link(LABELS['all_pubs'], site.rstrip('/') + '/publications/')}"]
    return "\n".join(lines)


def section_toolbox(data: dict) -> str:
    skills = data.get("skills") or []
    tools = [k for g in skills if g.get("name") != "Research methods" for k in g.get("keywords") or []]
    methods = [k for g in skills if g.get("name") == "Research methods" for k in g.get("keywords") or []]
    if not tools and not methods:
        return ""
    lines = [f"## {LABELS['toolbox']}", ""]
    if tools:
        lines.append(" ".join(md_badge(k) for k in tools))
    if methods:
        lines += ["", f"**{LABELS['methods']}:** " + " · ".join(methods)]
    return "\n".join(lines)


def section_web(data: dict) -> str:
    web = data.get("webDevelopment") or {}
    if not web.get("summary"):
        return ""
    lines = [f"## {LABELS['web']}", "", web["summary"]]
    if web.get("keywords"):
        lines += ["", " ".join(md_badge(k) for k in web["keywords"])]
    return "\n".join(lines)


def section_footer(data: dict) -> str:
    meta = data["meta"]
    site = (data["basics"].get("website") or "").rstrip("/")
    # Inside an HTML block GitHub does not parse Markdown, so links must be <a> tags.
    def a(text: str, url: str) -> str:
        return f'<a href="{html.escape(url)}">{html.escape(text)}</a>'
    links = []
    if site:
        links += [a(LABELS["full_cv"], site + "/cv/"), a(LABELS["talks"], site + "/talks/")]
    links.append(a("resume.json", meta.get("canonicalUrl") or "resume.json"))
    return ("---\n\n<p align=\"center\"><sub>" + " · ".join(links) + "<br>"
            + LABELS["footer"].format(date=meta["lastModified"]) + "</sub></p>")


def render(data: dict) -> str:
    sections = (
        section_header, section_lines, section_now, section_selected,
        section_toolbox, section_web, section_footer,
    )
    body = "\n\n".join(s for s in (fn(data) for fn in sections) if s)
    return "<!-- Generated by scripts/generate_readme.py from resume.json. Do not edit by hand. -->\n\n" + body + "\n"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def report_error(path: str, message: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::error file={path}::{message}")
    else:
        print(f"error: {path}: {message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", default="_data/resume.json", help="path to resume.json")
    parser.add_argument("--output", default="README.md", help="README to write")
    parser.add_argument("--check", action="store_true", help="exit 1 if the README is out of date; write nothing")
    args = parser.parse_args(argv)

    try:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except FileNotFoundError:
        report_error(args.input, "file not found")
        return 2
    except json.JSONDecodeError as exc:
        report_error(args.input, f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
        return 2

    errors = validate(data)
    if errors:
        for message in errors:
            report_error(args.input, message)
        return 2

    content = render(data)
    output = Path(args.output)
    current = output.read_text(encoding="utf-8") if output.exists() else None

    if args.check:
        if current != content:
            print(f"{output} is out of date; run scripts/generate_readme.py")
            return 1
        print(f"{output} is up to date")
        return 0

    if current == content:
        print(f"{output} unchanged")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content.encode("utf-8"))
    print(f"{output} written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
