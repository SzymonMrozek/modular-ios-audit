#!/usr/bin/env python3
"""Score audit consequence and reach separately; retain evidence, scope and user decisions."""
import argparse
from fractions import Fraction
import json
from pathlib import Path

POLICY = 'overall-risk-and-simple-review-v5'
STATES = {'issue', 'clear', 'not-applicable', 'unassessed'}
WEIGHTS = {'low': Fraction(1, 10), 'medium': Fraction(2, 5), 'high': Fraction(1), 'critical': Fraction(1)}
SEVERITIES = set(WEIGHTS)
PRINCIPLES = {f'P{i}' for i in range(1, 9)}
DECISIONS = {'open', 'resolved', 'invalid', 'accepted'}


def numeric(value, **extra):
    return {'score': float(value) if value is not None else None,
            'percent': float(value * 100) if value is not None else None,
            'band': None if value is None else 'LOW' if value < Fraction(3, 100) else 'MEDIUM' if value < Fraction(1, 10) else 'HIGH', **extra}


def score(data):
    modules = data['modules']
    if not modules or len(modules) != len(set(modules)):
        raise ValueError('Module inventory must be nonempty and unique')
    inventory = set(modules)
    if 'thresholds' in data:
        raise ValueError('Policy fixes 3%/10% bands; remove custom or legacy thresholds')
    exclusions = data.get('excluded_modules', [])
    excluded = set()
    for row in exclusions:
        if row.get('module') not in inventory or row['module'] in excluded or not str(row.get('reason', '')).strip():
            raise ValueError('Exclusions require unique inventory module IDs and reasons')
        excluded.add(row['module'])
    eligible = inventory - excluded
    consumers = data.get('consumers', {})
    if not isinstance(consumers, dict) or not set(consumers) <= inventory:
        raise ValueError('Consumer graph must map inventoried owners to module lists')
    for owner, names in consumers.items():
        if not isinstance(names, list) or len(names) != len(set(names)) or not set(names) <= inventory or owner in names:
            raise ValueError('Invalid direct unique consumers: ' + owner)
    provenance = data.get('consumer_graph_provenance', {})
    authority = isinstance(provenance, dict) and any(isinstance(provenance.get(k), str) and provenance[k].strip() for k in ('source', 'authority'))
    complete = eligible <= set(consumers) and data.get('consumer_graph_complete') is True and bool(authority)
    decisions = {}
    for fid, original in data.get('decisions', {}).items():
        decision = dict(original)
        if decision.get('status') == 'intended':
            decision['status'] = 'accepted'
        if decision.get('status') not in DECISIONS or decision['status'] != 'open' and decision.get('decided_by', 'user') != 'user':
            raise ValueError('Decisions require a supported status and user input: ' + fid)
        decisions[fid] = decision

    def root_ids(f):
        roots = f.get('rootCostModuleIDs', f.get('observed_modules'))
        if not isinstance(roots, list) or len(roots) != len(set(roots)) or not set(roots) <= inventory:
            raise ValueError('Invalid root-cost module IDs: ' + f['id'])
        if 'observed_modules' in f and 'rootCostModuleIDs' in f and set(f['observed_modules']) != set(roots):
            raise ValueError('Disagreeing legacy and canonical roots: ' + f['id'])
        return roots

    def metrics(roots, external=False):
        roots = sorted(set(roots) & eligible)
        available = complete and not external and bool(eligible)
        affected = sorted(set().union(*(set(consumers[r]) & eligible for r in roots))) if available else None
        value = Fraction(len(affected), len(eligible)) if available else None
        return {'rootCostModules': None if external else len(roots), 'rootCostModuleIDs': roots,
                'affectedModules': len(affected) if available else None, 'affectedModuleIDs': affected,
                'impact': numeric(value, scope='external-only' if external else 'module', total_modules=len(eligible),
                    graph_inventory_complete=complete, missing_root_graph=[r for r in roots if r not in consumers],
                    meaning='Direct import exposure; not consequence or architecture health')}

    def risk(findings, external=False):
        if external or not eligible or not complete:
            return numeric(None, weighted_affected_units=None, method='max consequence weight per affected module / eligible modules')
        weights = {}
        for f in findings:
            for root in set(root_ids(f)) & eligible:
                for module in set(consumers[root]) & eligible:
                    weights[module] = max(weights.get(module, Fraction()), WEIGHTS[f['severity']])
        return numeric(sum(weights.values(), Fraction()) / len(eligible), weighted_affected_units=int(sum(weights.values(), Fraction()) * 10), method='max consequence weight per affected module / eligible modules')

    results, seen, records, all_open, all_observed = [], set(), {}, set(), set()
    for p in data['principles']:
        pid = p['id']
        if pid not in PRINCIPLES or pid in seen:
            raise ValueError('Unknown or duplicate principle: ' + pid)
        seen.add(pid)
        if p.get('skipped'):
            if any(p.get(k) for k in ('findings', 'ledger', 'hard_gates', 'check_unknowns', 'enforcement_cases', 'scoring_scope')):
                raise ValueError('Skipped principle cannot contain assessment results: ' + pid)
            results.append({'id': pid, 'gate': 'skipped'})
            continue
        if p.get('scoring_scope', 'module') not in ('module', 'external-only'):
            raise ValueError('Unknown scoring scope: ' + pid)
        findings = p.get('findings', [])
        local_ids, owner_union, rows = set(), set(), []
        observed_findings, open_findings = [], []
        for f in findings:
            fid = f['id']
            if fid in local_ids:
                raise ValueError('Duplicate finding: ' + fid)
            local_ids.add(fid)
            roots = root_ids(f)
            canonical = {k: v for k, v in f.items() if k != 'observed_modules'}
            canonical['rootCostModuleIDs'] = sorted(roots)
            if fid in records and records[fid] != canonical:
                raise ValueError('Conflicting cross-principle finding: ' + fid)
            records[fid] = canonical
            kind = f.get('kind', 'issue')
            if kind not in ('issue', 'suggestion') or f['severity'] not in SEVERITIES:
                raise ValueError('Unknown finding kind or severity: ' + fid)
            if not f.get('severity_reason') or not f.get('evidence') or 'external_scopes' not in f:
                raise ValueError('Finding requires severity reason, evidence and explicit external scopes')
            reach = f['reach_modules']
            if len(reach) != len(set(reach)) or not set(reach) <= inventory:
                raise ValueError('Invalid consumer reach: ' + fid)
            if not roots and not f['external_scopes']:
                raise ValueError('Finding needs root-cost modules or external scope')
            decision = decisions.get(fid, {'status': 'open'})
            in_scope = bool(set(roots) & eligible) or not roots and bool(f['external_scopes'])
            if kind == 'issue':
                owner_union.update(roots)
                if in_scope:
                    observed_findings.append(f)
                    if decision['status'] == 'open':
                        open_findings.append(f)
            external = not roots and bool(f['external_scopes'])
            active = in_scope and kind == 'issue' and decision['status'] == 'open'
            fm = metrics(roots if active else [], external)
            original_risk = risk([f] if kind == 'issue' and in_scope else [], external)
            presentation = 'suggestion' if kind == 'suggestion' else 'tiny' if original_risk['score'] is not None and Fraction(original_risk['weighted_affected_units'], 10 * len(eligible)) < Fraction(2, 100) else 'issue'
            rows.append({'id': fid, 'kind': kind, 'presentation': presentation, 'severity': f['severity'], 'severity_reason': f['severity_reason'],
                         'decision': decision, 'in_scope': in_scope, 'active': active, 'observed': metrics(roots if in_scope and kind == 'issue' else [], external),
                         'consequence_weight': float(WEIGHTS[f['severity']]) if kind == 'issue' else 0,
                         **fm, 'risk': risk([f] if kind == 'issue' and in_scope and decision['status'] == 'open' else [], external),
                         'observed_risk': original_risk})
        external = p.get('scoring_scope') == 'external-only' or bool(findings) and all(not root_ids(f) for f in findings)
        if external and owner_union:
            raise ValueError('External-only scope cannot contain module defects: ' + pid)
        ledger = p.get('ledger', {})
        if not set(ledger) <= inventory or any(row.get('status') not in STATES or not row.get('basis') for row in ledger.values()):
            raise ValueError('Invalid ledger classifications: ' + pid)
        if {m for m, row in ledger.items() if row['status'] == 'issue'} != owner_union:
            raise ValueError('Issue ledger must equal evidenced issue-owner union; suggestions are not defects: ' + pid)
        counts = {state: sum(ledger.get(m, {}).get('status', 'unassessed') == state for m in eligible) for state in sorted(STATES)}
        applicable = len(eligible) - counts['not-applicable']
        hard = p.get('hard_gates', [])
        if any(not all(row.get(k) for k in ('id', 'reason', 'evidence')) for row in hard):
            raise ValueError('Hard gate requires id, reason and evidence')
        cases, case_ids, families = p.get('enforcement_cases', []), set(), set()
        for case in cases:
            if not all(case.get(k) for k in ('id', 'family', 'outcome', 'evidence')) or case['outcome'] not in ('passed', 'failed', 'unknown') or case['id'] in case_ids or case['family'] in families:
                raise ValueError('Invalid/duplicate enforcement family: ' + pid)
            case_ids.add(case['id']); families.add(case['family'])
        enforcement = {'evaluated_families': len(cases), **{state: sum(c['outcome'] == state for c in cases) for state in ('failed', 'passed', 'unknown')}, 'cases': cases}
        open_roots = set().union(*(set(root_ids(f)) & eligible for f in open_findings))
        observed_roots = owner_union & eligible
        current_risk, observed_risk = risk(open_findings, external), risk(observed_findings, external)
        attention = bool(hard or enforcement['failed'] or any(f['severity'] == 'critical' for f in open_findings))
        if current_risk['band'] == 'HIGH':
            gate = 'fail'
        elif p.get('check_unknowns') or enforcement['unknown'] or external and not cases or not external and (counts['unassessed'] or applicable and not complete):
            gate = 'incomplete'
        elif not external and not applicable:
            gate = 'not-applicable'
        elif current_risk['band'] == 'MEDIUM' or attention:
            gate = 'watch'
        else:
            gate = 'pass'
        results.append({'id': pid, **metrics(open_roots, external), 'observed': metrics(observed_roots, external),
                        'risk': current_risk, 'observed_risk': observed_risk, 'total': len(eligible), 'counts': counts,
                        'applicable': applicable, 'coverage': (counts['issue'] + counts['clear']) / applicable if applicable else None,
                        'accepted_findings': sum(f['kind'] == 'issue' and f['in_scope'] and f['decision']['status'] == 'accepted' for f in rows),
                        'resolved_findings': sum(f['kind'] == 'issue' and f['in_scope'] and f['decision']['status'] == 'resolved' for f in rows),
                        'invalid_findings': sum(f['kind'] == 'issue' and f['in_scope'] and f['decision']['status'] == 'invalid' for f in rows),
                        'external_enforcement': enforcement, 'attention_required': attention, 'gate': gate, 'hard_gates': hard,
                        'check_unknowns': p.get('check_unknowns', []), 'findings': rows})
        all_open.update(open_roots); all_observed.update(observed_roots)
    if not results:
        raise ValueError('At least one principle is required')
    if set(decisions) - set(records):
        raise ValueError('Decision references unknown finding IDs')
    gates = {p['gate'] for p in results}
    averaged = [p for p in results if p['gate'] not in ('skipped', 'not-applicable') and p.get('impact', {}).get('scope') != 'external-only']
    def mean(field):
        known = [Fraction(p[field]['weighted_affected_units'], 10 * len(eligible)) for p in averaged if p[field]['score'] is not None]
        value = sum(known, Fraction()) / len(averaged) if averaged and len(known) == len(averaged) else None
        return numeric(value, method='equal mean of selected applicable module-principle risks',
                       included_principles=[p['id'] for p in averaged], known_principles=len(known),
                       coverage_complete=all(not p['counts']['unassessed'] and not p['check_unknowns'] for p in averaged))
    adjusted_mean = mean('risk')
    # Only the aggregate risk controls the overall gate. Local checks stay separate.
    overall = ('skipped' if gates == {'skipped'} else 'not-applicable' if gates <= {'skipped', 'not-applicable'} else
               'incomplete' if adjusted_mean['score'] is None else
               'fail' if adjusted_mean['band'] == 'HIGH' else 'watch' if adjusted_mean['band'] == 'MEDIUM' else 'pass')
    external_only = all(p.get('impact', {}).get('scope') == 'external-only' for p in results if p['gate'] != 'skipped') and gates != {'skipped'}
    return {'policy': POLICY, 'thresholds': {'medium_min': .03, 'high_min': .10},
            'consequence_weights': {k: float(v) for k, v in WEIGHTS.items()}, 'overall_gate': overall,
            'scope': 'full' if seen == PRINCIPLES and 'skipped' not in gates else 'partial',
            'inventory_total': len(modules), 'total': len(eligible), 'excluded_modules': exclusions,
            'decisions': decisions, **metrics(all_open, external_only), 'observed': metrics(all_observed, external_only),
            'risk': adjusted_mean, 'observed_risk': mean('observed_risk'),
            'consumer_graph_provenance': data.get('consumer_graph_provenance'), 'principles': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--decisions', type=Path, help='Exported report decisions/scope; applies only to the matching audit input')
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding='utf-8'))
    if args.decisions:
        overrides = json.loads(args.decisions.read_text(encoding='utf-8'))
        # Input binding is required; a decision from another audit must not silently apply.
        import hashlib
        identity = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        if overrides.get('audit_id') != identity:
            raise SystemExit('Decisions belong to another audit input; revalidate before applying')
        data.update({k: overrides[k] for k in ('decisions', 'excluded_modules') if k in overrides})
    result = json.dumps(score(data), indent=2) + '\n'
    if args.output:
        args.output.write_text(result, encoding='utf-8')
    else:
        print(result, end='')
