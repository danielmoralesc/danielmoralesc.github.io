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
import html
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

# Interface labels (the profile README is written in English).
LABELS = {
    "about": "About me",
    "interests": "Research interests",
    "current": "Current position",
    "supervisors": "PhD supervisors",
    "stack": "Skills and tools",
    "publications": "Publications",
    "year": "Year",
    "publication": "Publication",
    "link": "Link",
    "projects": "Research projects",
    "years": "Years",
    "project": "Project",
    "role": "Role",
    "funding_col": "Funding",
    "career": "Career",
    "education": "Education",
    "thesis": "Thesis",
    "funding": "Grants and funding",
    "present": "present",
    "since": "since",
    "email": "Email",
    "website": "Website",
    "et_al": "et al.",
    "footer": "Generated automatically from [resume.json]({url}) · last updated {date}",
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
    "website": (None, "555555"),
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

def cell(text: str) -> str:
    """Make text safe inside a Markdown table cell."""
    return str(text).replace("\n", " ").replace("|", "\\|")


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


def badge_url(label: str, colour: str, logo: str | None) -> str:
    url = f"https://img.shields.io/badge/{shield_escape(label)}-{colour}?style=flat-square"
    if logo:
        url += f"&logo={logo}&logoColor={logo_colour(colour)}"
    return url


def brand(name: str) -> tuple[str | None, str]:
    return BRANDS.get(name.strip().lower(), (None, DEFAULT_COLOUR))


def html_badge(label: str, link: str) -> str:
    logo, colour = brand(label)
    return (f'<a href="{html.escape(link)}"><img alt="{html.escape(label)}" '
            f'src="{html.escape(badge_url(label, colour, logo))}"></a>')


def md_badge(label: str) -> str:
    logo, colour = brand(label)
    return f"![{label}]({badge_url(label, colour, logo)})"


def year_range(start: str | None, end: str | None) -> str:
    s = str(start)[:4] if start else ""
    e = str(end)[:4] if end else LABELS["present"]
    if not s:
        return e
    return s if s == e else f"{s}–{e}"


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


def format_venue(venue: dict | None) -> str:
    if not venue or not venue.get("name"):
        return ""
    out = f"*{venue['name']}*"
    if venue.get("volume"):
        out += f" {venue['volume']}"
        if venue.get("issue"):
            out += f"({venue['issue']})"
    if venue.get("pages"):
        out += f", {str(venue['pages']).replace('-', '–')}"
    elif venue.get("articleNumber"):
        out += f", {venue['articleNumber']}"
    return out


def section_header(data: dict) -> str:
    basics = data["basics"]
    lines = [f'<h1 align="center">{html.escape(basics["name"])}</h1>', ""]
    intro = []
    if basics.get("label"):
        intro.append(f"<strong>{html.escape(basics['label'])}</strong>")
    if basics.get("headline"):
        intro.append(html.escape(basics["headline"]))
    if intro:
        lines += ['<p align="center">', "  " + "<br>\n  ".join(intro), "</p>", ""]

    badges = [html_badge(p["network"], p["url"]) for p in basics.get("profiles") or [] if p.get("url")]
    if basics.get("website"):
        badges.append(html_badge(LABELS["website"], basics["website"]))
    if basics.get("email"):
        badges.append(html_badge(LABELS["email"], "mailto:" + basics["email"]))
    if badges:
        lines += ['<p align="center">', *("  " + b for b in badges), "</p>"]
    return "\n".join(lines)


def section_about(data: dict) -> str:
    basics = data["basics"]
    if not basics.get("summary") and not basics.get("researchInterests"):
        return ""
    parts = [f"## {LABELS['about']}"]
    if basics.get("summary"):
        parts.append(basics["summary"])
    if basics.get("researchInterests"):
        parts.append(f"**{LABELS['interests']}:** " + " · ".join(basics["researchInterests"]))
    return "\n\n".join(parts)


def section_current(data: dict) -> str:
    current = [a for a in data.get("affiliations") or [] if a.get("endDate") is None]
    if not current:
        return ""
    lines = [f"## {LABELS['current']}", ""]
    for a in current:
        org = md_link(a["organization"], a["url"]) if a.get("url") else a["organization"]
        dept = f", {a['department']}" if a.get("department") else ""
        since = f" ({LABELS['since']} {str(a['startDate'])[:4]})" if a.get("startDate") else ""
        lines.append(f"- **{a['role']}** · {org}{dept}{since}")
        if a.get("description"):
            lines.append(f"  <br>{a['description']}")
    supervisors = data["basics"].get("supervisors") or []
    if supervisors:
        names = " and ".join(s["name"] for s in supervisors)
        lines += ["", f"{LABELS['supervisors']}: {names}."]
    return "\n".join(lines)


def section_stack(data: dict) -> str:
    skills = data.get("skills") or []
    if not skills:
        return ""
    lines = [f"## {LABELS['stack']}", ""]
    for group in skills:
        badges = " ".join(md_badge(k) for k in group.get("keywords") or [])
        lines.append(f"**{group['name']}**  ")
        lines.append(badges)
        lines.append("")
    return "\n".join(lines).rstrip()


def section_publications(data: dict) -> str:
    pubs = data.get("publications") or []
    if not pubs:
        return ""
    lines = [
        f"## {LABELS['publications']}",
        "",
        f"| {LABELS['year']} | {LABELS['publication']} | {LABELS['link']} |",
        "|:---:|---|:---:|",
    ]
    for pub in pubs:
        # Original-language title first; English translation in brackets when it differs.
        title = pub.get("originalTitle") or pub["title"]
        translation = pub["title"] if pub.get("originalTitle") and pub["title"] != pub["originalTitle"] else None
        if pub.get("doi"):
            url = doi_url(pub["doi"])
        else:
            url = pub.get("url")
        title_md = md_link(title, url) if url else title
        if translation:
            title_md += f" [{translation}]"
        details = [title_md, format_authors(pub["authors"])]
        venue = format_venue(pub.get("venue"))
        if venue:
            details.append(venue)
        link = ""
        if pub.get("doi"):
            link = f"[![DOI]({badge_url('DOI', DOI_COLOUR, None)})](<{doi_url(pub['doi'])}>)"
        lines.append(f"| {pub['year']} | {cell('<br>'.join(details))} | {link} |")
    return "\n".join(lines)


def section_projects(data: dict) -> str:
    projects = data.get("researchProjects") or []
    if not projects:
        return ""
    lines = [
        f"## {LABELS['projects']}",
        "",
        f"| {LABELS['years']} | {LABELS['project']} | {LABELS['role']} | {LABELS['funding_col']} |",
        "|:---:|---|---|---|",
    ]
    for p in projects:
        funding = " ".join(x for x in (p.get("programme"), p.get("code") if p.get("title") else None) if x)
        funder = p.get("funder") or p.get("institution")
        if funder:
            funding = f"{funding} · {funder}" if funding else funder
        lines.append(
            f"| {year_range(p.get('startDate'), p.get('endDate'))} "
            f"| {cell(p.get('title') or p.get('code') or '')} "
            f"| {cell(p.get('role') or '')} "
            f"| {cell(funding)} |"
        )
    return "\n".join(lines)


def section_career(data: dict) -> str:
    items = data.get("affiliations") or []
    if not items:
        return ""
    lines = [f"## {LABELS['career']}", ""]
    for a in items:
        dept = f", {a['department']}" if a.get("department") else ""
        lines.append(f"- **{a['role']}**, {a['organization']}{dept} — {year_range(a.get('startDate'), a.get('endDate'))}")
    return "\n".join(lines)


def section_education(data: dict) -> str:
    items = data.get("education") or []
    if not items:
        return ""
    lines = [f"## {LABELS['education']}", ""]
    for e in items:
        lines.append(f"- **{e['degree']}**, {e['institution']} — {year_range(e.get('startDate'), e.get('endDate'))}")
        thesis = e.get("thesis") or {}
        topic = thesis.get("title") or thesis.get("topic")
        if topic:
            lines.append(f"  <br>{LABELS['thesis']}: *{topic}*")
    return "\n".join(lines)


def section_funding(data: dict) -> str:
    items = data.get("funding") or []
    if not items:
        return ""
    lines = [f"## {LABELS['funding']}", ""]
    for f in items:
        number = f" ({f['grantNumber']})" if f.get("grantNumber") else ""
        lines.append(f"- **{f['title']}**{number}, {f['funder']} — {year_range(f.get('startDate'), f.get('endDate'))}")
    return "\n".join(lines)


def section_footer(data: dict) -> str:
    meta = data["meta"]
    url = meta.get("canonicalUrl") or "resume.json"
    return "---\n\n<sub>" + LABELS["footer"].format(url=url, date=meta["lastModified"]) + "</sub>"


def render(data: dict) -> str:
    sections = (
        section_header, section_about, section_current, section_stack,
        section_publications, section_projects, section_career,
        section_education, section_funding, section_footer,
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
