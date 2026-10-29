#!/usr/bin/env python3
"""Change history facts: how often each module changes, how often those changes are fixes, and how often they edit
the module together with its importers or touch only one of its folders.

One change set is one first-parent commit with its merge diff, so squash-merged and merge-commit workflows both count
one change per merged request. The window ends at the audited commit, so a rerun at the same ref gives the same facts.
The structure scan runs this for every module; run it directly with `--clusters` to count how a module's evaluated
component clusters change.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import fnmatch
from itertools import combinations
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

POLICY = 'history-scan-v1'
# Conventional `fix:`, fix/bugfix/hotfix branches in merge subjects, plain-language bug words and reverts.
FIX = re.compile(r'^(fix|bugfix|hotfix)(\([^)]*\))?!?:|\b(bug|bugs|bugfix|hotfix|crash(es|ing)?|regression|fix(es|ed)?)\b|'
                 r'[/ ](fix|bugfix|hotfix)[/-]|^revert\b|^revert(\(|:)', re.IGNORECASE)
FIX_RULE = 'conventional fix/bugfix/hotfix type, fix branch in a merge, bug/crash/regression/fix words, or a revert'
# Fewer change sets than this cannot back a severity floor: a young or shallow history says little about a boundary.
MIN_CHANGE_SETS = 50
SEPARATOR = '\x1e'


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True, encoding='utf-8',
                          errors='replace', check=True).stdout


def is_fix(subject, body):
    # A merge commit's subject names the branch; its body's first line is usually the request title.
    title = body.strip().splitlines()[0] if subject.startswith('Merge ') and body.strip() else ''
    return bool(FIX.search(subject) or title and FIX.search(title))


def change_sets(root, days):
    """First-parent change sets in the window ending at HEAD's commit date: (sha, is_fix, paths). Paths are reported
    at their audited location: walking from newest to oldest, a file renamed or moved later keeps counting for the
    module that owns it now, so a folder restructure does not erase a module's history."""
    head = git(root, 'log', '-1', '--format=%cI').strip()
    if not head:
        return None, []
    end = datetime.fromisoformat(head)
    since = end - timedelta(days=days)
    out = git(root, 'log', '--first-parent', '--diff-merges=first-parent', '--relative', '--name-status', '-M', '-z',
              f'--since={since.isoformat()}', f'--format={SEPARATOR}%H%x00%s%x00%b%x00', '--', '.')
    sets, current = [], {}
    for record in out.split(SEPARATOR)[1:]:
        sha, subject, body, *fields = record.split('\x00')
        fields = [f.strip('\n') for f in fields if f.strip('\n')]
        paths, i = [], 0
        while i < len(fields):
            status = fields[i]
            if status[:1] in 'RC':
                old, new = fields[i + 1], fields[i + 2]
                now = current.get(new, new)
                if status[0] == 'R':
                    current[old] = now
                paths.append(now)
                i += 3
            else:
                paths.append(current.get(fields[i + 1], fields[i + 1]))
                i += 2
        sets.append((sha, is_fix(subject, body), paths))
    return {'end': end.isoformat(), 'since': since.isoformat(), 'days': days, 'head': git(root, 'rev-parse', 'HEAD').strip()}, sets


def path_owner(module_files):
    """Map a repository path to the module whose current files own its nearest directory, so deleted or renamed files,
    tests, resources and manifests inside a module's folders still count as changes to it."""
    claims = defaultdict(set)
    for m, files in module_files.items():
        for rel in files:
            claims[rel].add(m)
            for parent in PurePosixPath(rel).parents:
                if str(parent) != '.':
                    claims[str(parent)].add(m)
    owner = {p: next(iter(ms)) for p, ms in claims.items() if len(ms) == 1}

    def find(path):
        if path in owner:
            return owner[path]
        return next((owner[str(p)] for p in PurePosixPath(path).parents if str(p) in owner), None)
    return find


def group_of(groups):
    """Folder groups from the structure scan's divisibility split, deepest folder first."""
    folders = sorted(groups, key=len, reverse=True)
    return lambda path: next((g for g in folders if path.startswith(g + '/')), None)


def p1_floor(row, change_sets):
    """The P1 severity floor a module's history supports, with the counts behind it: observed broad coordinated change
    (many importers edited with it, or repeated fixes that needed its importers) or a target most changes go through
    while they stay inside one of its folders. History raises a floor; it never lowers one."""
    if change_sets < MIN_CHANGE_SETS:
        return None, None
    coordinated, partners, fixes = row['coordinated'], row['consumers_co_changed'], row['fixes_with_consumers']
    if coordinated >= 10 and (partners >= 10 or fixes >= 10 and partners >= 5):
        return 'high', (f'{coordinated} change sets edited it with 2+ importers; {partners} of {row["library_consumers"]} '
                        f'library importers co-changed; {fixes} fixes edited it with an importer')
    grouped, single = row.get('group_changes', 0), row.get('single_group_changes', 0)
    if 2 * row['changes'] >= change_sets and grouped >= 20 and 10 * single >= 6 * grouped:
        return 'high', (f'{row["changes"]} of {change_sets} change sets went through it; {single} of {grouped} '
                        f'touched only one of its {row["folder_groups"]} folder groups')
    # Editing a module with a few importers is ordinary feature work, so history backs only the high anchor.
    return None, None


