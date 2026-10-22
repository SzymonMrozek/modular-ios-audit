#!/usr/bin/env python3
"""Score an audit as consequence-weighted code exposure; retain evidence, scope, structural candidates and user decisions."""
import argparse
from fractions import Fraction
import json
from pathlib import Path

POLICY = 'structural-principles-v7'
STATES = {'issue', 'clear', 'not-applicable', 'unassessed'}
# Consequence weight = units / 20.
UNITS = {'low': 1, 'medium': 2, 'high': 8, 'critical': 14}
SEVERITIES = set(UNITS)
RANK = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
PRINCIPLES = {f'P{i}' for i in range(1, 9)}
DECISIONS = {'open', 'resolved', 'invalid', 'accepted'}
# Structure-scan archetypes and the principle whose evaluator confirms or dismisses them.
OWNERS = {'monolithic-module': 'P1', 'contamination-hub': 'P1', 'mixed-concerns': 'P1', 'parallel-abstractions': 'P5', 'tangled-graph': 'P7'}
MEDIUM_MIN, HIGH_MIN, TINY_MAX = Fraction(1, 10), Fraction(1, 4), Fraction(1, 100)


def band(value):
    return None if value is None else 'LOW' if value < MEDIUM_MIN else 'MEDIUM' if value < HIGH_MIN else 'HIGH'


def numeric(value, **extra):
    return {'score': float(value) if value is not None else None,
            'percent': float(value * 100) if value is not None else None,
            'health': None if value is None else round(float((1 - value) * 100)),
            'band': band(value), **extra}


