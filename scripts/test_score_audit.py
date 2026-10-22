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


def systemic(d, candidates, resolutions, findings):
    d['systemic'] = {'candidates': candidates, 'resolutions': resolutions}
    d['principles'].insert(0, {'id': 'S', 'title': 'Systemic structure', 'findings': findings})
    return d


def candidate(cid, modules, archetype='contamination-hub', floor='high'):
    return {'id': cid, 'archetype': archetype, 'modules': modules, 'severity_floor': floor, 'trigger': 'scan', 'metrics': {}}


def weighted(masses, severity='high'):
    modules = [f'M{i}' for i in range(len(masses))]
    d = {'modules': modules, 'module_weights': dict(zip(modules, masses)), 'consumer_graph_complete': True,
         'consumer_graph_provenance': {'source': 'fixture'}, 'consumers': {m: [] for m in modules}, 'principles': []}
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
    hub = [candidate('S-hub-1', ['Modules/M0']), candidate('S-mono-1', ['Modules/M5'], 'monolithic-module', 'medium')]
    d = systemic(sample(severity='medium'), hub, {'S-hub-1': {'status': 'confirmed', 'finding': 's-hub'}, 'S-mono-1': {'status': 'dismissed', 'reason': 'Composition only', 'evidence': ['App.swift:1']}},
                 [finding('s-hub', ['Modules/M0'], 'high', archetype='contamination-hub', candidate_ids=['S-hub-1'])]); cases.append(d)
    d = copy.deepcopy(d); d['systemic']['resolutions'].pop('S-mono-1'); cases.append(d)
    d = systemic(sample(), [], {}, [finding('s-a', ['Modules/M3'], 'high', archetype='tangled-graph'), finding('s-b', ['Modules/M3'], 'medium', archetype='parallel-abstractions'),
                                   finding('s-c', ['Modules/M3'], 'low', archetype='parallel-abstractions')]); cases.append(d)
    d = copy.deepcopy(d); d['decisions'] = {'s-a': {'status': 'invalid', 'decided_by': 'user'}}; cases.append(d)
    return cases


