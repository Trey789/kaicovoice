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
LLMS_SECTIONS = (
    ("English: overview", (
        ("/", "Website, Google listing, phone and job-system services for trade businesses."),
        ("/pricing", "Published one-time and monthly options, with terms and scope details."),
        ("/proof", "Examples of completed work and how Kaico checks reported numbers."),
        ("/start", "Request a review of your website, listing, phone or job workflow."),
        ("/tulsa", "Answering service in Tulsa, Oklahoma for trade businesses: founder-operated, delivered remotely, with setup steps and pricing."),
    )),
    ("English: services", (
        ("/services/front-door", "Monthly website, listing, phone, scheduling and job-system service."),
        ("/services/phone", "Phone answering and calendar booking for trade businesses."),
        ("/services/websites", "Website builds with contact and quote-request paths."),
        ("/services/job-system", "Jobs, quotes, invoices and customer email workflow."),
        ("/services/google-business-profile", "Google Business Profile setup and ongoing care."),
        ("/services/google-ads", "Managed search and call advertising; ad spend is separate."),
        ("/services/business-consulting", "Process review, workflow map and prioritized plan."),
    )),
    ("English: guides", (
        ("/guides", "Hub for the three guides on answering service and AI receptionist cost, with links to the coverage checker and pricing."),
        ("/guides/answering-service-cost", "Answering service pricing models explained, and what Kaico charges."),
        ("/guides/ai-receptionist-cost", "What drives AI receptionist cost and what $299 a month includes."),
        ("/guides/ai-receptionist-vs-answering-service", "Human answering service and AI receptionist compared, and who should pick which."),
    )),
    ("English: policies", (
        ("/client-agreement", "Payment, ownership, cancellation and service terms."),
        ("/privacy", "How information is handled, including calls to the AI receptionist."),
        ("/terms", "Website, service and SMS terms."),
        ("/sms", "SMS consent, message types and opt-out details."),
    )),
    ("English: tools", (
        ("/tools/after-hours-coverage-checker", "Free checker: enter the hours your shop answers and see the unanswered hours, nights and weekend days each week."),
    )),
    ("Español: información general", (
        ("/es", "Servicios de sitios web, perfil de Google, teléfono y sistema de trabajos para oficios."),
        ("/es/pricing", "Opciones publicadas de pago único y mensual, con detalles de condiciones y alcance."),
        ("/es/proof", "Ejemplos de trabajo realizado y cómo Kaico verifica las cifras publicadas."),
        ("/es/start", "Solicita una revisión de tu sitio, perfil, teléfono o proceso de trabajos."),
        ("/es/tulsa", "Atención telefónica en Tulsa, Oklahoma para negocios de oficios: dirigida por su fundador, entregada a distancia, con pasos de configuración y precios."),
    )),
    ("Español: servicios", (
        ("/es/services/front-door", "Servicio mensual de sitio web, perfil, teléfono, reservas y sistema de trabajos."),
        ("/es/services/phone", "Atención telefónica y reservas en calendario para negocios de oficios."),
        ("/es/services/websites", "Creación de sitios web con opciones de contacto y solicitud de cotización."),
        ("/es/services/job-system", "Gestión de trabajos, cotizaciones, facturas y correos a clientes."),
        ("/es/services/google-business-profile", "Configuración y mantenimiento del Perfil de Negocio de Google."),
        ("/es/services/google-ads", "Gestión de anuncios de búsqueda y llamadas; inversión publicitaria aparte."),
        ("/es/services/business-consulting", "Revisión de procesos, mapa de trabajo y plan priorizado."),
    )),
    ("Español: guías", (
        ("/es/guides", "Índice de las tres guías sobre el costo de un servicio de contestación y de una recepcionista con IA, con enlaces al verificador de cobertura y a los precios."),
        ("/es/guides/answering-service-cost", "Modelos de precios de los servicios de contestación y lo que cobra Kaico."),
        ("/es/guides/ai-receptionist-cost", "Qué determina el costo de una recepcionista con IA y qué incluyen los $299 al mes."),
        ("/es/guides/ai-receptionist-vs-answering-service", "Servicio de contestación humano y recepcionista con IA, comparados, y cuál elegir."),
    )),
    ("Español: políticas", (
        ("/es/client-agreement", "Condiciones de pago, propiedad, cancelación y servicio."),
        ("/es/privacy", "Tratamiento de datos, incluidas las llamadas a la recepcionista con IA."),
        ("/es/terms", "Condiciones del sitio web, los servicios y los SMS."),
        ("/es/sms", "Consentimiento, tipos de mensajes y baja del programa de SMS."),
    )),
    ("Español: herramientas", (
        ("/es/tools/after-hours-coverage-checker", "Verificador gratuito: ingresa las horas en que tu negocio contesta y ve las horas, noches y fines de semana sin cobertura."),
    )),
)
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
        "{{skip_link}}": "Ir al contenido" if lang == "es" else "Skip to content",
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
            "> Website, Google Business Profile, phone and job-system services for trade businesses. "
            "English and Spanish site guides below.", ""]
    by_canonical = {p["canonical"]: p for p in indexable}
    for heading, entries in LLMS_SECTIONS:
        links = [f"- [{by_canonical[path]['meta']['title']}]({SITE}{path}): {summary}"
                 for path, summary in entries if path in by_canonical]
        if links:
            llms += [f"## {heading}", *links, ""]
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
