// Curriculum vitae in PDF, built from _data/resume.json (the same data as the website).
// Build from the repository root:
//   quarto typst compile --root . cv/cv.typ files/cv.pdf
// The Pages workflow (.github/workflows/pages.yml) runs this on every push to master.
// Edit the JSON, not this file, to change content.

#let data = json("/_data/resume.json")
#let b = data.basics
#let accent = rgb("#8E1F2F")
#let muted = luma(85)

// ---------------------------------------------------------------- helpers

#let get(d, key) = d.at(key, default: none)
#let months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
#let year(s) = if s == none { "" } else { str(s).slice(0, 4) }
#let span(s, e) = {
  let a = year(s)
  let z = if e == none { "present" } else { year(e) }
  if a == "" { z } else if a == z { a } else { a + "–" + z }
}
#let month-year(d) = {
  let s = str(d)
  if s.len() >= 7 { months.at(int(s.slice(5, 7)) - 1) + " " + s.slice(0, 4) } else { s.slice(0, 4) }
}
#let day-month-year(d) = {
  let s = str(d)
  if s.len() >= 10 { str(int(s.slice(8, 10))) + " " + month-year(s) } else { month-year(s) }
}
#let join-and(items) = {
  if items.len() == 0 { [] } else if items.len() == 1 { items.at(0) } else {
    items.slice(0, -1).join(", ") + [ & ] + items.last()
  }
}

// Original-language title first; English translation in brackets when it differs.
#let titled(item, url: none) = {
  let original = get(item, "originalTitle")
  let main = if original != none { original } else { item.title }
  if url != none { link(url, main) } else { main }
  if original != none and original != item.title { [ #text(fill: muted, emph("[" + item.title + "]"))] }
}

// ---------------------------------------------------------------- page

#set document(title: b.name + " — Curriculum Vitae", author: b.name)
#set text(font: "Libertinus Serif", size: 10.5pt, lang: "en", region: "gb")
#set par(justify: true, leading: 0.58em, spacing: 0.9em)
#set page(
  paper: "a4",
  margin: (x: 2.1cm, top: 2cm, bottom: 2.2cm),
  footer: context {
    set text(8.5pt, fill: muted)
    [#b.name — Curriculum Vitae · last updated #day-month-year(data.meta.lastModified) #h(1fr) #counter(page).display("1 / 1", both: true)]
  },
)
#show link: set text(fill: accent)

#let section(title) = {
  v(0.6em)
  block(below: 0.7em, sticky: true)[
    #text(12.5pt, weight: "bold", fill: accent, smallcaps(title))
    #v(-0.55em)
    #line(length: 100%, stroke: 0.5pt + accent)
  ]
}
#let subhead(title) = block(above: 0.8em, below: 0.5em, sticky: true, text(10.5pt, style: "italic", fill: muted, title))

// Title on the left (wraps), date in its own column on the right.
#let entry(title, date, sub: none, body: none) = block(below: 0.75em, breakable: false)[
  #set par(justify: false)
  #grid(columns: (1fr, auto), column-gutter: 1.2em, strong(title), text(fill: muted, date))
  #if sub != none { v(-0.45em); sub }
  #if body != none { v(-0.45em); text(9.8pt, body) }
]

// ---------------------------------------------------------------- header

#align(center)[
  #text(24pt, weight: "bold", b.name)
  #v(-0.6em)
  #text(11.5pt, fill: muted, b.label)
  #v(-0.2em)
  #text(9.5pt)[
    #let loc = (b.location.city, b.location.region).filter(x => x != none).join(", ")
    #loc
    #h(0.5em)·#h(0.5em) #link("mailto:" + b.email, b.email)
    #h(0.5em)·#h(0.5em) #link(b.website, b.website.replace("https://", ""))
    #for p in b.profiles [ #h(0.5em)·#h(0.5em) #link(p.url, p.network)]
  ]
]

#v(0.3em)
#align(center, block(width: 88%, text(10pt, style: "italic", b.headline)))

// ---------------------------------------------------------------- profile

#if get(b, "summary") != none {
  section("Profile")
  b.summary
  let interests = get(b, "researchInterests")
  if interests != none and interests.len() > 0 {
    v(0.2em)
    text(9.8pt)[*Research interests:* #interests.join(" · ")]
  }
}

// ---------------------------------------------------------------- positions

#if data.affiliations.len() > 0 {
  section("Positions")
  for a in data.affiliations {
    let org = if get(a, "url") != none { link(a.url, a.organization) } else { a.organization }
    let sub = [#org#if get(a, "department") != none [, #a.department]#if get(a, "location") != none [ · #a.location]]
    entry(a.role, span(a.startDate, a.endDate), sub: sub, body: get(a, "description"))
  }
}

// ---------------------------------------------------------------- education

#if data.education.len() > 0 {
  section("Education")
  for e in data.education {
    let org = if get(e, "url") != none { link(e.url, e.institution) } else { e.institution }
    let t = get(e, "thesis")
    let body = if t != none {
      let thesis = if get(t, "title") != none { emph(titled(t)) } else { get(t, "topic") }
      let adv = get(t, "advisors")
      [Thesis: #thesis#if adv != none and adv.len() > 0 [. #if adv.len() > 1 [Supervisors] else [Supervisor]: #adv.join(" and ")]]
    }
    entry(e.degree, span(e.startDate, e.endDate), sub: org, body: body)
  }
}

