#!/usr/bin/env python3
"""Behavior and browser-projection parity checks. Run with python3; Node parity is optional."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from score_audit import score
from prepare_report import prepare, identity


def finding(fid, roots, severity='low', **extra):
    return {'id': fid, 'kind': 'issue', 'severity': severity, 'severity_reason': 'Traced consumer consequence',
            'rootCostModuleIDs': roots, 'reach_modules': [], 'external_scopes': [], 'evidence': ['Sources/Contract.swift:12'], **extra}


def sample(n=100, severity='low', affected=20, pid='P2'):
    modules = [f'Modules/M{i}' for i in range(n)]
    f = finding('unit-contract', [modules[0]], severity, reach_modules=modules[1:affected+1])
    ledger = {m: {'status': 'issue' if m == modules[0] else 'clear', 'basis': 'Traced contract'} for m in modules}
    return {'modules': modules, 'consumer_graph_complete': True, 'consumer_graph_provenance': {'source': 'Frozen fixture imports'}, 'consumers': {m: modules[1:affected+1] if i == 0 else [] for i, m in enumerate(modules)},
            'principles': [{'id': pid, 'findings': [f], 'ledger': ledger}]}


def principle(d, pid, findings=()):
    ledger = {m: {'status': 'clear', 'basis': 'Inspected'} for m in d['modules']}
    for f in findings:
        for m in f['rootCostModuleIDs']:
            ledger[m] = {'status': 'issue', 'basis': 'Traced'}
    d['principles'].append({'id': pid, 'findings': list(findings), 'ledger': ledger})
    return d


def structural(d, candidates, resolutions, findings, pid='P1'):
    d['structural'] = {'candidates': candidates, 'resolutions': resolutions}
    existing = next((p for p in d['principles'] if p['id'] == pid), None)
    if existing:
        existing['findings'].extend(findings)
        for f in findings:
            for m in f['rootCostModuleIDs']:
                existing['ledger'][m] = {'status': 'issue', 'basis': 'Traced'}
        return d
    principle(d, pid, findings); d['principles'].insert(0, d['principles'].pop())
    return d


def candidate(cid, modules, archetype='contamination-hub', floor='high'):
    return {'id': cid, 'archetype': archetype, 'modules': modules, 'severity_floor': floor, 'trigger': 'scan', 'metrics': {}}


def plain(n=2, severity='high'):
    modules = [f'M{i}' for i in range(n)]
    d = {'modules': modules, 'consumer_graph_complete': True, 'consumer_graph_provenance': {'source': 'fixture'},
         'consumers': {m: [] for m in modules}, 'principles': []}
    return principle(d, 'P1', [finding('owner', ['M0'], severity)])


def scenarios():
    base = sample()
    cases = [base]
    for severity in ['low', 'medium', 'high', 'critical']:
        for reach in [0, 3, 10, 30, 99]: cases.append(sample(severity=severity, affected=reach))
    for status in ['resolved', 'invalid', 'accepted', 'intended', 'open']:
        d = sample(severity='high'); d['decisions'] = {'unit-contract': {'status': status, 'decided_by': 'user'}}; cases.append(d)
    d = sample(); d['excluded_modules'] = [{'module': 'Modules/M0', 'reason': 'Outside requested scope'}]; cases.append(d)
    d = sample(); d['excluded_modules'] = [{'module': 'Modules/M1', 'reason': 'Outside scope'}]; cases.append(d)
    d = sample(); d['consumer_graph_complete'] = False; cases.append(d)
    d = sample(); d.pop('consumer_graph_provenance'); cases.append(d)
    d = sample(); del d['consumers']['Modules/M50']; cases.append(d)
    d = sample(); del d['principles'][0]['ledger']['Modules/M50']; cases.append(d)
    d = sample(); f = d['principles'][0]['findings'][0]; f['kind'] = 'suggestion'; d['principles'][0]['ledger']['Modules/M0']['status'] = 'clear'; cases.append(d)
    d = sample(); cases.append(principle(d, 'P3'))
    d = sample(severity='medium'); cases.append(principle(d, 'P3', [finding('p3-other', ['Modules/M0', 'Modules/M7'], 'high')]))
    d = sample(); d['principles'].append({'id': 'P7', 'scoring_scope': 'external-only', 'enforcement_cases': [{'id': 'edge-rule', 'family': 'Imports', 'outcome': 'failed', 'evidence': ['probe']}], 'findings': []}); cases.append(d)
    d = sample(); d['principles'].append({'id': 'P8', 'skipped': True}); cases.append(d)
    d = sample(); d['excluded_modules'] = [{'module': m, 'reason': 'Scope'} for m in d['modules']]; cases.append(d)
    d = sample(); d['module_weights'] = {m: (i % 7) * 13 + 1 for i, m in enumerate(d['modules'])}; cases.append(d)
    d = sample(severity='medium'); d['module_weights'] = {m: 500 if i == 0 else 3 for i, m in enumerate(d['modules'])}
    d['excluded_modules'] = [{'module': 'Modules/M2', 'reason': 'Scope'}]; cases.append(d)
    hub = [candidate('C-hub-1', ['Modules/M0']), candidate('C-mono-1', ['Modules/M5'], 'monolithic-module', 'medium'), candidate('C-par-1', ['Modules/M9'], 'parallel-abstractions', 'medium')]
    d = structural(sample(severity='medium'), hub, {'C-hub-1': {'status': 'confirmed', 'finding': 'p1-hub'}, 'C-mono-1': {'status': 'dismissed', 'reason': 'Composition only', 'evidence': ['App.swift:1']}},
                   [finding('p1-hub', ['Modules/M0'], 'high', archetype='contamination-hub', candidate_ids=['C-hub-1'])])
    d['principles'].append({'id': 'P5', 'skipped': True}); cases.append(d)
    d = copy.deepcopy(d); d['structural']['resolutions'].pop('C-mono-1'); cases.append(d)
    d = principle(sample(), 'P7', [finding('p7-a', ['Modules/M3'], 'high')]); principle(d, 'P5', [finding('p5-b', ['Modules/M3'], 'medium'), finding('p5-c', ['Modules/M3'], 'low')]); cases.append(d)
    d = copy.deepcopy(d); d['decisions'] = {'p7-a': {'status': 'invalid', 'decided_by': 'user'}}; cases.append(d)
    d = sample(severity='high'); d['principles'][0]['findings'][0]['implementation_only'] = True; cases.append(d)
    return cases


class AuditTests(unittest.TestCase):
    def test_defect_owner_counts_even_without_consumers(self):
        s = score(sample(severity='high', affected=0))
        self.assertAlmostEqual(s['risk']['score'], 1 / 100); self.assertEqual(s['principles'][0]['affectedModules'], 0)

    def test_risk_is_the_weighted_share_of_involved_modules(self):
        s = score(sample(affected=20)); self.assertEqual(s['principles'][0]['affectedModules'], 20)
        self.assertAlmostEqual(s['risk']['score'], .1 * 21 / 100); self.assertEqual(s['risk']['involved_modules'], 21); self.assertEqual(s['risk']['band'], 'LOW')
        s = score(sample(severity='medium', affected=33)); self.assertAlmostEqual(s['risk']['score'], .4 * 34 / 100); self.assertEqual(s['risk']['band'], 'HIGH')

    def test_code_mass_does_not_weight_the_score(self):
        d = sample(severity='medium', affected=5); base = score(d)['risk']['score']
        d['module_weights'] = {m: 1000 if i == 0 else 1 for i, m in enumerate(d['modules'])}
        self.assertEqual(score(d)['risk']['score'], base)

    def test_exact_bands(self):
        for affected, expected in [(1, 'LOW'), (2, 'MEDIUM'), (8, 'MEDIUM'), (9, 'HIGH')]:
            self.assertEqual(score(sample(severity='high', affected=affected))['risk']['band'], expected, affected)

    def test_each_module_counts_once_at_its_strongest_defect(self):
        d = plain(); d['principles'][0]['findings'].append(finding('second', ['M0'], 'medium'))
        self.assertAlmostEqual(score(d)['risk']['score'], 1 / 2)
        principle(d, 'P3', [finding('p3', ['M0', 'M1'], 'medium')])
        s = score(d); self.assertAlmostEqual(s['risk']['score'], (1 + .4) / 2); self.assertEqual(s['risk']['involved_modules'], 2)
        self.assertAlmostEqual(s['principles'][0]['risk']['score'], 1 / 2); self.assertAlmostEqual(s['principles'][1]['risk']['score'], .4)

    def test_cross_tagged_finding_counts_once(self):
        d = plain(); same = copy.deepcopy(d['principles'][0]['findings'][0]); principle(d, 'P3', [same])
        self.assertAlmostEqual(score(d)['risk']['score'], 1 / 2)

    def test_unresolved_candidates_withhold_the_score_and_mark_their_principle(self):
        d = structural(sample(), [candidate('C-hub-1', ['Modules/M0'])], {}, [])
        s = score(d); self.assertIsNone(s['risk']['score']); self.assertEqual(s['risk']['withheld'], 'structural candidates unresolved')
        self.assertEqual([p['gate'] for p in s['principles']], ['incomplete', 'pass']); self.assertEqual(s['overall_gate'], 'incomplete')
        d['structural']['resolutions'] = {'C-hub-1': {'status': 'dismissed', 'reason': 'Stable value module', 'evidence': ['Ids.swift:4']}}
        s = score(d); self.assertIsNotNone(s['risk']['score']); self.assertEqual(s['structural']['dismissed'], ['C-hub-1'])

    def test_candidates_of_skipped_principles_are_out_of_review(self):
        d = structural(sample(), [candidate('C-par-1', ['Modules/M0'], 'parallel-abstractions', 'medium')], {}, [])
        d['principles'].append({'id': 'P5', 'skipped': True})
        s = score(d); self.assertIsNotNone(s['risk']['score']); self.assertEqual(s['structural']['skipped'], ['C-par-1'])

    def test_confirmed_candidate_requires_owner_finding_and_floor(self):
        d = structural(sample(), [candidate('C-hub-1', ['Modules/M0'])], {'C-hub-1': {'status': 'confirmed', 'finding': 'p1-hub'}},
                       [finding('p1-hub', ['Modules/M0'], 'medium', archetype='contamination-hub', candidate_ids=['C-hub-1'])])
        with self.assertRaises(ValueError): score(d)
        d['principles'][0]['findings'][0]['floor_override_reason'] = 'Only value types leak; consumers never change with it'
        s = score(d); self.assertEqual(s['principles'][0]['findings'][0]['severity_floor'], 'high'); self.assertTrue(s['ranking'][0]['structural'])
        d['structural']['resolutions']['C-hub-1']['finding'] = 'unit-contract'
        with self.assertRaisesRegex(ValueError, 'P1 finding'): score(d)

    def test_implementation_only_defect_exposes_its_owner_only(self):
        d = sample(severity='high', affected=30); d['principles'][0]['findings'][0]['implementation_only'] = True
        s = score(d); self.assertAlmostEqual(s['risk']['score'], 1 / 100); self.assertEqual(s['principles'][0]['affectedModules'], 0)

    def test_reject_invalid_structural_records(self):
        bad = []
        bad.append(structural(sample(), [candidate('C-1', ['Modules/M0'])], {'C-1': {'status': 'dismissed', 'reason': 'No evidence'}}, []))
        bad.append(structural(sample(), [candidate('C-1', ['Missing'])], {}, []))
        bad.append(structural(sample(), [candidate('C-1', ['Modules/M0'], archetype='vibes')], {}, []))
        d = sample(); d['principles'].append({'id': 'S', 'findings': []}); bad.append(d)
        for d in bad:
            with self.assertRaises(ValueError): score(d)

    def test_no_reason_choices_and_reopen(self):
        for status in ['resolved', 'invalid', 'accepted', 'intended']:
            d = sample(severity='high'); d['decisions'] = {'unit-contract': {'status': status}}
            s = score(d); self.assertEqual(s['risk']['score'], 0); self.assertAlmostEqual(s['observed_risk']['score'], 21 / 100); self.assertEqual(s['rootCostModules'], 0)
            self.assertEqual(s['principles'][0]['counts']['issue'], 1)
            d['decisions']['unit-contract']['status'] = 'open'; self.assertAlmostEqual(score(d)['risk']['score'], 21 / 100)

    def test_shared_root_still_has_open_issue(self):
        d = sample(); f = copy.deepcopy(d['principles'][0]['findings'][0]); f['id'] = 'second'; d['principles'][0]['findings'].append(f)
        d['decisions'] = {'unit-contract': {'status': 'accepted', 'reason': 'Choice', 'decided_by': 'user'}}
        s = score(d); self.assertEqual(s['rootCostModules'], 1); self.assertAlmostEqual(s['risk']['score'], .021)

    def test_scope_filters_roots_consumers_and_denominator(self):
        d = sample(n=10, affected=2); d['excluded_modules'] = [{'module': 'Modules/M1', 'reason': 'Scope'}]
        s = score(d); self.assertEqual(s['total'], 9); self.assertEqual(s['affectedModules'], 1); self.assertAlmostEqual(s['risk']['score'], .1 * 2 / 9)
        d['excluded_modules'].append({'module': 'Modules/M0', 'reason': 'Scope'}); s = score(d); self.assertEqual(s['risk']['score'], 0); self.assertFalse(s['principles'][0]['findings'][0]['in_scope'])

    def test_external_enforcement_stays_out_of_risk(self):
        d = sample(); d['principles'].append({'id': 'P7', 'scoring_scope': 'external-only', 'findings': [], 'enforcement_cases': [{'id': 'rule', 'family': 'Edges', 'outcome': 'failed', 'evidence': ['probe']}]})
        s = score(d); self.assertEqual(s['principles'][1]['external_enforcement']['failed'], 1); self.assertIsNone(s['principles'][1]['rootCostModules']); self.assertEqual(s['risk']['included_principles'], ['P2'])

    def test_missing_authority_is_unknown(self):
        d = sample(); d.pop('consumer_graph_provenance'); s = score(d); self.assertIsNone(s['risk']['score']); self.assertEqual(s['overall_gate'], 'incomplete')

    def test_unknown_is_not_zero(self):
        d = sample(); d['consumer_graph_complete'] = False; s = score(d); self.assertIsNone(s['risk']['score']); self.assertEqual(s['overall_gate'], 'incomplete')
        d = sample(); del d['principles'][0]['ledger']['Modules/M99']; s = score(d); self.assertEqual(s['overall_gate'], 'pass'); self.assertFalse(s['risk']['coverage_complete'])
        self.assertAlmostEqual(s['risk']['coverage_min'], .99)

    def test_unscreened_audit_is_flagged(self):
        s = score(sample()); self.assertFalse(s['structural']['screened'])

    def test_suggestion_is_unscored(self):
        d = sample(severity='high'); d['principles'][0]['findings'][0]['kind'] = 'suggestion'; d['principles'][0]['ledger']['Modules/M0']['status'] = 'clear'
        s = score(d); self.assertEqual(s['risk']['score'], 0); self.assertEqual(s['rootCostModules'], 0); self.assertEqual(s['overall_gate'], 'pass')

    def test_reject_bad_decisions_scope_and_cross_tags(self):
        bad = []
        d = sample(); d['decisions'] = {'unit-contract': {'status': 'unknown'}}; bad.append(d)
        d = sample(); d['decisions'] = {'unit-contract': {'status': 'accepted', 'reason': 'Reason', 'decided_by': 'agent'}}; bad.append(d)
        d = sample(); d['decisions'] = {'missing': {'status': 'open'}}; bad.append(d)
        d = sample(); d['excluded_modules'] = [{'module': 'Missing', 'reason': 'Scope'}]; bad.append(d)
        d = sample(); p = copy.deepcopy(d['principles'][0]); p['id'] = 'P3'; p['findings'][0]['severity'] = 'critical'; d['principles'].append(p); bad.append(d)
        d = sample(); d['thresholds'] = {'high_min': .5}; bad.append(d)
        for d in bad:
            with self.assertRaises(ValueError): score(d)

    def test_tiny_is_strictly_under_two_percent_and_never_high(self):
        for severity, count, expected in [('medium', 3, 'tiny'), ('medium', 4, 'issue'), ('low', 18, 'tiny'), ('low', 19, 'issue'), ('high', 0, 'issue')]:
            d = sample(severity=severity, affected=count); s = score(d); self.assertEqual(s['principles'][0]['findings'][0]['presentation'], expected, (severity, count))
            d['decisions'] = {'unit-contract': {'status': 'resolved'}}; s = score(d); self.assertEqual(s['risk']['score'], 0); self.assertEqual(s['principles'][0]['findings'][0]['presentation'], expected)
        d = sample(); d['consumer_graph_complete'] = False; self.assertEqual(score(d)['principles'][0]['findings'][0]['presentation'], 'issue')

    def test_messy_structure_scores_worse_than_clean_structure(self):
        clean = principle({'modules': [f'M{i}' for i in range(20)], 'consumer_graph_complete': True,
                           'consumer_graph_provenance': {'source': 'fixture'}, 'consumers': {f'M{i}': [] for i in range(20)}, 'principles': []},
                          'P2', [finding(f'p2-{i}', [f'M{i}'], 'low') for i in range(2)])
        messy = {'modules': ['App', 'Core', 'Feature'], 'consumer_graph_complete': True,
                 'consumer_graph_provenance': {'source': 'fixture'}, 'consumers': {'App': [], 'Core': ['App', 'Feature'], 'Feature': ['App']}, 'principles': []}
        messy = structural(principle(messy, 'P2'), [candidate('C-mono', ['App'], 'monolithic-module'), candidate('C-hub', ['Core'])],
                           {'C-mono': {'status': 'confirmed', 'finding': 'p1-mono'}, 'C-hub': {'status': 'confirmed', 'finding': 'p1-hub'}},
                           [finding('p1-mono', ['App'], 'high', archetype='monolithic-module', candidate_ids=['C-mono']),
                            finding('p1-hub', ['Core'], 'high', archetype='contamination-hub', candidate_ids=['C-hub'])])
        self.assertEqual(score(clean)['risk']['band'], 'LOW'); self.assertEqual(score(messy)['risk']['band'], 'HIGH')
        top = score(messy)['ranking'][0]; self.assertEqual((top['id'], top['defect_modules'], top['involved_modules']), ('p1-hub', 1, 3))

    def test_utf8_cli_input_and_output(self):
        data = sample(); data['principles'][0]['findings'][0]['severity_reason'] = 'Unité: 1 → 100%'
        with tempfile.TemporaryDirectory(prefix='audit-utf8-') as folder:
            source = Path(folder) / 'entrée.json'; output = Path(folder) / 'résultat.json'
            source.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            subprocess.check_call([sys.executable, str(Path(__file__).with_name('score_audit.py')), str(source), '--output', str(output)])
            result = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(result['principles'][0]['findings'][0]['severity_reason'], data['principles'][0]['findings'][0]['severity_reason'])

    def test_packaging_escapes_and_is_idempotent(self):
        d = sample(); d['principles'][0]['findings'][0]['severity_reason'] = '</script><script>alert(1)</script>'
        html = '<html><body><section class="scoreboard" id="scores"></section><section id="p2"><details id="unit-contract"><section id="unit-contract-fix"></section><details id="unit-contract-evidence"></details></details></section></body></html>'
        output = prepare(d, html); self.assertEqual(output.count('id="audit-data"'), 1); self.assertNotIn('</script><script>alert(1)</script>', output)
        self.assertEqual(prepare(d, output), output); self.assertIn(identity(d), output); self.assertIn('Risk 2.1% · 21/100 modules involved', output)
        with self.assertRaises(ValueError): prepare(d, '<html><body></body></html>')

    @unittest.skipUnless(shutil.which('node'), 'Node unavailable; browser projection parity not run')
    def test_browser_arithmetic_parity(self):
        cases = scenarios(); asset = Path(__file__).resolve().parent.parent/'assets/report-scoring.js'
        script = "require(process.argv[1]);let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>process.stdout.write(JSON.stringify(JSON.parse(s).map(globalThis.ModularAuditScoring.compute))));"
        browser = json.loads(subprocess.check_output(['node', '-e', script, str(asset)], input=json.dumps(cases).encode()))
        for data, js in zip(cases, browser):
            py = score(data); self.assertEqual(py['overall_gate'], js['overall_gate'])
            for field in ['risk', 'observed_risk']:
                self.assertEqual(py[field]['band'], js[field]['band']); self.assertEqual(py[field]['involved_modules'], js[field]['involved_modules']); self.assertEqual(py[field]['withheld'], js[field]['withheld'])
                if py[field]['score'] is None: self.assertIsNone(js[field]['score'])
                else: self.assertAlmostEqual(py[field]['score'], js[field]['score'])
            self.assertEqual([(r['id'], r['defect_modules'], r['involved_modules']) for r in py['ranking']], [(r['id'], r['defect_modules'], r['involved_modules']) for r in js['ranking']])
            self.assertEqual(py['structural']['unresolved'], js['structural']['unresolved'])
            for p, j in zip(py['principles'], js['principles']):
                self.assertEqual(p['gate'], j['gate'])
                if p['gate'] == 'skipped': continue
                for field in ['rootCostModules', 'affectedModules', 'rootCostModuleIDs', 'affectedModuleIDs', 'counts', 'accepted_findings', 'resolved_findings', 'invalid_findings']:
                    self.assertEqual(p[field], j[field], field)
                if p['coverage'] is None: self.assertIsNone(j['coverage'])
                else: self.assertAlmostEqual(p['coverage'], j['coverage'])
                for field in ['risk', 'observed_risk']:
                    self.assertEqual(p[field]['band'], j[field]['band'])
                    if p[field]['score'] is None: self.assertIsNone(j[field]['score'])
                    else: self.assertAlmostEqual(p[field]['score'], j[field]['score'])
                for f, jf in zip(p['findings'], j['findings']):
                    for field in ['active', 'presentation', 'rootCostModules', 'affectedModules', 'rootCostModuleIDs', 'affectedModuleIDs']:
                        self.assertEqual(f[field], jf[field], field)
                    for field in ['risk', 'observed_risk']:
                        if f[field]['score'] is None: self.assertIsNone(jf[field]['score'])
                        else: self.assertAlmostEqual(f[field]['score'], jf[field]['score'])
        print(f'Python/browser parity: {len(cases)} scenarios')


if __name__ == '__main__': unittest.main()
