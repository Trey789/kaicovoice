#!/usr/bin/env python3
"""Stamp src/pages/**/*.html into deployable HTML with one shared head, nav and footer.
Zero dependencies. `python3 build.py` writes the site and exits 1 on any check failure.
Spec: vault schema/specs/2026-09-07-kaicovoice-site-design.md, section 7."""
import datetime
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SITE = "https://www.kaicovoice.com"
GA4_ID = ""  # "G-XXXXXXXXXX" once Trey creates the property (spec 11.1); empty means no snippet
TITLE_MAX = 61
BANNED = [r"trey@kaicovoice\.com",  # mailbox lapsed 2026-08-08; the operator inbox is trey.kaico@gmail.com
          r"\$250", r"\bcancel anytime\b", r"\bno contract\b", r"\bsample data\b", "—", "–"]
STATIC = {"/robots.txt", "/sitemap.xml", "/llms.txt"}
GA4_SNIPPET = ('<script async src="https://www.googletagmanager.com/gtag/js?id={id}"></script>'
               '<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}'
               'gtag("js",new Date());gtag("config","{id}");</script>')


def read(p):
    return p.read_text(encoding="utf-8")


def parse(path):
    """Return (meta dict, body) from a page whose first thing is a <!-- meta ... --> block."""
    text = read(path)
    m = re.match(r"\s*<!--\s*meta\n(.*?)\n-->\s*", text, re.S)
    if not m:
        return None, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def lastmod(root, path):
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(path)],
                             capture_output=True, text=True, cwd=root).stdout.strip()
        if out:
            return out
    except Exception:
        pass
    return datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()


def render(root, meta, body, partials, lang="en"):
    c = meta["canonical"]
    org = "organization.es.json" if lang == "es" else "organization.json"
    schema = f'<script type="application/ld+json">{read(root / "src" / "schema" / org)}</script>\n'
    # ponytail: Spanish pages omit English page-specific schema; localize it when Spanish SEO needs it.
    if meta.get("schema") and lang == "en":
        schema += f'<script type="application/ld+json">{read(root / "src" / meta["schema"])}</script>\n'
    noindex = meta.get("noindex", "false").lower() == "true"
    nav = re.sub(rf'(<a href="{re.escape(c)}")', r'\1 aria-current="page"', partials["nav"])
    html = partials["head"] + nav + body + partials["footer"]
    english = c[3:] or "/" if lang == "es" else c
    spanish = c if lang == "es" else "/es" + ("" if c == "/" else c)
    alternates = "\n".join(
        f'<link rel="alternate" hreflang="{code}" href="{SITE}{path}" />'
        for code, path in (("en", english), ("es", spanish), ("x-default", english)))
    switch = ('<div class="lang-switch" role="group" aria-label="Language / Idioma">'
              f'<a href="{english}" lang="en" hreflang="en"' + (' aria-current="page"' if lang == "en" else '') + '>EN</a>'
              f'<a href="{spanish}" lang="es" hreflang="es"' + (' aria-current="page"' if lang == "es" else '') + '>ES</a></div>')
    fills = {
        "{{title}}": meta["title"],
        "{{description}}": meta["description"],
        "{{canonical}}": SITE + c,
        "{{og_title}}": meta.get("og_title", meta["title"]),
        "{{schema_jsonld}}": schema,
        "{{ga4}}": GA4_SNIPPET.format(id=GA4_ID) if GA4_ID else "",
        "{{robots}}": '<meta name="robots" content="noindex, nofollow" />' if noindex else "",
        "{{lead_form}}": partials["lead-form"].rstrip("\n"),
        "{{lang}}": lang,
        "{{hreflang}}": alternates,
        "{{language_switch}}": switch,
        "{{og_locale}}": "es_US" if lang == "es" else "en_US",
        "{{og_image_alt}}": "Kaico Voice, asistente que atiende llamadas las 24 horas" if lang == "es" else "Kaico Voice, AI receptionist that answers and books 24/7",
    }
    for k, v in fills.items():
        html = html.replace(k, v)
    return html