class AuditTests(unittest.TestCase):
    def test_defect_owner_counts_even_without_consumers(self):
        s = score(sample(severity='high', affected=0))
        self.assertAlmostEqual(s['risk']['score'], .4 / 100); self.assertEqual(s['principles'][0]['affectedModules'], 0)

    def test_exposure_includes_root_and_direct_consumers(self):
        s = score(sample(affected=20)); self.assertEqual(s['principles'][0]['affectedModules'], 20)
        self.assertAlmostEqual(s['risk']['score'], .1 * 21 / 100); self.assertEqual(s['risk']['health'], 98)

    def test_code_mass_drives_risk(self):
        s = score(weighted([60, 10, 10, 10, 10])); self.assertAlmostEqual(s['risk']['score'], .24); self.assertEqual(s['weighting'], 'code-mass')
        s = score(weighted([1, 10, 10, 10, 10])); self.assertLess(s['risk']['score'], .01)

    def test_exact_bands(self):
        for masses, expected in [([1, 4], 'LOW'), ([1, 3], 'MEDIUM'), ([5, 4], 'MEDIUM'), ([5, 3], 'HIGH')]:
            self.assertEqual(score(weighted(masses))['risk']['band'], expected, masses)

    def test_max_within_dimension_and_compound_across_dimensions(self):
        d = weighted([1, 1]); d['principles'][0]['findings'].append(finding('second', ['M0'], 'medium'))
        self.assertAlmostEqual(score(d)['risk']['score'], .4 / 2)
        principle(d, 'P3', [finding('p3', ['M0'], 'medium')])
        s = score(d); self.assertAlmostEqual(s['risk']['score'], (1 - .6 * .8) / 2); self.assertAlmostEqual(s['principles'][0]['risk']['score'], .4 / 2); self.assertAlmostEqual(s['principles'][1]['risk']['score'], .2 / 2)

    def test_cross_tagged_finding_counts_once(self):
        d = weighted([1, 1]); same = copy.deepcopy(d['principles'][0]['findings'][0]); principle(d, 'P3', [same])
        self.assertAlmostEqual(score(d)['risk']['score'], .4 / 2)

    def test_systemic_archetypes_are_separate_dimensions(self):
        d = systemic(weighted([1, 1], 'low'), [], {}, [finding('s-a', ['M1'], 'high', archetype='tangled-graph'),
                     finding('s-b', ['M1'], 'medium', archetype='parallel-abstractions'), finding('s-c', ['M1'], 'low', archetype='parallel-abstractions')])
        s = score(d); self.assertAlmostEqual(s['principles'][0]['risk']['score'], (1 - .6 * .8) / 2)
        self.assertEqual([r['id'] for r in s['ranking']][:2], ['s-a', 's-b'])

    def test_unresolved_candidates_withhold_the_score(self):
        d = systemic(sample(), [candidate('S-hub-1', ['Modules/M0'])], {}, [])
        s = score(d); self.assertIsNone(s['risk']['score']); self.assertEqual(s['risk']['withheld'], 'systemic candidates unresolved')
        self.assertEqual(s['principles'][0]['gate'], 'incomplete'); self.assertEqual(s['overall_gate'], 'incomplete')
        d['systemic']['resolutions'] = {'S-hub-1': {'status': 'dismissed', 'reason': 'Stable value module', 'evidence': ['Ids.swift:4']}}
        s = score(d); self.assertIsNotNone(s['risk']['score']); self.assertEqual(s['systemic']['dismissed'], ['S-hub-1'])

    def test_confirmed_candidate_requires_floor_or_override(self):
        d = systemic(sample(), [candidate('S-hub-1', ['Modules/M0'])], {'S-hub-1': {'status': 'confirmed', 'finding': 's-hub'}},
                     [finding('s-hub', ['Modules/M0'], 'medium', archetype='contamination-hub', candidate_ids=['S-hub-1'])])
        with self.assertRaises(ValueError): score(d)
        d['principles'][0]['findings'][0]['floor_override_reason'] = 'Only value types leak; consumers never change with it'
        self.assertEqual(score(d)['principles'][0]['findings'][0]['severity_floor'], 'high')

    def test_reject_invalid_systemic_records(self):
        bad = []
        bad.append(systemic(sample(), [candidate('S-1', ['Modules/M0'])], {'S-1': {'status': 'dismissed', 'reason': 'No evidence'}}, []))
        bad.append(systemic(sample(), [candidate('S-1', ['Modules/M0'])], {'S-1': {'status': 'confirmed', 'finding': 'unit-contract'}}, []))
        bad.append(systemic(sample(), [candidate('S-1', ['Missing'])], {}, []))
        bad.append(systemic(sample(), [candidate('S-1', ['Modules/M0'], archetype='vibes')], {}, []))
        d = sample(); d['systemic'] = {'candidates': [candidate('S-1', ['Modules/M0'])], 'resolutions': {}}; d['principles'].append({'id': 'S', 'skipped': True}); bad.append(d)
        for d in bad:
            with self.assertRaises(ValueError): score(d)

    def test_module_weights_must_cover_inventory(self):
        for weights in [{'M0': 1}, {'M0': -1, 'M1': 1}, {'M0': True, 'M1': 1}, {'M0': 0, 'M1': 0}]:
            d = weighted([1, 1]); d['module_weights'] = weights
            with self.assertRaises(ValueError): score(d)

    def test_no_reason_choices_and_reopen(self):
        for status in ['resolved', 'invalid', 'accepted', 'intended']:
            d = sample(severity='high'); d['decisions'] = {'unit-contract': {'status': status}}
            s = score(d); self.assertEqual(s['risk']['score'], 0); self.assertAlmostEqual(s['observed_risk']['score'], .4 * 21 / 100); self.assertEqual(s['rootCostModules'], 0)
            self.assertEqual(s['principles'][0]['counts']['issue'], 1)
            d['decisions']['unit-contract']['status'] = 'open'; self.assertAlmostEqual(score(d)['risk']['score'], .4 * 21 / 100)

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
        self.assertAlmostEqual(s['risk']['assessed_mass_min'], .99)

    def test_unscreened_audit_is_flagged(self):
        s = score(sample()); self.assertFalse(s['systemic']['screened'])

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

    def test_tiny_is_strictly_under_one_percent_and_stable_after_review(self):
        for severity, count, expected in [('high', 1, 'tiny'), ('high', 2, 'issue'), ('low', 8, 'tiny'), ('low', 9, 'issue')]:
            d = sample(severity=severity, affected=count); s = score(d); self.assertEqual(s['principles'][0]['findings'][0]['presentation'], expected, (severity, count))
            d['decisions'] = {'unit-contract': {'status': 'resolved'}}; s = score(d); self.assertEqual(s['risk']['score'], 0); self.assertEqual(s['principles'][0]['findings'][0]['presentation'], expected)
        d = sample(); d['consumer_graph_complete'] = False; self.assertEqual(score(d)['principles'][0]['findings'][0]['presentation'], 'issue')

    def test_messy_structure_scores_worse_than_clean_structure(self):
        clean = principle({'modules': [f'M{i}' for i in range(20)], 'module_weights': {f'M{i}': 5 for i in range(20)}, 'consumer_graph_complete': True,
                           'consumer_graph_provenance': {'source': 'fixture'}, 'consumers': {f'M{i}': [] for i in range(20)}, 'principles': []},
                          'P2', [finding(f'p2-{i}', [f'M{i}'], 'medium') for i in range(4)])
        messy = {'modules': ['App', 'Core', 'Feature'], 'module_weights': {'App': 70, 'Core': 20, 'Feature': 10}, 'consumer_graph_complete': True,
                 'consumer_graph_provenance': {'source': 'fixture'}, 'consumers': {'App': [], 'Core': ['App', 'Feature'], 'Feature': ['App']}, 'principles': []}
        messy = systemic(principle(messy, 'P2'), [candidate('S-mono', ['App'], 'monolithic-module'), candidate('S-hub', ['Core'])],
                         {'S-mono': {'status': 'confirmed', 'finding': 's-mono'}, 'S-hub': {'status': 'confirmed', 'finding': 's-hub'}},
                         [finding('s-mono', ['App'], 'high', archetype='monolithic-module', candidate_ids=['S-mono']),
                          finding('s-hub', ['Core'], 'high', archetype='contamination-hub', candidate_ids=['S-hub'])])
        self.assertGreater(score(clean)['risk']['health'], 90); self.assertLess(score(messy)['risk']['health'], 60)
        self.assertEqual(score(messy)['ranking'][0]['id'], 's-hub')

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
        self.assertEqual(prepare(d, output), output); self.assertIn(identity(d), output); self.assertIn('Architecture health', output)
        with self.assertRaises(ValueError): prepare(d, '<html><body></body></html>')

    @unittest.skipUnless(shutil.which('node'), 'Node unavailable; browser projection parity not run')
    def test_browser_arithmetic_parity(self):
        cases = scenarios(); asset = Path(__file__).resolve().parent.parent/'assets/report-scoring.js'
        script = "require(process.argv[1]);let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>process.stdout.write(JSON.stringify(JSON.parse(s).map(globalThis.ModularAuditScoring.compute))));"
        browser = json.loads(subprocess.check_output(['node', '-e', script, str(asset)], input=json.dumps(cases).encode()))
        for data, js in zip(cases, browser):
            py = score(data); self.assertEqual(py['overall_gate'], js['overall_gate'])
            for field in ['risk', 'observed_risk']:
                self.assertEqual(py[field]['band'], js[field]['band']); self.assertEqual(py[field]['health'], js[field]['health']); self.assertEqual(py[field]['withheld'], js[field]['withheld'])
                if py[field]['score'] is None: self.assertIsNone(js[field]['score'])
                else: self.assertAlmostEqual(py[field]['score'], js[field]['score'])
            self.assertEqual([r['id'] for r in py['ranking']], [r['id'] for r in js['ranking']])
            self.assertEqual(py['systemic']['unresolved'], js['systemic']['unresolved'])
            for p, j in zip(py['principles'], js['principles']):
                self.assertEqual(p['gate'], j['gate'])
                if p['gate'] == 'skipped': continue
                for field in ['rootCostModules', 'affectedModules', 'rootCostModuleIDs', 'affectedModuleIDs', 'counts', 'accepted_findings', 'resolved_findings', 'invalid_findings']:
                    self.assertEqual(p[field], j[field], field)
                if p['assessed_mass'] is None: self.assertIsNone(j['assessed_mass'])
                else: self.assertAlmostEqual(p['assessed_mass'], j['assessed_mass'])
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
