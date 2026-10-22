"""Checks release resources, standard metadata and self-contained report packaging."""
import json
from pathlib import Path
import re
import unittest
from html.parser import HTMLParser
from prepare_report import prepare

ROOT = Path(__file__).resolve().parent.parent


class PackageTests(unittest.TestCase):
    def test_skill_metadata_and_local_reference_links(self):
        text = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        self.assertTrue(text.startswith('---\nname: modular-ios-audit\n'))
        self.assertIn('\nlicense: MIT\n', text)
        self.assertIn('\ncompatibility: ', text)
        for path in [ROOT / 'SKILL.md', *sorted((ROOT / 'references').glob('*.md'))]:
            for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                if '://' in target or target.startswith('#'):
                    continue
                self.assertTrue((path.parent / target.split('#')[0]).is_file(), (path.name, target))

    def test_embedded_assets_match_sources_and_input_is_synthetic(self):
        template = (ROOT / 'assets/report-template.html').read_text(encoding='utf-8')
        fixture = json.loads((ROOT / 'tests/fixtures/audit.json').read_text(encoding='utf-8'))
        self.assertEqual(prepare(fixture, template), template)
        self.assertIn('Illustrative', template)
        for script_id, name in [('audit-scoring', 'report-scoring.js'), ('audit-navigation', 'report-navigation.js')]:
            actual = re.search(r'<script id="' + script_id + r'"[^>]*>([\s\S]*?)</script>', template)[1]
            self.assertEqual(actual, (ROOT / 'assets' / name).read_text(encoding='utf-8'))
        actual = re.search(r'<style id="audit-base-style">([\s\S]*?)</style>', template)[1]
        self.assertEqual(actual, (ROOT / 'assets/report-base.css').read_text(encoding='utf-8'))

    def test_no_external_runtime_assets(self):
        external = []
        class Assets(HTMLParser):
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag in {'script', 'img', 'iframe', 'source'} and attrs.get('src'):
                    external.append(attrs['src'])
                if tag == 'link' and attrs.get('rel') == 'stylesheet':
                    external.append(attrs.get('href'))
        Assets().feed((ROOT / 'assets/report-template.html').read_text(encoding='utf-8'))
        self.assertEqual(external, [])
        self.assertNotIn('@import', (ROOT / 'assets/report-base.css').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
