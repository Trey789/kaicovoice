#!/usr/bin/env python3
"""One-off: split the live hand-written pages into src/partials and src/pages.
Run once for the homepage (--home), then once per other page (--page industries/hvac.html)."""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
MAIN_OPEN = re.compile(r"<main[^>]*>")


def split(html):
    head, rest = html.split("<nav>", 1)
    nav, rest = rest.split("</nav>", 1)
    m = MAIN_OPEN.search(rest)
    pre_main, main_tag, rest = rest[:m.start()], m.group(0), rest[m.end():]
    main, footer = rest.split("</main>", 1)
    return head + pre_main.strip(), "<nav>" + nav + "</nav>\n", main_tag + main + "</main>\n", footer.lstrip()


def meta_of(html):
    def grab(pat):
        m = re.search(pat, html, re.S)
        return m.group(1).strip() if m else ""
    return {
        "title": grab(r"<title>(.*?)</title>").replace("&amp;", "&"),
        "description": grab(r'<meta name="description" content="(.*?)"'),
        "canonical": grab(r'<link rel="canonical" href="https://www\.kaicovoice\.com(/[^"]*)"') or "/",
    }


def templatize_head(head):
    head = re.sub(r"<title>.*?</title>", "<title>{{title}}</title>", head, flags=re.S)
    head = re.sub(r'(<meta name="description" content=")[^"]*(")', r"\1{{description}}\2", head)
    head = re.sub(r'(<link rel="canonical" href=")[^"]*(")', r"\1{{canonical}}\2", head)
    head = re.sub(r'(<meta property="og:title" content=")[^"]*(")', r"\1{{og_title}}\2", head)
    head = re.sub(r'(<meta property="og:description" content=")[^"]*(")', r"\1{{description}}\2", head)
    head = re.sub(r'(<meta property="og:url" content=")[^"]*(")', r"\1{{canonical}}\2", head)
    head = re.sub(r'(<meta name="twitter:title" content=")[^"]*(")', r"\1{{og_title}}\2", head)
    head = re.sub(r'(<meta name="twitter:description" content=")[^"]*(")', r"\1{{description}}\2", head)
    head = re.sub(r'\s*<script type="application/ld\+json">.*?</script>', "", head, flags=re.S)
    return head.replace("</head>", "{{robots}}\n{{schema_jsonld}}{{ga4}}\n</head>")


def front_matter(meta, extra=""):
    return f"<!-- meta\ntitle: {meta['title']}\ndescription: {meta['description']}\ncanonical: {meta['canonical']}\n{extra}-->\n"


def save_page_schema(head, rel):
    """Keep any non-organization JSON-LD (FAQPage etc.) as the page's own schema file."""
    blocks = [b.strip() for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', head, re.S)
              if "ProfessionalService" not in b]
    if not blocks:
        return ""
    name = (rel.replace("/", "-").replace(".html", "") or "index") + ".json"
    (SRC / "schema").mkdir(parents=True, exist_ok=True)
    (SRC / "schema" / name).write_text(blocks[0], encoding="utf-8")
    return f"schema: schema/{name}\n"


def home():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    head, nav, main, footer = split(html)
    (SRC / "partials").mkdir(parents=True, exist_ok=True)
    (SRC / "pages").mkdir(parents=True, exist_ok=True)
    (SRC / "schema").mkdir(parents=True, exist_ok=True)
    (SRC / "partials" / "head.html").write_text(templatize_head(head), encoding="utf-8")
    (SRC / "partials" / "nav.html").write_text(nav, encoding="utf-8")
    (SRC / "partials" / "footer.html").write_text(footer, encoding="utf-8")
    extra = save_page_schema(head, "index.html")
    (SRC / "pages" / "index.html").write_text(front_matter(meta_of(html), extra) + main, encoding="utf-8")
    print("home split: partials + src/pages/index.html")


def page(rel):
    html = (ROOT / rel).read_text(encoding="utf-8")
    head, _nav, main, _footer = split(html)
    home_css = re.search(r"<style>.*?</style>", (SRC / "partials" / "head.html").read_text(encoding="utf-8"), re.S)
    page_css = re.search(r"<style>.*?</style>", head, re.S)
    body = main
    if page_css and (not home_css or page_css.group(0) != home_css.group(0)):
        body = page_css.group(0) + "\n" + main  # page keeps its own CSS until its content task prunes it
    extra = save_page_schema(head, rel)
    out = SRC / "pages" / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(front_matter(meta_of(html), extra) + body, encoding="utf-8")
    print(f"page split: src/pages/{rel}")


if __name__ == "__main__":
    if sys.argv[1] == "--home":
        home()
    else:
        page(sys.argv[2])
