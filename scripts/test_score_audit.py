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


def sample(n=100, severity='low', affected=20, pid='P2'):
    modules = [f'Modules/M{i}' for i in range(n)]
    f = {'id': 'unit-contract', 'kind': 'issue', 'severity': severity, 'severity_reason': 'Traced consumer consequence',
         'rootCostModuleIDs': [modules[0]], 'reach_modules': modules[1:affected+1], 'external_scopes': [], 'evidence': ['Sources/Contract.swift:12']}
    ledger = {m: {'status': 'issue' if m == modules[0] else 'clear', 'basis': 'Traced contract'} for m in modules}
    return {'modules': modules, 'consumer_graph_complete': True, 'consumer_graph_provenance': {'source': 'Frozen fixture imports'}, 'consumers': {m: modules[1:affected+1] if i == 0 else [] for i, m in enumerate(modules)},
            'principles': [{'id': pid, 'findings': [f], 'ledger': ledger}]}


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
    d = sample(); p = copy.deepcopy(d['principles'][0]); p.update(id='P3', findings=[]); p['ledger']['Modules/M0']['status'] = 'clear'; d['principles'].append(p); cases.append(d)
    d = sample(); d['principles'].append({'id': 'P7', 'scoring_scope': 'external-only', 'enforcement_cases': [{'id': 'edge-rule', 'family': 'Imports', 'outcome': 'failed', 'evidence': ['probe']}], 'findings': []}); cases.append(d)
    d = sample(); d['principles'].append({'id': 'P8', 'skipped': True}); cases.append(d)
    d = sample(); d['excluded_modules'] = [{'module': m, 'reason': 'Scope'} for m in d['modules']]; cases.append(d)
    return cases


