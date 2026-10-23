#!/usr/bin/env python3
"""Structure scan checks on synthetic repositories: a clean modular graph stays quiet, a tangled one surfaces every archetype."""
from pathlib import Path
import tempfile
import unittest
from structure_scan import excluded, groups_within, scan


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
        write(root, f'Common/Sources/Mixed{i}.swift', ['UIKit', 'CoreData'], f'class Mixed{i}Controller: UIViewController {{}}\n' + lines(f'Mixed{i}', 5))
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

    def test_feature_importing_implementations_is_not_a_composition_root(self):
        with tempfile.TemporaryDirectory() as root:
            messy_repo(root)
            for name in ['Orders', 'Basket', 'Wallet', 'Promo']:
                write(root, f'{name}/Interface/Sources/{name}.swift', [], lines(name + 'Contract', 3))
                write(root, f'{name}/Implementation/Sources/{name}.swift', [f'{name}Interface'], lines(name + 'Live', 3))
            write(root, 'Checkout/Sources/Checkout.swift', [f'{n}Implementation' for n in ['Orders', 'Basket', 'Wallet', 'Promo']], lines('Checkout', 400))
            write(root, 'App/Checkout.swift', ['Checkout'], lines('Entry', 2))
            result = scan(root)
        self.assertEqual(result['modules']['Checkout']['kind'], 'library')
        self.assertEqual(len(result['modules']['Checkout']['implementation_imports']), 4)

    def test_excludes_match_components_files_and_globs(self):
        for rel, pattern, expected in [('RecurringBuy/A.swift', 'RecurringBuy/', True), ('RecurringBuyFlow/A.swift', 'RecurringBuy', False),
                                       ('RecurringBuyFlow/A.swift', 'RecurringBuy/', False), ('Api/SecretApiLayer8.swift', 'Api/SecretApiLayer*.swift', True),
                                       ('Utils/Locale+More.swift', 'Utils/Locale+More.swift', True)]:
            self.assertEqual(excluded(rel, [pattern]), expected, (rel, pattern))
        with tempfile.TemporaryDirectory() as root:
            clean_repo(root)
            result = scan(root, excludes=['Modules/Values/'])
        self.assertNotIn('Modules/Values', result['modules'])

    def test_vendor_names_and_nested_folders_do_not_become_modules(self):
        with tempfile.TemporaryDirectory() as root:
            clean_repo(root)
            Path(root, 'Package.resolved').write_text('{"pins": [{"identity": "swift-collections"}]}')
            write(root, 'App/Sources/Collections/Grid.swift', ['SwiftUI'], lines('Grid', 40))
            write(root, 'App/Sources/Uses.swift', ['Collections'], lines('Uses', 2))
            write(root, 'Modules/Feed/Implementation/Sources/Values/Local.swift', [], lines('Local', 20))
            Path(root, 'Modules/Values/Project.swift').write_text('// manifest')
            result = scan(root)
        self.assertNotIn('App/Sources/Collections', result['modules'])
        self.assertEqual(result['modules']['Modules/Values']['loc'], 14)

    def test_extension_info_plist_marks_a_host(self):
        with tempfile.TemporaryDirectory() as root:
            clean_repo(root)
            write(root, 'NotificationService/NotificationService.swift', ['UserNotifications', 'Values'], 'class NotificationService: UNNotificationServiceExtension {}\n')
            Path(root, 'NotificationService/Info.plist').write_text('<key>NSExtension</key><dict><key>NSExtensionPrincipalClass</key></dict>')
            result = scan(root)
        self.assertEqual(result['modules']['NotificationService']['kind'], 'app')

    def test_dominant_folder_keeps_its_siblings_as_groups(self):
        files = [(f'Code/v6.0/Feature{i}/F.swift', 100) for i in range(4)] + [('Code/Networking/W.swift', 60), ('Code/UI/V.swift', 60)]
        _, mass, membership = groups_within(files)
        self.assertIn('Code/Networking', mass); self.assertIn('Code/v6.0/Feature0', mass)
        self.assertEqual(membership['Code/UI/V.swift'], 'Code/UI')

    def test_objc_header_namespace_imports_do_not_form_cycles(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, 'Svg/Sources/Svg.swift', ['LegacyImpl'], lines('Svg', 10))
            Path(root, 'Svg/LegacyImpl/Sources').mkdir(parents=True)
            Path(root, 'Svg/LegacyImpl/Sources/Legacy.m').write_text('#import <Svg/Svg.h>\n@implementation Legacy\n@end\n')
            write(root, 'App/Main.swift', ['Svg'], '@main\nstruct Main {}\n')
            result = scan(root)
        self.assertEqual(result['repository']['cycles'], 0)

    def test_module_map_overrides_discovery(self):
        with tempfile.TemporaryDirectory() as root:
            clean_repo(root)
            mapping = {'modules': {'Everything': {'kind': 'library', 'import_names': [], 'sources': ['Modules']},
                                   'App': {'kind': 'app', 'import_names': [], 'sources': ['App']}}}
            result = scan(root, mapping)
        self.assertEqual(set(result['modules']), {'App', 'Everything'})
        self.assertEqual(result['modules']['Everything']['kind'], 'library')
        self.assertEqual(result['module_source'], 'map')


if __name__ == '__main__':
    unittest.main()
