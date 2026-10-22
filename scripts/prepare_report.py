#!/usr/bin/env python3
"""Embed validated audit data, scoring and navigation; print an openable local URL."""
import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import webbrowser
from score_audit import score


def scroll_tables(document):
    """Keep wide evidence tables inside the page, preserving authored table markup."""
    offsets, total = [], 0
    for line in document.splitlines(keepends=True):
        offsets.append(total); total += len(line)
    edits = []
    class Tables(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False); self.stack = []; self.tables = []
        def position(self):
            line, column = self.getpos(); return offsets[line - 1] + column
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'table':
                wrap = not any('table-scroll' in classes.split() for _, classes in self.stack)
                self.tables.append(wrap)
                if wrap: edits.append((self.position(), '<div class="table-scroll">'))
            if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
                self.stack.append((tag, attrs.get('class', '')))
        def handle_endtag(self, tag):
            if tag == 'table' and self.tables and self.tables.pop():
                end = document.index('>', self.position()) + 1; edits.append((end, '</div>'))
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]; break
        def handle_startendtag(self, tag, attrs):
            pass
    Tables().feed(document)
    for position, insertion in sorted(edits, reverse=True):
        document = document[:position] + insertion + document[position:]
    return document


def identity(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def snapshot(result, titles):
    def percent(value):
        return one_decimal(value['percent'])
    def badge(label, cls):
        return f'<span class="gate {html.escape(cls)}">{html.escape(label)}</span>'
    total = result['total']
    rows = []
    for p in result['principles']:
        pid = p['id']
        if p['gate'] == 'skipped':
            roots, involved, risk_label, coverage = '—', '—', 'Skipped', ''
        elif p['impact']['scope'] == 'external-only':
            roots, involved, risk_label, coverage = '—', '—', f"{p['external_enforcement']['failed']}/{p['external_enforcement']['evaluated_families']} families failed", 'External enforcement'
        else:
            roots = f"{p['rootCostModules']}/{total}"
            involved = f"{p['risk']['involved_modules'] if p['risk']['involved_modules'] is not None else '?'}/{total}"
            risk_label = f"{percent(p['risk'])} · {p['risk']['band'] or 'N/A'}"
            coverage = f"{p['counts']['issue'] + p['counts']['clear']}/{p['applicable']} classified"
        rows.append(f'<div class="score-row"><a class="score-name" href="#{pid.lower()}">{html.escape(pid + " " + titles.get(pid, ""))}<span class="score-sub">{coverage}</span></a><div>{roots}</div><div>{involved}</div><div>{risk_label}</div><div>{badge(p["gate"].upper(), p["gate"])}</div></div>')
    risk, observed, structural = result['risk'], result['observed_risk'], result['structural']
    band = risk['band'] or 'N/A'
    band_chip = f'<span class="impact-band {band.lower()}" aria-label="Overall risk band">{band}</span>'
    headline = f'Risk withheld · {html.escape(risk["withheld"])}' if risk['withheld'] else f'Risk {percent(risk)} · {risk["involved_modules"]}/{total} modules involved'
    facts = [f'Defects in {result["rootCostModules"] if result["rootCostModules"] is not None else "?"}/{total} modules',
             f'Before review choices {percent(observed)}', f'{total}/{result["inventory_total"]} modules in scope',
             f'Lowest principle classification {math.floor(risk["coverage_min"] * 100)}%' if risk['coverage_min'] is not None else 'Classification unknown',
             f'Structural candidates {structural["candidates"] - len(structural["unresolved"])}/{structural["candidates"]} resolved' if structural['screened'] else 'Structure scan missing']
    structure = result.get('structure')
    structure_row = '' if not structure else '<div class="score-structure"><span>Structure scan:</span>' + ''.join(f'<span>{html.escape(label)}</span>' for label in (
        f'effective modules {structure["effective_modules"]}', f'largest {structure["largest_module"]} holds {structure["largest_share"] * 100:.0f}% of code',
        f'a change reaches {structure["mass_propagation_cost"] * 100:.0f}% of code', f'cycles {structure["cycles"]}')) + '</div>'
    top = [r for r in result['ranking'] if r['open']][:5]
    problems = '' if not top else '<h3 class="top-problems-title">Top problems by risk</h3><ol class="top-problems" aria-label="Top problems by risk">' + ''.join(
        f'<li><a href="#{html.escape(r["id"])}">{html.escape(titles.get(r["id"], r["id"]))}</a><span class="score-sub">{problem_facts(r, total)}</span></li>' for r in top) + '</ol>'
    key = ('Risk = severity-weighted share of modules that own or directly import an open defect (low 0.1 · medium 0.4 · high and critical 1.0). '
           'Each module counts once, at its strongest open defect. LOW < 3% · MEDIUM < 10% · HIGH ≥ 10%.')
    return (f'<section class="scoreboard" id="scores" data-overview><div class="verdict"><h2>{headline}</h2>{band_chip}<span class="fact-chip">Coverage: {"complete" if risk["coverage_complete"] else "partial"}</span></div>'
            f'<div class="score-overall">{"".join(f"<span>{html.escape(fact)}</span>" for fact in facts)}</div>{structure_row}{problems}'
            f'<div class="score-head"><span>Principle</span><span>Defect modules</span><span>Involved</span><span>Risk</span><span>Local status</span></div>{"".join(rows)}'
            f'<div class="score-key score-policy"><span>{html.escape(key)}</span></div></section>')


def one_decimal(percent):
    """Round half up to one decimal, matching the browser's display."""
    return 'N/A' if percent is None else f'{math.floor(percent * 10 + 0.5) / 10:.1f}%'


def problem_facts(r, total):
    modules = 'module' if r['defect_modules'] == 1 else 'modules'
    return html.escape(f'{", ".join(r["principles"])}{" · structural" if r["structural"] else ""} · {r["severity"]} · '
                       f'defects in {r["defect_modules"]} {modules} · {r["involved_modules"]}/{total} involved · {one_decimal(r["impact"] * 100)} risk')


def prepare(data, document):
    result = score(data)
    for p in data['principles']:
        targets = [p['id'].lower()]
        for f in p.get('findings', []):
            targets.append(f['id'])
            if f.get('kind', 'issue') == 'issue':
                targets.extend(f['id'] + suffix for suffix in ('-fix', '-evidence'))
        for target in targets:
            if not re.search(r'\bid=["\']' + re.escape(target) + r'["\']', document):
                raise ValueError('Report is missing principle/issue anchor: ' + target)
    assets = Path(__file__).resolve().parent.parent / 'assets'
    if re.search(r'<style\b[^>]*\bid=["\']audit-base-style["\']', document):
        document = re.sub(r'<style\b[^>]*\bid=["\']audit-base-style["\'][^>]*>[\s\S]*?</style>', lambda _: '<style id="audit-base-style">' + (assets / 'report-base.css').read_text(encoding='utf-8') + '</style>', document)
    # Replacing known embedded assets is idempotent. Escape JSON before putting it in HTML.
    document = re.sub(r'<style\b[^>]*\bid=["\']audit-review-style["\'][^>]*>[\s\S]*?</style>', '', document)
    document = document.replace('</head>', '<style id="audit-review-style">' + (assets / 'report-review.css').read_text(encoding='utf-8') + '</style></head>')
    for script_id in ('audit-data', 'audit-scoring', 'audit-navigation'):
        document = re.sub(r'<script\b[^>]*\bid=["\']' + script_id + r'["\'][^>]*>[\s\S]*?</script>', '', document)
    document, count = re.subn(r'<section\b[^>]*class=["\']scoreboard["\'][^>]*>[\s\S]*?</section>',
        lambda _: snapshot(result, {**{p['id']: p.get('title', '') for p in data['principles']},
                                    **{f['id']: f.get('title', f['id']) for p in data['principles'] for f in p.get('findings', [])}}), document, count=1)
    if not count:
        raise ValueError('Report needs a section.scoreboard with id="scores"')
    for p in result['principles']:
        for f in p.get('findings', []):
            labels = {'open': 'Open', 'resolved': 'Resolved', 'invalid': 'Invalid for this repo', 'accepted': 'Acceptable for this project'}
            status = 'Out of scope' if not f['in_scope'] else labels[f['decision']['status']] if f['decision']['status'] != 'open' else 'Suggestion · unscored' if f['presentation'] == 'suggestion' else 'Tiny issue' if f['presentation'] == 'tiny' else 'Open'
            location = 'External checks' if f['rootCostModules'] is None else f"Defects in {f['rootCostModules']}/{result['total']} · {f['risk']['involved_modules'] if f['risk']['involved_modules'] is not None else '?'}/{result['total']} involved"
            risk = one_decimal(f['risk']['percent'])
            summary = f'<div class="finding-metrics"><span>{html.escape(status)}</span>'
            if f['presentation'] == 'issue':
                summary += f'<span>{location}</span>'
            summary += f'<strong>Risk {risk}</strong></div>'
            pattern = r'(<details\b[^>]*\bid=["\']' + re.escape(f['id']) + r'["\'][^>]*>\s*<summary\b[^>]*>)([\s\S]*?)(</summary>)'
            def update(match):
                body = re.sub(r'<div\b[^>]*class=["\']finding-metrics["\'][^>]*>[\s\S]*?</div>', lambda _: summary, match[2])
                prefix = re.sub(r'\bclass="([^"]*)"', lambda c: 'class="' + ' '.join([name for name in c[1].split() if name not in ('issue--tiny', 'issue--suggestion')] + (['issue--' + f['presentation']] if f['presentation'] != 'issue' else [])) + '"', match[1], count=1)
                return prefix + body + match[3]
            document = re.sub(pattern, update, document, count=1)
    for p in result['principles']:
        if p['gate'] == 'skipped':
            label = 'Skipped'
        elif p['impact']['scope'] == 'external-only':
            label = f"{p['external_enforcement']['failed']}/{p['external_enforcement']['evaluated_families']}!"
        else:
            label = one_decimal(p['risk']['percent'])
        pattern = r'(<a\b[^>]*href=["\']#' + p['id'].lower() + r'["\'][^>]*>[\s\S]*?<span\b[^>]*class=["\']nav-result["\'][^>]*>)[\s\S]*?(</span>)'
        document = re.sub(pattern, lambda m: m[1] + label + m[2], document, count=1)
    document = scroll_tables(document)
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    scripts = f'<script id="audit-data" type="application/json" data-audit-id="{identity(data)}">{payload}</script>'
    scripts += '<script id="audit-scoring">' + (assets / 'report-scoring.js').read_text(encoding='utf-8') + '</script>'
    scripts += '<script id="audit-navigation">' + (assets / 'report-navigation.js').read_text(encoding='utf-8') + '</script>'
    if '</body>' not in document:
        raise ValueError('Report needs a closing body')
    return document.replace('</body>', scripts + '</body>')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('report', type=Path, help='Populated HTML following the report template')
    parser.add_argument('--output', type=Path, help='Defaults to updating the supplied report')
    parser.add_argument('--no-open', action='store_true', help='Validate/package without launching a browser')
    args = parser.parse_args()
    output = (args.output or args.report).expanduser().resolve()
    document = prepare(json.loads(args.input.read_text(encoding='utf-8')), args.report.read_text(encoding='utf-8'))
    output.write_text(document, encoding='utf-8')
    assert output.is_file() and output.stat().st_size > 0
    print(output.as_uri())
    if not args.no_open:
        try:
            requested = webbrowser.open(output.as_uri(), new=2)
            print('Requested opening in the default external browser.' if requested else 'Browser opener unavailable; use the local URL above.')
        except Exception as error:
            print('Browser opener unavailable; use the local URL above. ' + str(error))