class AuditTests(unittest.TestCase):
    def test_minor_clarity_is_not_full_blast_radius_risk(self):
        s = score(sample()); self.assertEqual(s['principles'][0]['affectedModules'], 20)
        self.assertEqual(s['risk']['percent'], 2); self.assertEqual(s['overall_gate'], 'pass')

    def test_exact_bands(self):
        for count, band in [(2, 'LOW'), (3, 'MEDIUM'), (9, 'MEDIUM'), (10, 'HIGH')]:
            s = score(sample(severity='high', affected=count)); self.assertEqual(s['risk']['band'], band)

    def test_max_weight_on_shared_consumers(self):
        d = sample(n=10, affected=3); p = d['principles'][0]
        other = copy.deepcopy(p['findings'][0]); other.update(id='other', severity='medium', rootCostModuleIDs=['Modules/M5'])
        p['findings'].append(other); p['ledger']['Modules/M5']['status'] = 'issue'; d['consumers']['Modules/M5'] = ['Modules/M2', 'Modules/M3', 'Modules/M4']
        s = score(d)['principles'][0]; self.assertEqual(s['affectedModules'], 4); self.assertAlmostEqual(s['risk']['score'], .13)

    def test_mean_includes_zero_risk_principles(self):
        d = sample(severity='high', affected=10); p = copy.deepcopy(d['principles'][0]); p.update(id='P3', findings=[]); p['ledger']['Modules/M0']['status'] = 'clear'; d['principles'].append(p)
        s = score(d); self.assertEqual(s['risk']['percent'], 5); self.assertEqual(s['overall_gate'], 'watch')

    def test_no_reason_choices_and_reopen(self):
        for status in ['resolved', 'invalid', 'accepted', 'intended']:
            d = sample(severity='high'); d['decisions'] = {'unit-contract': {'status': status}}
            s = score(d); self.assertEqual(s['risk']['score'], 0); self.assertEqual(s['observed_risk']['score'], .2); self.assertEqual(s['rootCostModules'], 0)
            self.assertEqual(s['principles'][0]['counts']['issue'], 1)
            d['decisions']['unit-contract']['status'] = 'open'; self.assertEqual(score(d)['risk']['score'], .2)

    def test_shared_root_still_has_open_issue(self):
        d = sample(); f = copy.deepcopy(d['principles'][0]['findings'][0]); f['id'] = 'second'; d['principles'][0]['findings'].append(f)
        d['decisions'] = {'unit-contract': {'status': 'accepted', 'reason': 'Choice', 'decided_by': 'user'}}
        s = score(d); self.assertEqual(s['rootCostModules'], 1); self.assertEqual(s['risk']['score'], .02)

    def test_scope_filters_roots_consumers_and_denominator(self):
        d = sample(n=10, affected=2); d['excluded_modules'] = [{'module': 'Modules/M1', 'reason': 'Scope'}]
        s = score(d); self.assertEqual(s['total'], 9); self.assertEqual(s['affectedModules'], 1); self.assertAlmostEqual(s['risk']['score'], .1/9)
        d['excluded_modules'].append({'module': 'Modules/M0', 'reason': 'Scope'}); s = score(d); self.assertEqual(s['risk']['score'], 0); self.assertFalse(s['principles'][0]['findings'][0]['in_scope'])

    def test_check_failures_do_not_override_overall_risk(self):
        d = sample(severity='critical', affected=0); d['decisions'] = {'unit-contract': {'status': 'intended', 'reason': 'Choice', 'decided_by': 'user'}}
        self.assertEqual(score(d)['overall_gate'], 'pass')
        d = sample(); d['principles'].append({'id': 'P7', 'scoring_scope': 'external-only', 'findings': [], 'enforcement_cases': [{'id': 'rule', 'family': 'Edges', 'outcome': 'failed', 'evidence': ['probe']}]})
        s = score(d); self.assertEqual(s['overall_gate'], 'pass'); self.assertEqual(s['principles'][1]['external_enforcement']['failed'], 1); self.assertIsNone(s['principles'][1]['rootCostModules']); self.assertEqual(s['risk']['included_principles'], ['P2'])

    def test_missing_authority_is_unknown(self):
        d = sample(); d.pop('consumer_graph_provenance'); s = score(d); self.assertIsNone(s['risk']['score']); self.assertEqual(s['overall_gate'], 'incomplete')

    def test_unknown_is_not_zero(self):
        d = sample(); d['consumer_graph_complete'] = False; s = score(d); self.assertIsNone(s['risk']['score']); self.assertEqual(s['overall_gate'], 'incomplete')
        d = sample(); del d['principles'][0]['ledger']['Modules/M99']; s = score(d); self.assertEqual(s['overall_gate'], 'pass'); self.assertFalse(s['risk']['coverage_complete'])

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
        for d in bad:
            with self.assertRaises(ValueError): score(d)

    def test_two_percent_overall_passes_despite_local_fail(self):
        d = sample(severity='high', affected=16)
        for pid in ['P1', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8']:
            p = copy.deepcopy(d['principles'][0]); p.update(id=pid, findings=[]); p['ledger']['Modules/M0']['status'] = 'clear'; d['principles'].append(p)
        s = score(d); self.assertEqual(s['risk']['percent'], 2); self.assertEqual(s['overall_gate'], 'pass'); self.assertEqual(s['principles'][0]['gate'], 'fail')

    def test_overall_ten_percent_boundary(self):
        for reach, gate in [(198, 'watch'), (200, 'fail')]:
            d = sample(n=1000, severity='high', affected=reach); p = copy.deepcopy(d['principles'][0]); p.update(id='P3', findings=[]); p['ledger']['Modules/M0']['status'] = 'clear'; d['principles'].append(p)
            self.assertEqual(score(d)['overall_gate'], gate)

    def test_tiny_is_strictly_under_two_percent_and_stable_after_review(self):
        for severity, count, expected in [('high', 1, 'tiny'), ('high', 2, 'issue'), ('low', 19, 'tiny'), ('low', 20, 'issue')]:
            d = sample(severity=severity, affected=count); s = score(d); self.assertEqual(s['principles'][0]['findings'][0]['presentation'], expected)
            d['decisions'] = {'unit-contract': {'status': 'resolved'}}; s = score(d); self.assertEqual(s['risk']['score'], 0); self.assertEqual(s['principles'][0]['findings'][0]['presentation'], expected)
        d = sample(); d['consumer_graph_complete'] = False; self.assertEqual(score(d)['principles'][0]['findings'][0]['presentation'], 'issue')

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
        self.assertEqual(prepare(d, output), output); self.assertIn(identity(d), output)
        with self.assertRaises(ValueError): prepare(d, '<html><body></body></html>')

    @unittest.skipUnless(shutil.which('node'), 'Node unavailable; browser projection parity not run')
    def test_browser_arithmetic_parity(self):
        cases = scenarios(); asset = Path(__file__).resolve().parent.parent/'assets/report-scoring.js'
        script = "require(process.argv[1]);let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>process.stdout.write(JSON.stringify(JSON.parse(s).map(globalThis.ModularAuditScoring.compute))));"
        browser = json.loads(subprocess.check_output(['node', '-e', script, str(asset)], input=json.dumps(cases).encode()))
        for data, js in zip(cases, browser):
            py = score(data); self.assertEqual(py['overall_gate'], js['overall_gate'])
            self.assertEqual(py['risk']['band'], js['risk']['band'])
            if py['risk']['score'] is None: self.assertIsNone(js['risk']['score'])
            else: self.assertAlmostEqual(py['risk']['score'], js['risk']['score'])
            for p, j in zip(py['principles'], js['principles']):
                self.assertEqual(p['gate'], j['gate'])
                if p['gate'] == 'skipped': continue
                for field in ['rootCostModules', 'affectedModules', 'rootCostModuleIDs', 'affectedModuleIDs', 'counts', 'accepted_findings', 'resolved_findings', 'invalid_findings']:
                    self.assertEqual(p[field], j[field], field)
                for field in ['risk', 'observed_risk']:
                    self.assertEqual(p[field]['band'], j[field]['band'])
                    if p[field]['score'] is None: self.assertIsNone(j[field]['score'])
                    else: self.assertAlmostEqual(p[field]['score'], j[field]['score'])
                for f, jf in zip(p['findings'], j['findings']):
                    for field in ['active', 'presentation', 'rootCostModules', 'affectedModules', 'rootCostModuleIDs', 'affectedModuleIDs']:
                        self.assertEqual(f[field], jf[field], field)
        print(f'Python/browser parity: {len(cases)} scenarios')


if __name__ == '__main__': unittest.main()