def history(root, module_files, consumers, hosts=(), groups=None, days=365):
    """Per-module change facts over the window. `groups` maps a module to its major folder groups; `hosts` never count
    as co-changed importers, because app targets wire every change by design."""
    try:
        window, sets = change_sets(root, days)
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return {'policy': POLICY, 'available': False, 'reason': 'not a git checkout, or git is unavailable'}
    if window is None:
        return {'policy': POLICY, 'available': False, 'reason': 'no commits'}
    owner = path_owner(module_files)
    finders = {m: group_of(gs) for m, gs in (groups or {}).items()}
    # A change set touching a quarter of the modules is a sweep (rename, format, toolchain bump), not one module's change.
    sweep_limit = max(10, len(module_files) // 4)
    rows = {m: Counter() for m in module_files}
    partners = defaultdict(set)
    totals = Counter()
    for _, fix, files in sets:
        touched = defaultdict(list)
        for path in files:
            m = owner(path)
            if m:
                touched[m].append(path)
        if not touched:
            continue
        if len(touched) > sweep_limit:
            totals['sweeps'] += 1
            continue
        totals['change_sets'] += 1
        totals['fixes'] += fix
        for m, paths in touched.items():
            row = rows[m]
            row['changes'] += 1
            row['fixes'] += fix
            co = {c for c in consumers.get(m, ()) if c in touched and c not in hosts}
            if co:
                row['with_consumers'] += 1
                row['fixes_with_consumers'] += fix
                partners[m] |= co
            row['coordinated'] += len(co) >= 2
            if m in finders:
                hit = {g for g in map(finders[m], paths) if g}
                row['group_changes'] += bool(hit)
                row['single_group_changes'] += len(hit) == 1
    modules = {}
    for m in sorted(module_files):
        row = rows[m]
        out = {'changes': row['changes'], 'fixes': row['fixes'], 'with_consumers': row['with_consumers'],
               'fixes_with_consumers': row['fixes_with_consumers'], 'coordinated': row['coordinated'],
               'library_consumers': sum(c not in hosts for c in consumers.get(m, ())), 'consumers_co_changed': len(partners[m])}
        if m in finders:
            out.update(folder_groups=len(groups[m]), group_changes=row['group_changes'], single_group_changes=row['single_group_changes'])
        floor, basis = p1_floor(out, totals['change_sets'])
        if floor:
            out.update(p1_floor=floor, p1_floor_basis=basis)
        modules[m] = out
    return {'policy': POLICY, 'available': True, 'window': window,
            'unit': 'first-parent change set (a merged request or a direct commit)',
            'change_sets': totals['change_sets'], 'fixes': totals['fixes'], 'sweeps_excluded': totals['sweeps'],
            'sweep_limit_modules': sweep_limit, 'fix_rule': FIX_RULE, 'min_change_sets_for_floor': MIN_CHANGE_SETS,
            'modules': modules}


def clusters(root, spec, days=365):
    """How an evaluated module's component clusters change: per-cluster counts, single-cluster change sets and pairs
    that changed together. `spec` is {"module": "…", "clusters": {"Name": ["repo/relative/glob*.swift", …]}}."""
    window, sets = change_sets(root, days)
    patterns = spec['clusters']
    names = sorted(patterns)
    rows, pairs, totals = {n: Counter() for n in names}, Counter(), Counter()
    sweep_limit = max(10, len(names) // 4)
    for _, fix, files in sets:
        hit = {n for n in names for path in files if any(fnmatch.fnmatchcase(path, p) for p in patterns[n])}
        if not hit:
            continue
        if len(hit) > sweep_limit:
            totals['sweeps'] += 1
            continue
        totals['change_sets'] += 1
        totals['fixes'] += fix
        totals['single_cluster'] += len(hit) == 1
        for n in hit:
            rows[n]['changes'] += 1
            rows[n]['fixes'] += fix
        pairs.update(combinations(sorted(hit), 2))
    return {'policy': POLICY, 'module': spec.get('module'), 'window': window, 'fix_rule': FIX_RULE,
            'clusters': len(names), 'change_sets': totals['change_sets'], 'fixes': totals['fixes'],
            'single_cluster_change_sets': totals['single_cluster'], 'sweeps_excluded': totals['sweeps'], 'sweep_limit_clusters': sweep_limit,
            'pairs_changed_together': len(pairs), 'possible_pairs': len(names) * (len(names) - 1) // 2,
            'per_cluster': {n: dict(rows[n]) for n in names},
            'top_pairs': [{'pair': list(p), 'change_sets': k} for p, k in pairs.most_common(10)]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--clusters', type=Path, required=True, help='{"module": "…", "clusters": {"Name": ["glob", …]}}')
    parser.add_argument('--days', type=int, default=365)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = json.dumps(clusters(args.root, json.loads(args.clusters.read_text(encoding='utf-8')), args.days), indent=2) + '\n'
    if args.output:
        args.output.write_text(result, encoding='utf-8')
    else:
        print(result, end='')