// ---------------------------------------------------------------- publications

#let citation(p) = {
  let url = if get(p, "doi") != none { "https://doi.org/" + p.doi } else { get(p, "url") }
  let names = p.authors.map(a => if get(a, "isSelf") == true { strong(a.name) } else { [#a.name] })
  let when = if get(p, "status") == "forthcoming" {
    "forthcoming" + if get(p, "month") != none { ", " + month-year(str(p.year) + "-" + str(p.month + 100).slice(1)) } else { "" }
  } else { str(p.year) }
  let v = p.venue
  [#join-and(names) (#when). #titled(p, url: url). #emph(v.name)]
  if get(v, "volume") != none { [, #v.volume] }
  if get(v, "issue") != none { [(#v.issue)] }
  if get(v, "pages") != none { [, #v.pages.replace("-", "–")] } else if get(v, "articleNumber") != none { [, #v.articleNumber] }
  [.]
  if get(p, "doi") != none { [ #link(url)[doi:#p.doi]] }
}

#if data.publications.len() > 0 {
  section("Publications")
  set par(hanging-indent: 1.2em, justify: false)
  let forthcoming = data.publications.filter(p => get(p, "status") == "forthcoming")
  let published = data.publications.filter(p => get(p, "status") != "forthcoming")
  if forthcoming.len() > 0 {
    subhead("Forthcoming")
    for p in forthcoming { block(below: 0.6em, citation(p)) }
  }
  if published.len() > 0 {
    subhead("Journal articles")
    for p in published { block(below: 0.6em, citation(p)) }
  }
}

// ---------------------------------------------------------------- presentations

#if data.presentations.len() > 0 {
  section("Presentations")
  for t in data.presentations {
    let when = if str(t.date).len() >= 10 { day-month-year(t.date) } else { month-year(t.date) }
    let title = [#if get(t, "originalTitle") != none { t.originalTitle } else { t.title }#if get(t, "status") == "upcoming" [ #text(8pt, fill: accent, weight: "bold", smallcaps("upcoming"))]]
    let event = if get(t, "eventUrl") != none { link(t.eventUrl, t.event) } else { t.event }
    let translation = if get(t, "originalTitle") != none and t.originalTitle != t.title { [#text(fill: muted, emph("[" + t.title + "]")) \ ] }
    entry(title, when, sub: [#translation#event#if get(t, "location") != none [ · #t.location]])
  }
}

// ---------------------------------------------------------------- research projects

#if data.researchProjects.len() > 0 {
  section("Research projects")
  for p in data.researchProjects {
    let parts = ()
    if get(p, "programme") != none { parts.push(p.programme) }
    if get(p, "code") != none and get(p, "title") != none { parts.push(p.code) }
    let funder = if get(p, "funder") != none { p.funder } else { get(p, "institution") }
    let sub = [#p.role#if parts.len() > 0 [ · #parts.join(" ")]#if funder != none [ · #funder]]
    entry(if get(p, "title") != none { p.title } else { p.code }, span(p.startDate, p.endDate), sub: sub)
  }
}

// ---------------------------------------------------------------- funding

#if data.funding.len() > 0 {
  section("Grants and funding")
  for f in data.funding {
    entry(f.title, span(f.startDate, f.endDate), sub: [#f.funder#if get(f, "grantNumber") != none [ · #f.grantNumber]])
  }
}

// ---------------------------------------------------------------- teaching

#let teaching-item(t) = {
  let parts = (t.role,)
  let place = if get(t, "programme") != none { t.programme + ", " + t.institution } else { t.institution }
  parts.push(place)
  let n = get(t, "semesters")
  if n != none and n > 1 { parts.push(str(n) + " semesters") }
  entry(t.course, span(t.startDate, t.endDate), sub: parts.join(" · "), body: get(t, "description"))
}

#if data.teaching.len() > 0 {
  section("Teaching")
  let lecturer = data.teaching.filter(t => get(t, "type") == "lecturer")
  let assistant = data.teaching.filter(t => get(t, "type") == "assistant")
  if lecturer.len() > 0 { subhead("Lecturer"); for t in lecturer { teaching-item(t) } }
  if assistant.len() > 0 { subhead("Teaching assistant"); for t in assistant { teaching-item(t) } }
}

// ---------------------------------------------------------------- media

#if get(data, "press") != none and data.press.len() > 0 {
  section("Media coverage")
  for m in data.press {
    let title = if get(m, "url") != none { link(m.url, m.title) } else { m.title }
    entry(title, day-month-year(m.date), sub: [#emph(m.outlet)#if get(m, "section") != none [ (#m.section)]])
  }
}

// ---------------------------------------------------------------- skills

#if data.skills.len() > 0 {
  section("Skills")
  for s in data.skills {
    block(below: 0.45em)[*#s.name:* #s.keywords.join(" · ")]
  }
}
