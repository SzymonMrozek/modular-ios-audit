#!/usr/bin/env python3
"""Change-history checks on synthetic git repositories: change-set units, fix and sweep counting, and P1 floors."""
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest
from history_scan import MIN_CHANGE_SETS, clusters, history, is_fix

ENV = {**os.environ, 'GIT_AUTHOR_NAME': 'Test', 'GIT_AUTHOR_EMAIL': 'test@example.com', 'GIT_COMMITTER_NAME': 'Test',
       'GIT_COMMITTER_EMAIL': 'test@example.com', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}


def git(root, *args):
    subprocess.run(['git', '-C', root, *args], check=True, capture_output=True, env=ENV)


def commit(root, message, paths):
    for path in paths:
        file = Path(root, path)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(file.read_text(encoding='utf-8') + '.' if file.exists() else 'x', encoding='utf-8')
    git(root, 'add', '-A')
    git(root, 'commit', '-q', '-m', message)


def repo(test):
    root = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, root, ignore_errors=True)
    git(root, 'init', '-q', '-b', 'main')
    return root


def files(names):
    return {m: [f'{m}/Sources/{Path(m).name}.swift'] for m in names}


class HistoryScanTests(unittest.TestCase):
    def test_fix_rule(self):
        for subject in ['fix(trade): round amounts', 'Fix crash when opening chat', 'Revert "feat: x"', 'hotfix: token']:
            self.assertTrue(is_fix(subject, ''), subject)
        for subject in ['feat(fixtures): add data', 'Prefix names', 'chore: bump version']:
            self.assertFalse(is_fix(subject, ''), subject)
        self.assertTrue(is_fix('Merge pull request #12 from org/bugfix/login', ''))
        self.assertTrue(is_fix("Merge branch 'feature'", 'Fix empty list after removing a member\n'))

    def test_not_a_git_checkout(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertFalse(history(root, files(['Core']), {})['available'])

    def test_merge_request_is_one_change_set_and_deleted_paths_count(self):
        root = repo(self)
        commit(root, 'feat: start', ['Core/Sources/Core.swift', 'Core/Sources/Legacy.swift', 'Feed/Sources/Feed.swift'])
        git(root, 'checkout', '-q', '-b', 'topic')
        commit(root, 'wip one', ['Feed/Sources/Feed.swift'])
        commit(root, 'wip two', ['Core/Tests/CoreTests.swift'])
        git(root, 'rm', '-q', 'Core/Sources/Legacy.swift')
        git(root, 'commit', '-q', '-m', 'wip three')
        git(root, 'checkout', '-q', 'main')
        git(root, 'merge', '-q', '--no-ff', '-m', "Merge branch 'topic'", 'topic')
        commit(root, 'fix: core rounding', ['Core/Sources/Core.swift', 'README.md'])
        result = history(root, files(['Core', 'Feed']), {'Core': ['Feed']})
        self.assertEqual(result['change_sets'], 3)
        self.assertEqual(result['fixes'], 1)
        core = result['modules']['Core']
        self.assertEqual((core['changes'], core['fixes'], core['with_consumers'], core['coordinated']), (3, 1, 2, 0))
        self.assertEqual(result['modules']['Feed']['changes'], 2)

    def test_moved_module_keeps_its_history(self):
        root = repo(self)
        commit(root, 'feat: core', ['Modules/Core/Sources/Core.swift'])
        commit(root, 'fix: core', ['Modules/Core/Sources/Core.swift'])
        Path(root, 'Modules/Utilities').mkdir()
        git(root, 'mv', 'Modules/Core', 'Modules/Utilities/Core')
        git(root, 'commit', '-q', '-m', 'refactor: group modules')
        commit(root, 'feat: more', ['Modules/Utilities/Core/Sources/Core.swift'])
        core = history(root, {'Modules/Utilities/Core': ['Modules/Utilities/Core/Sources/Core.swift']}, {})['modules']['Modules/Utilities/Core']
        self.assertEqual((core['changes'], core['fixes']), (4, 1))

    def test_broad_coordinated_change_sets_a_high_p1_floor(self):
        root = repo(self)
        importers = [f'Feature{i}' for i in range(12)]
        hosts = ['App']
        for i in range(MIN_CHANGE_SETS):
            touched = ['Hub', importers[i % 12], importers[(i + 1) % 12]] if i < 12 else [importers[i % 12]]
            commit(root, f'feat: change {i}', [f'{m}/Sources/{m}.swift' for m in touched + hosts])
        # A sweep touches a quarter of the modules and is left out of every count.
        commit(root, 'chore: format', [f'{m}/Sources/{m}.swift' for m in ['Hub', 'Leaf'] + importers])
        consumers = {'Hub': importers + hosts, 'Leaf': ['Feature0']}
        result = history(root, files(['Hub', 'Leaf', 'App'] + importers), consumers, hosts=set(hosts))
        self.assertEqual(result['sweeps_excluded'], 1)
        hub = result['modules']['Hub']
        self.assertEqual((hub['changes'], hub['coordinated'], hub['consumers_co_changed'], hub['library_consumers']), (12, 12, 12, 12))
        self.assertEqual(hub['p1_floor'], 'high')
        self.assertIn('12 of 12 library importers co-changed', hub['p1_floor_basis'])
        self.assertNotIn('p1_floor', result['modules']['Feature0'])
        self.assertNotIn('p1_floor', result['modules']['App'])

    def test_monolith_most_changes_go_through_while_folders_change_alone(self):
        root = repo(self)
        folders = ['App/Library', 'App/Editor', 'App/Sharing']
        for i in range(MIN_CHANGE_SETS):
            commit(root, f'feat: {i}', [f'{folders[i % 3]}/File{i % 4}.swift'] + ([f'{folders[(i + 1) % 3]}/File.swift'] if i % 5 == 0 else []))
        module_files = {'App': [f'{f}/File0.swift' for f in folders], 'Core': ['Core/Core.swift']}
        result = history(root, module_files, {}, groups={'App': folders})
        app = result['modules']['App']
        self.assertEqual((app['changes'], app['group_changes'], app['single_group_changes']), (50, 50, 40))
        self.assertEqual(app['p1_floor'], 'high')

    def test_short_history_backs_no_floor(self):
        root = repo(self)
        importers = [f'Feature{i}' for i in range(12)]
        for i in range(12):
            commit(root, f'feat: {i}', [f'{m}/Sources/{m}.swift' for m in ['Hub', importers[i], importers[(i + 1) % 12]]])
        result = history(root, files(['Hub'] + importers), {'Hub': importers})
        self.assertEqual(result['modules']['Hub']['coordinated'], 12)
        self.assertNotIn('p1_floor', result['modules']['Hub'])

    def test_clusters_count_independent_and_paired_changes(self):
        root = repo(self)
        commit(root, 'feat: button', ['UI/Sources/Button.swift'])
        commit(root, 'fix: card crash', ['UI/Sources/Card.swift', 'UI/Sources/CardStyle.swift'])
        commit(root, 'feat: both', ['UI/Sources/Button.swift', 'UI/Sources/Card.swift'])
        commit(root, 'docs: readme', ['README.md'])
        spec = {'module': 'UI', 'clusters': {'Button': ['UI/Sources/Button*.swift'], 'Card': ['UI/Sources/Card*.swift'],
                                             'Chart': ['UI/Sources/Chart*.swift']}}
        result = clusters(root, spec)
        self.assertEqual((result['change_sets'], result['single_cluster_change_sets'], result['fixes']), (3, 2, 1))
        self.assertEqual(result['per_cluster']['Card'], {'changes': 2, 'fixes': 1})
        self.assertEqual((result['pairs_changed_together'], result['possible_pairs']), (1, 3))

    def test_clusters_leave_out_sweeps(self):
        root = repo(self)
        names = [f'Component{i}' for i in range(44)]
        commit(root, 'feat: one', ['UI/Component0.swift'])
        commit(root, 'chore: rename', [f'UI/{n}.swift' for n in names[:12]])
        result = clusters(root, {'module': 'UI', 'clusters': {n: [f'UI/{n}.swift'] for n in names}})
        self.assertEqual((result['sweep_limit_clusters'], result['sweeps_excluded'], result['change_sets']), (11, 1, 1))
        self.assertEqual(result['pairs_changed_together'], 0)


if __name__ == '__main__':
    unittest.main()