def check(root, pages):
    errs, seen = [], {"title": {}, "description": {}, "canonical": {}}
    paths = {p["canonical"] for p in pages} | STATIC
    for p in pages:
        # checks run on what a browser renders; HTML comments (the P0-T8 / P1 pending-link markers) are not content
        c, m, html = p["canonical"], p["meta"], re.sub(r"<!--.*?-->", "", p["html"], flags=re.S)
        t, d = m.get("title", ""), m.get("description", "")
        for k in ("title", "description", "canonical"):
            if not m.get(k):
                errs.append(f"{c}: missing {k}")
        if t and ("|" not in t or " - " in t or len(t) > TITLE_MAX):
            errs.append(f"{c}: bad title {t!r}")
        if d and not 70 <= len(d) <= 160:
            errs.append(f"{c}: description length {len(d)}")
        for k, v in (("title", t), ("description", d), ("canonical", c)):
            if v and v in seen[k]:
                errs.append(f"{c}: duplicate {k} with {seen[k][v]}")
            seen[k][v] = c
        for b in BANNED:
            if re.search(b, html, re.I):
                errs.append(f"{c}: banned string {b!r}")
        h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        if len(h1s) != 1:
            errs.append(f"{c}: {len(h1s)} h1 tags")
        for h in h1s:
            if re.search(r"\bAI\b|receptionist", h, re.I):
                errs.append(f"{c}: h1 mentions AI/receptionist")
        for img in re.findall(r"<img[^>]*>", html):
            if "alt=" not in img:
                errs.append(f"{c}: img without alt")
        for href in set(re.findall(r'href="(/[^"#?]*)"', html)):
            if href.endswith(".html"):
                errs.append(f"{c}: .html link {href}")
            elif href not in paths and not (root / href.strip("/")).exists() \
                    and not (root / (href.strip("/") + ".html")).exists():
                errs.append(f"{c}: dead link {href}")
    return errs


def build(root=ROOT, write=True):
    """Render every page. Returns (errors, outputs). Writes files only when write=True and there are no errors."""
    src = root / "src"
    partials = {n: read(src / "partials" / f"{n}.html") for n in ("head", "nav", "footer", "lead-form")}
    spanish = dict(partials)
    if (src / "pages" / "es").exists():
        spanish.update({n: read(src / "partials" / f"{n}.es.html") for n in ("nav", "footer", "lead-form")})
    pages, errs = [], []
    for path in sorted((src / "pages").rglob("*.html")):
        meta, body = parse(path)
        if meta is None:
            errs.append(f"{path}: missing meta block")
            continue
        rel = "/" + str(path.relative_to(src / "pages"))[:-5]
        meta.setdefault("canonical", {"/index": "/", "/es/index": "/es"}.get(rel, rel))
        if rel in ("/404", "/es/404"):
            meta["noindex"] = "true"
        for k in ("title", "description"):
            meta.setdefault(k, "")
        lang = "es" if path.relative_to(src / "pages").parts[0] == "es" else "en"
        pages.append({"meta": meta, "canonical": meta["canonical"], "src": path,
                      "html": render(root, meta, body, spanish if lang == "es" else partials, lang)})
    errs += check(root, pages)
    indexable = [p for p in pages if p["meta"].get("noindex", "false").lower() != "true"]
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sitemap += [f"  <url><loc>{SITE}{p['canonical']}</loc><lastmod>{lastmod(root, p['src'])}</lastmod></url>"
                for p in indexable]
    sitemap.append("</urlset>")
    llms = ["# Kaico Voice",
            "> Kaico builds and runs the online front door for the trades: the website, the Google listing, "
            "and the phone that answers when you can't.", ""]
    llms += [f"- [{p['meta']['title']}]({SITE}{p['canonical']}): {p['meta']['description']}" for p in indexable]
    out = {p["canonical"]: p["html"] for p in pages}
    out["sitemap.xml"] = "\n".join(sitemap) + "\n"
    out["llms.txt"] = "\n".join(llms) + "\n"
    if errs or not write:
        return errs, out
    for p in pages:
        op = root / ("index.html" if p["canonical"] == "/" else p["canonical"].strip("/") + ".html")
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(p["html"], encoding="utf-8")
    (root / "sitemap.xml").write_text(out["sitemap.xml"], encoding="utf-8")
    (root / "llms.txt").write_text(out["llms.txt"], encoding="utf-8")
    return errs, out


if __name__ == "__main__":
    errors, result = build()
    if errors:
        print("\n".join("FAIL " + e for e in errors))
        sys.exit(1)
    n = len([k for k in result if k.startswith("/")])
    print(f"OK {n} pages, {result['sitemap.xml'].count('<loc>')} indexable, sitemap.xml and llms.txt written")
