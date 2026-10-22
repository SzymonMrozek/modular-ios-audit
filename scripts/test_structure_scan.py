#!/usr/bin/env python3
"""Structure scan checks on synthetic repositories: a clean modular graph stays quiet, a tangled one surfaces every archetype."""
from pathlib import Path
import tempfile
import unittest
from structure_scan import scan


def write(root, path, imports, body):
    file = Path(root, path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(''.join(f'import {name}\n' for name in imports) + body, encoding='utf-8')


def lines(name, count=30):
    return f'public struct {name} {{\n' + ''.join(f'    let value{i} = {i}\n' for i in range(count)) + '}\n'


def clean_repo(root):
    write(root, 'App/Sources/App.swift', ['SwiftUI', 'AccountInterface', 'AccountImplementation', 'FeedInterface', 'FeedImplementation'],
          '@main\nstruct ExampleApp {}\n' + lines('Composition', 10))
    for name in ['Account', 'Feed']:
        write(root, f'Modules/{name}/Interface/Sources/{name}.swift', ['Values'], lines(name + 'Contract', 8))
        for i in range(4):
            write(root, f'Modules/{name}/Implementation/Sources/{name}{i}.swift', ['SwiftUI', f'{name}Interface', 'Values'], lines(f'{name}Screen{i}'))
    write(root, 'Modules/Feed/Implementation/Sources/Open.swift', ['AccountInterface'], lines('OpenAccount', 5))
    write(root, 'Modules/Values/Sources/Values.swift', [], lines('Identifier', 12))
    write(root, 'Modules/Values/Sources/ValuesTests.swift', ['XCTest', 'Values'], lines('Ignored', 400))


def messy_repo(root):
    folders = ['Library', 'Editor', 'Sharing', 'Settings']
    for f in folders:
        others = ' '.join(f'{o}Type()' for o in folders if o != f)
        for i in range(6):
            write(root, f'App/{f}/{f}{i}.swift', ['UIKit', 'Common', 'PaymentsInterface', 'Profile', 'Search', 'Chat'], f'class {f}Type{i if i else ""} {{ func go() {{ {others} }} }}\n' + lines(f'{f}Model{i}', 60))
    write(root, 'App/AppDelegate.swift', ['UIKit'], '@main\nclass AppDelegate: UIResponder, UIApplicationDelegate {}\n')
    for i in range(6):
        write(root, f'Common/Sources/Common{i}.swift', ['UIKit', 'CoreData', 'Alamofire', 'Kingfisher', 'Logging', 'Analytics'],
              lines(f'Shared{i}', 70))
    for i in range(3):
        write(root, f'Common/Sources/Mixed{i}.swift', ['UIKit', 'CoreData'], lines(f'Mixed{i}', 5))
    write(root, 'Analytics/Sources/Tracker.swift', ['Common'], 'public protocol Tracker {}\n' + lines('Tracker', 10))
    write(root, 'Logging/Sources/Logger.swift', ['Analytics'], lines('Logger', 10))
    for name in ['Profile', 'Search', 'Chat']:
        write(root, f'{name}/Sources/{name}.swift', ['Common', 'Nuke', 'PaymentsImplementation'], lines(name, 150))
    write(root, 'Payments/Interface/Sources/Payments.swift', [], 'public protocol HTTPClient {}\n' + lines('Payments', 5))
    write(root, 'Payments/Implementation/Sources/Payments.swift', ['PaymentsInterface'], 'protocol APIClient {}\n' + lines('PaymentsLive', 5))
    write(root, 'Profile/Sources/Client.swift', [], 'public protocol NetworkClient {}\n')


class StructureScanTests(unittest.TestCase):
    def test_clean_modular_graph_has_no_candidates(self):
        with tempfile.TemporaryDirectory() as root:
            clean_repo(root)
            result = scan(root)
        self.assertEqual(result['candidates'], [])
        self.assertEqual(set(result['modules']), {'App', 'Modules/Account', 'Modules/Feed', 'Modules/Values'})
        self.assertEqual(result['modules']['App']['kind'], 'app')
        self.assertEqual(result['consumers']['Modules/Account'], ['App', 'Modules/Feed'])
        self.assertEqual(result['repository']['cycles'], 0)
        self.assertNotIn('XCTest', result['modules']['Modules/Values']['third_party'])
        self.assertEqual(result['module_weights']['Modules/Values'], 14)

    def test_implementation_behind_interface_does_not_spread(self):
        with tempfile.TemporaryDirectory() as root:
            clean_repo(root)
            result = scan(root)
        self.assertEqual(result['modules']['Modules/Feed']['library_dependents_mass_share'], 0)
        self.assertGreater(result['modules']['Modules/Account']['library_dependents_mass_share'], 0)

    def test_tangled_repository_surfaces_each_archetype(self):
        with tempfile.TemporaryDirectory() as root:
            messy_repo(root)
            result = scan(root)
        found = {c['archetype']: c for c in result['candidates']}
        self.assertEqual(set(found), {'monolithic-module', 'contamination-hub', 'tangled-graph', 'mixed-concerns', 'parallel-abstractions'})
        mono = found['monolithic-module']
        self.assertEqual(mono['modules'], ['App']); self.assertEqual(mono['severity_floor'], 'high')
        self.assertGreaterEqual(mono['metrics']['divisibility']['density'], .9)
        hub = next(c for c in result['candidates'] if c['archetype'] == 'contamination-hub')
        self.assertEqual(hub['modules'], ['Common']); self.assertIn('mixes layers', hub['metrics']['dirt'])
        tangles = [c for c in result['candidates'] if c['archetype'] == 'tangled-graph']
        self.assertTrue(any(c['metrics'].get('cycles') for c in tangles))
        self.assertTrue(any(c['metrics'].get('implementation_imports') for c in tangles))
        concerns = {c['metrics']['concern'] for c in result['candidates'] if c['archetype'] == 'parallel-abstractions'}
        self.assertEqual(concerns, {'images', 'networking'})

    def test_module_map_overrides_discovery(self):
        with tempfile.TemporaryDirectory() as root:
            clean_repo(root)
            mapping = {'modules': {'Everything': {'kind': 'library', 'import_names': [], 'sources': ['Modules']},
                                   'App': {'kind': 'app', 'import_names': [], 'sources': ['App']}}}
            result = scan(root, mapping)
        self.assertEqual(set(result['modules']), {'App', 'Everything'})
        self.assertEqual(result['module_source'], 'map')


if __name__ == '__main__':
    unittest.main()
