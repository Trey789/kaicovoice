import pathlib, shutil, sys, tempfile, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import build  # noqa: E402

HEAD = ('<!doctype html><html lang="en"><head><title>{{title}}</title>'
        '<meta name="description" content="{{description}}" />'
        '<link rel="canonical" href="{{canonical}}" />{{robots}}{{schema_jsonld}}{{ga4}}</head><body>')
NAV = '<nav><a href="/">Home</a><a href="/pricing">Pricing</a></nav>'
FOOT = '<footer></footer></body></html>'
DESC = "Front Door Audit free. Website builds from $3,500. Month to month, 30 days notice. See the ladder."


def make_site(tmp, pages):
    src = tmp / "src"
    (src / "partials").mkdir(parents=True)
    (src / "pages").mkdir()
    (src / "schema").mkdir()
    (src / "partials" / "head.html").write_text(HEAD)
    (src / "partials" / "nav.html").write_text(NAV)
    (src / "partials" / "footer.html").write_text(FOOT)
    (src / "schema" / "organization.json").write_text('{"@type": "ProfessionalService"}')
    for name, text in pages.items():
        p = src / "pages" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


def page(title="Pricing | Kaico Voice", desc=DESC, canonical="/pricing",
         body="<main><h1>Pricing</h1></main>", extra=""):
    return f"<!-- meta\ntitle: {title}\ndescription: {desc}\ncanonical: {canonical}\n{extra}-->\n{body}"


class BuildChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_build(self, pages):
        make_site(self.tmp, pages)
        return build.build(self.tmp, write=False)

    def test_good_page_passes_and_marks_active_nav(self):
        errs, out = self.run_build({"pricing.html": page()})
        self.assertEqual(errs, [])
        self.assertIn('href="/pricing" aria-current="page"', out["/pricing"])
        self.assertIn("<title>Pricing | Kaico Voice</title>", out["/pricing"])

    def test_em_dash_fails(self):
        errs, _ = self.run_build({"pricing.html": page(body="<main><h1>Pricing</h1><p>a — b</p></main>")})
        self.assertTrue(any("banned" in e for e in errs), errs)

    def test_retired_price_and_contract_phrases_fail(self):
        errs, _ = self.run_build({"pricing.html": page(body="<main><h1>Pricing</h1><p>$250/mo, cancel anytime, no contract</p></main>")})
        self.assertEqual(sum("banned" in e for e in errs), 3, errs)

    def test_no_contractor_is_not_no_contract(self):
        errs, _ = self.run_build({"pricing.html": page(body="<main><h1>Pricing</h1><p>no contractor is left waiting</p></main>")})
        self.assertEqual(errs, [])

    def test_missing_description_fails(self):
        errs, _ = self.run_build({"pricing.html": page(desc="")})
        self.assertTrue(any("missing description" in e for e in errs), errs)

    def test_long_title_fails(self):
        errs, _ = self.run_build({"pricing.html": page(title="X" * 55 + " | Kaico Voice")})
        self.assertTrue(any("bad title" in e for e in errs), errs)

    def test_two_h1_fails(self):
        errs, _ = self.run_build({"pricing.html": page(body="<main><h1>A</h1><h1>B</h1></main>")})
        self.assertTrue(any("h1 tags" in e for e in errs), errs)

    def test_receptionist_in_h1_fails(self):
        errs, _ = self.run_build({"pricing.html": page(body="<main><h1>Your AI receptionist</h1></main>")})
        self.assertTrue(any("AI/receptionist" in e for e in errs), errs)

    def test_img_without_alt_fails(self):
        errs, _ = self.run_build({"pricing.html": page(body='<main><h1>P</h1><img src="/assets/x.png"></main>')})
        self.assertTrue(any("img without alt" in e for e in errs), errs)

    def test_dead_and_html_links_fail(self):
        body = '<main><h1>P</h1><a href="/nope">x</a><a href="/pricing.html">y</a><a href="/#audit">z</a></main>'
        errs, _ = self.run_build({"pricing.html": page(body=body)})
        self.assertTrue(any("dead link /nope" in e for e in errs), errs)
        self.assertTrue(any(".html link" in e for e in errs), errs)
        self.assertFalse(any("/#audit" in e for e in errs), errs)

    def test_link_to_existing_root_html_file_passes(self):
        (self.tmp / "proof.html").write_text("<html></html>")
        errs, _ = self.run_build({"pricing.html": page(body='<main><h1>P</h1><a href="/proof">x</a></main>')})
        self.assertEqual(errs, [])

    def test_commented_out_markup_is_ignored(self):
        body = ('<main><h1>P</h1><!-- P1: <a href="/nope">x</a> --><!-- <h1>ghost</h1> -->'
                '<!-- <img src="/assets/x.png"> --><!-- $250 --></main>')
        errs, _ = self.run_build({"pricing.html": page(body=body)})
        self.assertEqual(errs, [])

    def test_dead_mailbox_address_fails(self):
        errs, _ = self.run_build({"pricing.html": page(body='<main><h1>P</h1><a href="mailto:trey@kaicovoice.com">mail</a></main>')})
        self.assertTrue(any("banned" in e for e in errs), errs)

    def test_duplicate_title_fails(self):
        errs, _ = self.run_build({"a.html": page(canonical="/a"), "b.html": page(canonical="/b")})
        self.assertTrue(any("duplicate title" in e for e in errs), errs)

    def test_noindex_excluded_from_sitemap_and_gets_robots_meta(self):
        pages = {"pricing.html": page(),
                 "thanks.html": page(title="Thanks | Kaico Voice", canonical="/thanks",
                                     desc="Your Front Door Audit request is in. It lands in your inbox within two business days.",
                                     body="<main><h1>Thanks</h1></main>", extra="noindex: true\n")}
        errs, out = self.run_build(pages)
        self.assertEqual(errs, [])
        self.assertIn("/pricing", out["sitemap.xml"])
        self.assertNotIn("/thanks", out["sitemap.xml"])
        self.assertIn('name="robots" content="noindex', out["/thanks"])
        self.assertIn("Pricing | Kaico Voice", out["llms.txt"])


if __name__ == "__main__":
    unittest.main()
