"""The rendered site must define the business once and resolve its service providers."""
import json
from html.parser import HTMLParser
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build


class LinkedData(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.active = False
        self.text = ''
        self.nodes = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('type') == 'application/ld+json':
            self.active = True
            self.text = ''

    def handle_data(self, text):
        if self.active:
            self.text += text

    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            data = json.loads(self.text)
            self.nodes.extend(data.get('@graph', [data]))
            self.active = False


class SharedBusinessSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        errors, cls.pages = build.build(write=False)
        assert not errors, errors

    def test_every_service_provider_resolves_to_one_business_definition(self):
        services = 0
        for route, html in self.pages.items():
            if not route.startswith('/'):
                continue
            with self.subTest(route=route):
                nodes = LinkedData(html).nodes
                business = [n for n in nodes if n.get('name') == 'Kaico Voice']
                self.assertEqual(len(business), 1)
                company = business[0]
                self.assertEqual(company['@type'], 'Organization')
                self.assertTrue(company.get('@id', '').startswith('https://www.kaicovoice.com/'))
                for node in nodes:
                    if node.get('@type') == 'Service':
                        services += 1
                        self.assertEqual(node['provider'], {'@id': company['@id']})
        self.assertGreaterEqual(services, 8)

    def test_languages_describe_the_same_business_without_an_invented_street(self):
        english = LinkedData(self.pages['/']).nodes[0]
        spanish = LinkedData(self.pages['/es']).nodes[0]
        for key in ('@id', 'name', 'legalName', 'url', 'telephone', 'email', 'address'):
            self.assertEqual(english.get(key), spanish.get(key), key)
        self.assertTrue(english.get('@id'))
        self.assertNotIn('streetAddress', english['address'])
        self.assertNotIn('postalCode', english['address'])
