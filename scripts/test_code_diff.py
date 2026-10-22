"""Verify highlighted diffs preserve source text across common iOS languages."""
from html.parser import HTMLParser
import unittest
try:
    from code_diff import render_file
except ModuleNotFoundError:
    render_file = None


class DiffRows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []; self.row = None; self.in_code = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'div' and 'diff-line' in attrs.get('class', '').split():
            self.row = {'old': attrs.get('data-old', ''), 'new': attrs.get('data-new', ''), 'text': ''}
            self.rows.append(self.row)
        if tag == 'code' and self.row is not None:
            self.in_code = True
    def handle_endtag(self, tag):
        if tag == 'code': self.in_code = False
    def handle_data(self, data):
        if self.in_code: self.row['text'] += data


@unittest.skipIf(render_file is None, 'Install Pygments to test highlighted diffs')
class HighlightTests(unittest.TestCase):
    def test_common_languages_and_multiline_state_preserve_source(self):
        samples = {
            'Example.swift': ('let text = """\n<old>\n"""\n', 'let text = """\n<new> & value\n"""\n'),
            'Example.m': ('/* comment\ncontinues */\nNSString *x = @"old";\n', '/* comment\ncontinues */\nNSString *x = @"new";\n'),
            'Example.mm': ('auto x = 1;\n', 'auto x = 2;\n'),
            'Example.py': ('value = "old"\n', 'value = "new"\n'),
            'Example.sh': ('echo "<old>"\n', 'echo "<new> & value"\n'),
            'Fastfile': ('lane :old do\nend\n', 'lane :new do\nend\n'),
            'Example.json': ('{"value": 1}\n', '{"value": 2}\n'),
            'Example.yml': ('value: old\n', 'value: new\n'),
            'Example.plist': ('<string>old</string>\n', '<string>new &amp; value</string>\n'),
            'Example.toml': ('value = "old"\n', 'value = "new"\n'),
            'Example.ts': ('const value = 1;\n', 'const value = 2;\n'),
            'Example.proto': ('message Old {}\n', 'message New {}\n'),
            'Example.metal': ('float value = 1;\n', 'float value = 2;\n'),
            'Example.unknown': ('<old>\n', '<new>\n'),
        }
        for path, (before, after) in samples.items():
            with self.subTest(path=path):
                output = render_file({'owner': 'Example', 'path': path, 'before': before, 'after': after})
                rows = DiffRows(); rows.feed(output)
                source, proposed = before.split('\n'), after.split('\n')
                checked = 0
                for row in rows.rows:
                    if row['old']:
                        self.assertEqual(row['text'], source[int(row['old']) - 1]); checked += 1
                    if row['new']:
                        self.assertEqual(row['text'], proposed[int(row['new']) - 1]); checked += 1
                self.assertGreater(checked, 0)
                self.assertNotIn('<old>', output)
                self.assertNotIn('<new>', output)


if __name__ == '__main__':
    unittest.main()