def score(data):
    modules = data['modules']
    if not modules or len(modules) != len(set(modules)):
        raise ValueError('Module inventory must be nonempty and unique')
    inventory = set(modules)
    if 'thresholds' in data:
        raise ValueError('Policy fixes 10%/25% bands; remove custom or legacy thresholds')
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
    raw_weights = data.get('module_weights')
    if raw_weights is not None:
        if not isinstance(raw_weights, dict) or set(raw_weights) != inventory or any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in raw_weights.values()):
            raise ValueError('module_weights must give a nonnegative integer code mass for every inventoried module')
        weights = {m: raw_weights[m] for m in eligible}
        if eligible and not sum(weights.values()):
            raise ValueError('Eligible modules need nonzero total code mass')
    else:
        weights = {m: 1 for m in eligible}
    mass_total = sum(weights.values())
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

    def exposure(roots, implementation_only=False):
        roots = set(roots) & eligible
        if not complete:
            return None
        return roots if implementation_only else roots | set().union(*(set(consumers[r]) & eligible for r in roots))

    def metrics(roots, external=False, implementation_only=False, spreading=None):
        """Footprint of roots; only `spreading` roots (default: all, none when implementation_only) reach consumers."""
        roots = sorted(set(roots) & eligible)
        spreading = set() if implementation_only else set(roots) if spreading is None else set(spreading) & eligible
        available = complete and not external and bool(eligible)
        affected = sorted(set().union(*(set(consumers[r]) & eligible for r in spreading))) if available else None
        exposed = set(roots) | set(affected) if available else None
        reach = Fraction(sum(weights[m] for m in exposed), mass_total) if available else None
        return {'rootCostModules': None if external else len(roots), 'rootCostModuleIDs': roots,
                'affectedModules': len(affected) if available else None, 'affectedModuleIDs': affected,
                'impact': numeric(reach, scope='external-only' if external else 'module', total_modules=len(eligible),
                    exposed_modules=len(exposed) if exposed is not None else None, graph_inventory_complete=complete,
                    missing_root_graph=[r for r in roots if r not in consumers],
                    meaning='Code mass owning or directly importing the defect; not consequence or architecture health')}

    def risk(findings, external=False):
        """Max consequence within each principle, noisy-OR across principles, mass-weighted."""
        if external or not eligible or not complete:
            return numeric(None, method='mass-weighted exposure; max per principle, combined across principles')
        values = {}
        for f, pid in findings:
            for module in exposure(root_ids(f), f.get('implementation_only') is True):
                row = values.setdefault(module, {})
                row[pid] = max(row.get(pid, 0), UNITS[f['severity']])
        total = Fraction()
        for module, row in values.items():
            clean = Fraction(1)
            for units in row.values():
                clean *= 1 - Fraction(units, 20)
            total += weights[module] * (1 - clean)
        return numeric(total / mass_total, method='mass-weighted exposure; max per principle, combined across principles')

    structural = data.get('structural')
    candidates, resolutions = {}, {}
    if structural is not None:
        for c in structural.get('candidates', []):
            owner = c.get('principle', OWNERS.get(c.get('archetype')))
            if not c.get('id') or c['id'] in candidates or owner not in PRINCIPLES or c.get('severity_floor') not in SEVERITIES:
                raise ValueError('Structural candidates need unique IDs, an owning principle and a severity floor')
            if not set(c.get('modules', [])) <= inventory:
                raise ValueError('Structural candidate names unknown modules: ' + c['id'])
            candidates[c['id']] = {**c, 'principle': owner}
        resolutions = structural.get('resolutions', {})
        if set(resolutions) - set(candidates):
            raise ValueError('Resolution references unknown structural candidates')
        for cid, r in resolutions.items():
            if r.get('status') == 'dismissed' and not (str(r.get('reason', '')).strip() and r.get('evidence')):
                raise ValueError('Dismissed structural candidate needs reason and counterevidence: ' + cid)
            if r.get('status') not in ('confirmed', 'dismissed'):
                raise ValueError('Structural resolution must be confirmed or dismissed: ' + cid)
    skipped = {p['id'] for p in data['principles'] if p.get('skipped')}
    in_review = {cid for cid, c in candidates.items() if c['principle'] not in skipped}

    results, seen, records, all_open, all_observed = [], set(), {}, [], []
    finding_principles = {}
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
            finding_principles.setdefault(fid, []).append(pid)
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
            linked = f.get('candidate_ids', [])
            if set(linked) - set(candidates):
                raise ValueError('Finding links unknown structural candidates: ' + fid)
            floor = max((candidates[c]['severity_floor'] for c in linked), key=RANK.get, default=None)
            if floor and RANK[f['severity']] < RANK[floor] and not str(f.get('floor_override_reason', '')).strip():
                raise ValueError(f'Finding {fid} is below its structural severity floor ({floor}) without floor_override_reason')
            decision = decisions.get(fid, {'status': 'open'})
            in_scope = bool(set(roots) & eligible) or not roots and bool(f['external_scopes'])
            if kind == 'issue':
                owner_union.update(roots)
                if in_scope:
                    observed_findings.append((f, pid))
                    if decision['status'] == 'open':
                        open_findings.append((f, pid))
            external = not roots and bool(f['external_scopes'])
            active = in_scope and kind == 'issue' and decision['status'] == 'open'
            implementation_only = f.get('implementation_only') is True
            original_risk = risk([(f, pid)] if kind == 'issue' and in_scope else [], external)
            tiny = original_risk['score'] is not None and original_risk['score'] < TINY_MAX
            presentation = 'suggestion' if kind == 'suggestion' else 'tiny' if tiny else 'issue'
            rows.append({'id': fid, 'kind': kind, 'presentation': presentation, 'severity': f['severity'], 'severity_reason': f['severity_reason'],
                         'structural': bool(linked), 'archetype': f.get('archetype'), 'candidate_ids': linked, 'severity_floor': floor,
                         'implementation_only': implementation_only, 'decision': decision, 'in_scope': in_scope, 'active': active,
                         'observed': metrics(roots if in_scope and kind == 'issue' else [], external, implementation_only),
                         'consequence_weight': UNITS[f['severity']] / 20 if kind == 'issue' else 0,
                         **metrics(roots if active else [], external, implementation_only), 'risk': risk([(f, pid)] if active else [], external),
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
        applicable_mass = sum(weights[m] for m in eligible if ledger.get(m, {}).get('status') != 'not-applicable')
        assessed_mass = sum(weights[m] for m in eligible if ledger.get(m, {}).get('status') in ('issue', 'clear'))
        hard = p.get('hard_gates', [])
        if any(not all(row.get(k) for k in ('id', 'reason', 'evidence')) for row in hard):
            raise ValueError('Hard gate requires id, reason and evidence')
        cases, case_ids, families = p.get('enforcement_cases', []), set(), set()
        for case in cases:
            if not all(case.get(k) for k in ('id', 'family', 'outcome', 'evidence')) or case['outcome'] not in ('passed', 'failed', 'unknown') or case['id'] in case_ids or case['family'] in families:
                raise ValueError('Invalid/duplicate enforcement family: ' + pid)
            case_ids.add(case['id']); families.add(case['family'])
        enforcement = {'evaluated_families': len(cases), **{state: sum(c['outcome'] == state for c in cases) for state in ('failed', 'passed', 'unknown')}, 'cases': cases}
        open_roots = set().union(*(set(root_ids(f)) & eligible for f, _ in open_findings))
        observed_roots = owner_union & eligible
        spread = lambda fs: set().union(*(set(root_ids(f)) for f, _ in fs if f.get('implementation_only') is not True))
        current_risk, observed_risk = risk(open_findings, external), risk(observed_findings, external)
        attention = bool(hard or enforcement['failed'] or any(f['severity'] == 'critical' for f, _ in open_findings))
        unresolved = any(c['principle'] == pid and cid not in resolutions for cid, c in candidates.items())
        if current_risk['band'] == 'HIGH':
            gate = 'fail'
        elif unresolved or p.get('check_unknowns') or enforcement['unknown'] or external and not cases or not external and (counts['unassessed'] or applicable and not complete):
            gate = 'incomplete'
        elif not external and not applicable:
            gate = 'not-applicable'
        elif current_risk['band'] == 'MEDIUM' or attention:
            gate = 'watch'
        else:
            gate = 'pass'
        observed_spread = set().union(*(set(root_ids(f)) for f in findings if f.get('kind', 'issue') == 'issue' and f.get('implementation_only') is not True))
        results.append({'id': pid, **metrics(open_roots, external, spreading=spread(open_findings)), 'observed': metrics(observed_roots, external, spreading=observed_spread),
                        'risk': current_risk, 'observed_risk': observed_risk, 'total': len(eligible), 'counts': counts,
                        'applicable': applicable, 'coverage': (counts['issue'] + counts['clear']) / applicable if applicable else None,
                        'assessed_mass': float(Fraction(assessed_mass, applicable_mass)) if applicable_mass else None,
                        'accepted_findings': sum(f['kind'] == 'issue' and f['in_scope'] and f['decision']['status'] == 'accepted' for f in rows),
                        'resolved_findings': sum(f['kind'] == 'issue' and f['in_scope'] and f['decision']['status'] == 'resolved' for f in rows),
                        'invalid_findings': sum(f['kind'] == 'issue' and f['in_scope'] and f['decision']['status'] == 'invalid' for f in rows),
                        'external_enforcement': enforcement, 'attention_required': attention, 'gate': gate, 'hard_gates': hard,
                        'check_unknowns': p.get('check_unknowns', []), 'findings': rows})
        if not external:
            all_open.extend(open_findings); all_observed.extend(observed_findings)
    if not results:
        raise ValueError('At least one principle is required')
    if set(decisions) - set(records):
        raise ValueError('Decision references unknown finding IDs')
    for cid, r in resolutions.items():
        owner = candidates[cid]['principle']
        if r['status'] == 'confirmed' and owner not in skipped and (r.get('finding') not in records or owner not in finding_principles[r['finding']]):
            raise ValueError(f'Confirmed structural candidate {cid} must name a {owner} finding')
    unresolved = sorted(in_review - set(resolutions))
    included = [p for p in results if p['gate'] not in ('skipped', 'not-applicable') and p.get('impact', {}).get('scope') != 'external-only']
    unique = lambda fs: list({f['id']: (f, finding_principles[f['id']][0]) for f, _ in fs}.values())

    def overall(findings, field):
        value = risk(unique(findings))
        known = all(p[field]['score'] is not None for p in included)
        withheld = 'structural candidates unresolved' if unresolved else None if known else 'unknown principle risk'
        if withheld:
            value = numeric(None, method=value['method'])
        return {**value, 'withheld': withheld, 'included_principles': [p['id'] for p in included],
                'coverage_complete': not unresolved and all(not p['counts']['unassessed'] and not p['check_unknowns'] for p in included),
                'assessed_mass_min': min((p['assessed_mass'] for p in included if p['assessed_mass'] is not None), default=None)}
    adjusted, observed = overall(all_open, 'risk'), overall(all_observed, 'observed_risk')
    ranked = []
    for p in results:
        for f in p.get('findings', []):
            if f['kind'] == 'issue' and f['in_scope'] and f['observed_risk']['score'] is not None and f['id'] not in {r['id'] for r in ranked}:
                ranked.append({'id': f['id'], 'principles': finding_principles[f['id']], 'structural': f['structural'], 'severity': f['severity'],
                               'impact': f['observed_risk']['score'], 'open': f['active']})
    ranked.sort(key=lambda r: (-r['impact'], not r['structural'], -RANK[r['severity']], r['id']))
    gates = {p['gate'] for p in results}
    legacy = ('skipped' if gates == {'skipped'} else 'not-applicable' if gates <= {'skipped', 'not-applicable'} else
              'incomplete' if adjusted['score'] is None else
              'fail' if adjusted['band'] == 'HIGH' else 'watch' if adjusted['band'] == 'MEDIUM' else 'pass')
    external_only = all(p.get('impact', {}).get('scope') == 'external-only' for p in results if p['gate'] != 'skipped') and gates != {'skipped'}
    structure = data.get('structure', {})
    return {'policy': POLICY, 'thresholds': {'medium_min': float(MEDIUM_MIN), 'high_min': float(HIGH_MIN), 'tiny_max': float(TINY_MAX)},
            'consequence_weights': {k: v / 20 for k, v in UNITS.items()}, 'overall_gate': legacy,
            'weighting': 'code-mass' if raw_weights is not None else 'equal',
            'scope': 'full' if seen == PRINCIPLES and 'skipped' not in gates else 'partial',
            'inventory_total': len(modules), 'total': len(eligible), 'excluded_modules': exclusions,
            'decisions': decisions, **metrics(set().union(*(set(root_ids(f)) for f, _ in all_open)), external_only, spreading=spread(all_open)),
            'observed': metrics(set().union(*(set(root_ids(f)) for f, _ in all_observed)), external_only, spreading=spread(all_observed)),
            'risk': adjusted, 'observed_risk': observed, 'ranking': ranked,
            'structural': {'screened': structural is not None, 'candidates': len(in_review), 'unresolved': unresolved,
                           'confirmed': sorted(c for c, r in resolutions.items() if r['status'] == 'confirmed'),
                           'dismissed': sorted(c for c, r in resolutions.items() if r['status'] == 'dismissed'),
                           'skipped': sorted(set(candidates) - in_review)},
            'structure': structure.get('repository'),
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
