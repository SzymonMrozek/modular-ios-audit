#!/usr/bin/env python3
"""Deterministic structure scan: code mass, dependency topology and structural candidates.

The scan produces facts and candidates, never verdicts. Each candidate names the principle that owns it; that
principle's evaluator confirms it as a finding or dismisses it with counterevidence.
"""
import argparse
import fnmatch
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import re

POLICY = 'structure-scan-v2'
SOURCE_SUFFIXES = {'.swift', '.m', '.mm'}
VENDOR_DIRS = {'.git', '.build', 'Pods', 'Carthage', 'DerivedData', 'Derived', 'SourcePackages', 'checkouts',
               'node_modules', 'vendor', 'Vendor', 'ThirdParty', 'third_party', '.swiftpm', 'Tuist', 'fastlane', 'build'}
GENERATED = re.compile(r'(\.pb|\.grpc|\.generated|\+Generated|R\.generated|Generated|\.g)\.swift$|/Generated/|/gen/')
TEST_PART = re.compile(r'(^|/)[^/]*(Tests?|Specs?|Mocks?|TestSupport|TestUtils?|TestsUtils|Testing|UITests|Fixtures|Snapshots?|'
                       r'TestHost|TestsHost|[Tt]ests?-host)(/|$)|(\.tests?|\.spec|Tests?|Specs?|Mocks?)\.(swift|mm?)$')
MANIFESTS = {'Package.swift', 'Project.swift', 'Workspace.swift', 'Tuist.swift', 'Config.swift', 'Dangerfile.swift', 'Podfile'}
# A directory holding one of these declares build targets; discovery trusts such directories over bare folder names.
BUILD_FILES = {'Package.swift', 'Project.swift', 'BUILD', 'BUILD.bazel', 'project.yml'}
BUILD_SUFFIXES = ('.podspec', '.xcodeproj')
TOOLING_IMPORT = re.compile(r'(Test|Mock|Snapshot|Stub|Fixture|PackageDescription|ProjectDescription|^objc$|^XCTest)')
TARGET_SUFFIXES = ('Implementation', 'Interface', 'Impl', 'Proto', 'Testing', 'Mocks', 'TestSupport', 'Sources')
APPLE = set('''Foundation UIKit SwiftUI SwiftUICore Combine CoreData CoreGraphics CoreLocation MapKit AVFoundation AVKit Photos
PhotosUI UserNotifications UserNotificationsUI WebKit StoreKit Security LocalAuthentication CryptoKit CommonCrypto Network os
OSLog Dispatch Darwin ObjectiveC XCTest Testing QuartzCore CoreImage CoreMedia CoreVideo CoreText ImageIO MobileCoreServices
UniformTypeIdentifiers SafariServices AuthenticationServices Contacts ContactsUI CallKit PushKit CoreTelephony
SystemConfiguration BackgroundTasks WidgetKit ActivityKit AppIntents Intents IntentsUI MessageUI LinkPresentation QuickLook
QuickLookThumbnailing PDFKit Vision VisionKit CoreML NaturalLanguage Speech CoreMotion HealthKit EventKit EventKitUI GameKit
SpriteKit SceneKit ARKit RealityKit Metal MetalKit Accelerate Observation SwiftData CoreBluetooth CoreNFC CoreSpotlight
CloudKit FileProvider MediaPlayer AudioToolbox CoreAudio ReplayKit MultipeerConnectivity NotificationCenter Social Accounts
AdSupport AppTrackingTransparency CoreHaptics PassKit Charts TipKit simd zlib CoreFoundation CoreServices Synchronization
RegexBuilder Swift MachO XCUIAutomation DeveloperToolsSupport CoreTransferable ExtensionKit DeviceCheck AdServices
StoreKitTest Foundation_Private _Concurrency libkern sqlite3 Compression CFNetwork Messages MediaToolbox VideoToolbox
CoreAudioKit AudioUnit GLKit OpenGLES ExternalAccessory HomeKit WatchConnectivity ClockKit CarPlay AssetsLibrary
AddressBook AddressBookUI iAd Twitter NetworkExtension CoreMIDI ModelIO PhotosUI_Private MetalPerformanceShaders
MetalPerformanceShadersGraph IOSurface Translation MetricKit AVFAudio AVRouting JavaScriptCore AppKit Cocoa Carbon
SystemPackage OSLog os_log IOKit CoreWLAN SensitiveContentAnalysis BrowserEngineKit LiveCommunicationKit FamilyControls
ManagedSettings DeviceActivity Foundation_ObjC CoreLocationUI MediaAccessibility CoreServicesUI PushToTalk SharedWithYou
SharedWithYouCore Darwin_C mach sys pthread arpa netinet netinet6 netdb notify libc unistd dlfcn ifaddrs objc_runtime
CommonCrypto_Private Accessibility'''.split())
# Competing mechanisms for one concern. Two or more families in use is a parallel-abstraction candidate.
CONCERNS = {
    'networking': {'Alamofire': 'Alamofire', 'Moya': 'Moya', 'Apollo': 'Apollo', 'AFNetworking': 'AFNetworking',
                   'GRPC': 'gRPC', 'GRPCCore': 'gRPC', 'Get': 'Get', 'Siesta': 'Siesta'},
    'persistence': {'CoreData': 'CoreData', 'SwiftData': 'SwiftData', 'RealmSwift': 'Realm', 'Realm': 'Realm',
                    'GRDB': 'GRDB', 'SQLite': 'SQLite.swift', 'FMDB': 'FMDB', 'YapDatabase': 'YapDatabase',
                    'sqlite3': 'sqlite3', 'Couchbase': 'Couchbase', 'CouchbaseLiteSwift': 'Couchbase'},
    'reactive': {'RxSwift': 'Rx', 'RxCocoa': 'Rx', 'RxRelay': 'Rx', 'ReactiveSwift': 'ReactiveSwift',
                 'ReactiveCocoa': 'ReactiveSwift', 'PromiseKit': 'PromiseKit', 'Combine': 'Combine',
                 'OpenCombine': 'Combine', 'Bond': 'Bond', 'ReactiveKit': 'Bond'},
    'dependency-injection': {'Swinject': 'Swinject', 'SwinjectAutoregistration': 'Swinject', 'Resolver': 'Resolver',
                             'Factory': 'Factory', 'NeedleFoundation': 'Needle', 'Cleanse': 'Cleanse', 'Dip': 'Dip',
                             'Dependencies': 'swift-dependencies', 'Weaver': 'Weaver'},
    'images': {'Kingfisher': 'Kingfisher', 'SDWebImage': 'SDWebImage', 'SDWebImageSwiftUI': 'SDWebImage',
               'Nuke': 'Nuke', 'NukeUI': 'Nuke', 'AlamofireImage': 'AlamofireImage', 'PINRemoteImage': 'PINRemoteImage'},
    'logging': {'CocoaLumberjack': 'CocoaLumberjack', 'CocoaLumberjackSwift': 'CocoaLumberjack',
                'SwiftyBeaver': 'SwiftyBeaver', 'XCGLogger': 'XCGLogger', 'Logging': 'swift-log', 'Willow': 'Willow'},
    'layout': {'SnapKit': 'SnapKit', 'PureLayout': 'PureLayout', 'Cartography': 'Cartography',
               'TinyConstraints': 'TinyConstraints', 'Anchorage': 'Anchorage'},
    'keychain': {'KeychainAccess': 'KeychainAccess', 'SAMKeychain': 'SAMKeychain', 'Valet': 'Valet',
                 'KeychainSwift': 'KeychainSwift', 'SwiftKeychainWrapper': 'SwiftKeychainWrapper'},
    'json-mapping': {'SwiftyJSON': 'SwiftyJSON', 'ObjectMapper': 'ObjectMapper', 'Unbox': 'Unbox', 'Mantle': 'Mantle',
                     'HandyJSON': 'HandyJSON'},
}
LAYERS = {'ui': {'UIKit', 'SwiftUI', 'SwiftUICore', 'AppKit'},
          'persistence': {'CoreData', 'SwiftData', 'RealmSwift', 'Realm', 'GRDB', 'SQLite', 'FMDB', 'YapDatabase', 'sqlite3'},
          'networking': {'Alamofire', 'Moya', 'Apollo', 'AFNetworking', 'GRPC', 'GRPCCore', 'Starscream', 'SocketIO', 'Network', 'CFNetwork'}}
# Each structural archetype is evaluated by the principle it violates; candidates are leads for that evaluator only.
OWNERS = {'monolithic-module': 'P1', 'contamination-hub': 'P1', 'mixed-concerns': 'P1', 'parallel-abstractions': 'P5', 'tangled-graph': 'P7'}
# Generic infrastructure roles. A protocol whose name reduces to qualifiers + one role word is a mechanism, not a domain port.
ROLES = {'networking': r'(HTTPClient|APIClient|NetworkClient|NetworkService|Networking|NetworkManager|RequestPerform\w*|'
                       r'RequestExecut\w*|RequestSend\w*|RestClient|WebService|APIService|Transport|HTTPSession|NetworkSession)',
         'persistence': r'(Storage|Store|KeyValueStor\w*|Database|Persistence|PersistentStore|Cache|Caching|Storing)',
         'navigation': r'(Router|Routing|Coordinator|Coordinating|Navigator|Navigation|FlowController|Flow)',
         'dependency-injection': r'(Container|DIContainer|Resolver|Resolving|Assembly|Injector|ServiceLocator|DependencyProvider|Dependencies)',
         'logging': r'(Logger|Logging|LogService|LogWriter)',
         'analytics': r'(Analytics|AnalyticsService|AnalyticsTracker|Tracker|EventTracker|Tracking)'}
QUALIFIERS = r'(Any|Base|Default|Live|Main|Core|App|Shared|Common|Generic|Global|Remote|Local|Secure|Disk|Memory|In|File|Data|' \
             r'Image|HTTP|API|Rest|Web|Async|Combine|Rx|Simple|Standard|Basic|Protocol|Type|Interface|Providing|Provider|Able|Key|Value)*'
IMPORT = re.compile(r'^\s*((?:@\w+(?:\([^)]*\))?\s+)*)(?:(?:public|internal|package|private|fileprivate)\s+)?import\s+'
                    r'(?:(?:typealias|struct|class|enum|protocol|let|var|func)\s+)?([A-Za-z_][A-Za-z0-9_]*)', re.M)
OBJC_IMPORT = re.compile(r'^\s*(?:@import\s+([A-Za-z_]\w*)|#import\s+<([A-Za-z_]\w*)/)', re.M)
DECL = re.compile(r'^\s*(?:@[\w()., ]+\s+)*(?:(?:public|open|internal|package|private|fileprivate|final|indirect|nonisolated)\s+)*'
                  r'(class|struct|enum|protocol|actor|typealias)\s+([A-Za-z_]\w*)', re.M)
PUBLIC = re.compile(r'^\s*(?:@[\w()., ]+\s+)*(?:public|open)\s', re.M)
TOKEN = re.compile(r'\b[A-Z][A-Za-z0-9_]{2,}\b')
APP_MARKER = re.compile(r'@main\b|UIApplicationMain|@UIApplicationMain|NSExtensionPrincipalClass|: *UIApplicationDelegate')
# A file is UI code when it declares or extends views and controllers, not when it merely imports UIKit.
UI_CODE = re.compile(r'\b(UIViewController|UIView|UITableView|UICollectionView|UINavigationController|NSViewController|'
                     r'UIHostingController|some View|:\s*View\b|ViewModifier)\b')
OBJC_HEADER_IMPORT = re.compile(r'^\s*#import\s+<([A-Za-z_]\w*)/', re.M)


def code_lines(text):
    count, block = 0, False
    for line in text.splitlines():
        s = line.strip()
        if block:
            block = '*/' not in s
            continue
        if not s or s.startswith('//'):
            continue
        if s.startswith('/*'):
            block = '*/' not in s
            continue
        count += 1
    return count


def logical_name(name):
    for suffix in TARGET_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[:-len(suffix)]
    return name


def norm(name):
    return re.sub(r'[^a-z0-9]', '', name.lower().replace('-ios-', '-').replace('ios-', '').replace('-ios', ''))


def excluded(rel, patterns):
    """A pattern excludes a path, or everything under it, at component boundaries; `*`/`?`/`[` make it a glob."""
    for pattern in patterns:
        if any(c in pattern for c in '*?['):
            if fnmatch.fnmatchcase(rel, pattern):
                return True
            continue
        prefix = pattern.strip('/')
        if prefix and (rel == prefix or rel.startswith(prefix + '/')):
            return True
    return False


def walk_sources(root, include_tests, extra_excludes, include_files=None):
    allowed = set(include_files) if include_files is not None else None
    for current, dirs, files in os.walk(root):
        rel_dir = Path(os.path.relpath(current, root))
        dirs[:] = [d for d in dirs if d not in VENDOR_DIRS and not d.endswith(('.xcodeproj', '.xcworkspace', '.xcassets',
                   '.bundle', '.framework', '.xcframework', '.playground', '.docc')) and not d.startswith('.')
                   and not excluded((rel_dir / d).as_posix().lstrip('./'), extra_excludes)]
        for name in files:
            path = Path(current, name)
            rel = path.relative_to(root).as_posix()
            if path.suffix not in SOURCE_SUFFIXES or GENERATED.search(rel) or name in MANIFESTS or excluded(rel, extra_excludes):
                continue
            if allowed is not None and rel not in allowed:
                continue
            if not include_tests and TEST_PART.search(rel):
                continue
            yield rel, path


def vendor_names(root):
    """Module names supplied by dependency managers or binary frameworks; they never name first-party folders."""
    names = set()
    for lock in root.glob('**/Podfile.lock'):
        if 'Pods' in lock.parts:
            continue
        names |= set(re.findall(r'^  - "?([A-Za-z0-9_+.-]+)', lock.read_text(errors='replace'), re.M))
    for cart in root.glob('**/Cartfile.resolved'):
        names |= {repo.split('/')[-1] for repo in re.findall(r'^\w+ "([^"]+)"', cart.read_text(errors='replace'), re.M)}
    for resolved in root.glob('**/Package.resolved'):
        text = resolved.read_text(errors='replace')
        names |= set(re.findall(r'"identity"\s*:\s*"([^"]+)"', text)) | set(re.findall(r'"package"\s*:\s*"([^"]+)"', text))
    for current, dirs, _ in os.walk(root):
        for d in list(dirs):
            if d.endswith(('.framework', '.xcframework')):
                names.add(d.rsplit('.', 1)[0])
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', 'DerivedData', '.build')]
    keys = set()
    for name in names:
        base = re.sub(r'^(swift|ios)-|-(ios|swift|sdk|spm)$', '', name.lower())
        keys |= {norm(name), norm(base), norm(base.split('-')[0])}
    return keys - {''}


def extension_dirs(root, extra_excludes):
    """Directories whose Info.plist declares an app extension; their code is a host target, like an app."""
    found = set()
    for plist in root.glob('**/*Info.plist'):
        rel = plist.relative_to(root).as_posix()
        if any(part in VENDOR_DIRS for part in plist.parts) or excluded(rel, extra_excludes):
            continue
        if 'NSExtension' in plist.read_text(errors='replace'):
            found.add(Path(rel).parent.as_posix())
    return found


def has_build_file(root, d):
    folder = root / d
    return folder.is_dir() and any(c.name in BUILD_FILES or c.name.endswith(BUILD_SUFFIXES) for c in folder.iterdir())


def parse(path):
    text = path.read_text(encoding='utf-8', errors='replace')
    imports = []
    for attrs, name in IMPORT.findall(text):
        imports.append((name, '@_exported' in attrs, '@testable' in attrs))
    for a, b in OBJC_IMPORT.findall(text):
        imports.append((a or b, False, False))
    decls = DECL.findall(text)
    return {'loc': code_lines(text), 'imports': imports, 'decls': decls, 'public': len(PUBLIC.findall(text)),
            'tokens': set(TOKEN.findall(text)), 'app_marker': bool(APP_MARKER.search(text)),
            'ui_code': bool(UI_CODE.search(text)), 'header_imports': set(OBJC_HEADER_IMPORT.findall(text))}


def owner_dir(d):
    path = Path(d)
    while path.name in TARGET_SUFFIXES + ('Source', 'src') and path.parent.as_posix() != '.':
        path = path.parent
    return path.as_posix()


def discover(root, files, parsed, app_dirs):
    """Map imported Swift module names to target directories; unowned code falls to its top-level app directory."""
    imported = {name for p in parsed.values() for name, _, _ in p['imports']} - APPLE
    vendors = vendor_names(root)
    wanted = {norm(n): n for n in imported}
    dirs = sorted({Path(rel).parent.as_posix() for rel in files})
    candidates = {}
    for d in dirs:
        parts = Path(d).parts
        for depth in range(len(parts), 0, -1):
            base = Path(*parts[:depth])
            names = [base.name]
            if depth >= 2:
                names.append(parts[depth - 2] + base.name)
                if base.name in ('Sources', 'Source', 'src'):
                    names.append(parts[depth - 2])
            if depth >= 3 and base.name in ('Sources', 'Source'):
                names.append(parts[depth - 3] + parts[depth - 2])
            for n in names:
                if norm(n) in wanted:
                    candidates.setdefault(base.as_posix(), wanted[norm(n)])
                    break
    # A folder only becomes a module by name when nothing contradicts it: a vendor's module name, or a folder nested
    # inside another candidate, needs its own build file. When one name matches several folders, a folder with a
    # build file wins, then the shallowest.
    built = {d: has_build_file(root, d) or has_build_file(root, Path(d).parent.as_posix()) for d in candidates}
    for d in sorted(candidates, key=lambda d: len(Path(d).parts)):
        if d not in candidates:
            continue
        nested = any(a.as_posix() in candidates for a in Path(d).parents)
        if (nested or norm(candidates[d]) in vendors) and not built[d]:
            del candidates[d]
    by_name = defaultdict(list)
    for d, name in candidates.items():
        by_name[name].append(d)
    for name, ds in by_name.items():
        if len(ds) > 1:
            keep = min(ds, key=lambda d: (not built[d], len(Path(d).parts), d))
            for d in ds:
                if d != keep and not built[d]:
                    del candidates[d]
    unit_of = {}
    for rel in files:
        parent = Path(rel).parent
        unit_of[rel] = next((c.as_posix() for c in [parent, *parent.parents] if c.as_posix() in candidates), None)
    used = set(unit_of.values()) - {None}
    units, modules = {}, {}
    for d in sorted(used):
        name = candidates[d]
        mid = owner_dir(d)
        units[name] = {'module': mid, 'dirs': [d]} if name not in units else {**units[name], 'dirs': units[name]['dirs'] + [d]}
        module = modules.setdefault(mid, {'kind': 'library', 'import_names': [], 'sources': []})
        module['import_names'] = sorted(set(module['import_names']) | {name})
        module['sources'] = sorted(set(module['sources']) | {d})
    assignment, unit_assignment = {}, {}
    apps = [a.rstrip('/') for a in app_dirs]
    for rel in files:
        if unit_of[rel]:
            name = candidates[unit_of[rel]]
            assignment[rel], unit_assignment[rel] = units[name]['module'], name
            continue
        app = next((a for a in apps if rel.startswith(a + '/')), None)
        if app is None:
            app = Path(rel).parts[0] if len(Path(rel).parts) > 1 else '(root)'
        assignment[rel], unit_assignment[rel] = app, app
        modules.setdefault(app, {'kind': 'unowned', 'import_names': [], 'sources': [app]})
    return modules, assignment, unit_assignment


def assign_from_map(files, mapping):
    modules = mapping['modules']
    order = sorted(((src.rstrip('/'), mid) for mid, m in modules.items() for src in m['sources']), key=lambda x: -len(x[0]))
    assignment = {}
    for rel in files:
        assignment[rel] = next((mid for src, mid in order if rel == src or rel.startswith(src + '/')), '(unmapped)')
    if '(unmapped)' in assignment.values():
        modules = {**modules, '(unmapped)': {'kind': 'unowned', 'import_names': [], 'sources': []}}
    targets = sorted(((src.rstrip('/'), name) for m in modules.values() for name, srcs in m.get('targets', {}).items()
                      for src in srcs), key=lambda x: -len(x[0]))
    units = {rel: next((name for src, name in targets if rel.startswith(src + '/')), assignment[rel]) for rel in files}
    return modules, assignment, units


def closure(graph, start):
    seen, stack = set(), [start]
    while stack:
        for nxt in graph.get(stack.pop(), ()):
            if nxt not in seen and nxt != start:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def sccs(nodes, graph):
    index, low, stack, on, out, counter = {}, {}, [], set(), [], [0]

    def visit(v):
        index[v] = low[v] = counter[0]; counter[0] += 1; stack.append(v); on.add(v)
        for w in graph.get(v, ()):
            if w not in index:
                visit(w); low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop(); on.discard(w); comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                out.append(sorted(comp))
    import sys
    sys.setrecursionlimit(max(10000, len(nodes) * 4))
    for v in nodes:
        if v not in index:
            visit(v)
    return out


def groups_within(files):
    """Group a module's files by folder, expanding any folder that holds most of the code into its children while its
    siblings stay groups, so a wrapper folder (`Sources/`, `v6.0/`) never hides the folders beside it."""
    common = Path(os.path.commonpath([f for f, _ in files])) if len(files) > 1 else Path(files[0][0]).parent
    groups = {common.as_posix(): files}
    total = sum(loc for _, loc in files) or 1
    for _ in range(12):
        name, members = max(groups.items(), key=lambda kv: sum(loc for _, loc in kv[1]))
        if sum(loc for _, loc in members) / total <= .6:
            break
        depth = len(Path(name).parts) if name not in ('', '.') else 0
        children = defaultdict(list)
        for rel, loc in members:
            parts = Path(rel).parts
            children[Path(*parts[:depth + 1]).as_posix() if len(parts) > depth + 1 else name + '/(files)'].append((rel, loc))
        if len(children) == 1 and next(iter(children)).endswith('/(files)'):
            break
        del groups[name]
        groups.update(children)
    mass = Counter({g: sum(loc for _, loc in fs) for g, fs in groups.items()})
    return common.as_posix(), mass, {rel: g for g, fs in groups.items() for rel, _ in fs}


def divisibility(module_files, parsed):
    """Directed reference density between top-level folders: high density means the module cannot be split cleanly."""
    files = [(rel, parsed[rel]['loc']) for rel in module_files]
    if len(files) < 20:
        return None
    prefix, mass, membership = groups_within(files)
    total = sum(mass.values()) or 1
    major = [g for g, m in mass.items() if m / total >= .02 and not g.endswith('(files)')]
    if len(major) < 3:
        return {'root': prefix, 'groups': len(major), 'density': None}
    group_of = {rel: membership[rel] if membership[rel] in major else None for rel, _ in files}
    declared = defaultdict(set)
    for rel, g in group_of.items():
        if g:
            for kind, name in parsed[rel]['decls']:
                declared[name].add(g)
    unique = {name: next(iter(gs)) for name, gs in declared.items() if len(gs) == 1}
    edges = Counter()
    for rel, g in group_of.items():
        if not g:
            continue
        for token in parsed[rel]['tokens']:
            target = unique.get(token)
            if target and target != g:
                edges[(g, target)] += 1
    pairs = len(major) * (len(major) - 1)
    linked = {pair for pair, n in edges.items() if n >= 2}
    mutual = {tuple(sorted(p)) for p in linked if (p[1], p[0]) in linked}
    return {'root': prefix, 'groups': len(major), 'density': round(len(linked) / pairs, 3),
            'mutual_pairs': len(mutual), 'possible_pairs': pairs // 2,
            'group_mass': {g: mass[g] for g in sorted(major, key=lambda g: -mass[g])}}


def generic_role(name):
    for role, pattern in ROLES.items():
        if re.fullmatch(QUALIFIERS + pattern + r'(Protocol|Type|Interface|ing|able)?', name):
            return role
    return None


def scan(root, mapping=None, app_dirs=(), include_tests=False, excludes=()):
    root = Path(root).resolve()
    files = dict(walk_sources(root, include_tests, excludes, (mapping or {}).get('include_files')))
    extensions = extension_dirs(root, excludes)
    parsed = {rel: parse(path) for rel, path in files.items()}
    if mapping:
        modules, assignment, unit_assignment = assign_from_map(files, mapping)
    else:
        modules, assignment, unit_assignment = discover(root, files, parsed, app_dirs)
    unit_module = {unit_assignment[rel]: assignment[rel] for rel in files}
    name_to_unit = {}
    for mid, m in modules.items():
        for name in m.get('import_names', []):
            name_to_unit[name] = name if name in unit_module else mid
    per = {mid: {'files': [], 'loc': 0, 'public': 0, 'third_party': Counter(), 'exported': set(), 'apple': Counter(),
                 'impl_imports': defaultdict(set), 'app_marker': False} for mid in modules}
    unit_deps, unit_loc, unit_vendors, unit_exported = defaultdict(set), Counter(), defaultdict(set), defaultdict(set)
    # Edges seen only through `#import <X/Header.h>` can be a target including its own public-header namespace; cycle
    # detection uses edges backed by a module import.
    strong_deps, unit_files, unit_layer_files, unit_ui_files = defaultdict(set), Counter(), defaultdict(Counter), Counter()
    for rel, p in parsed.items():
        mid, unit = assignment[rel], unit_assignment[rel]
        row = per[mid]
        row['files'].append(rel); row['loc'] += p['loc']; row['public'] += p['public']
        row['app_marker'] |= p['app_marker'] or any(rel.startswith(d + '/') for d in extensions)
        unit_loc[unit] += p['loc']; unit_files[unit] += 1; unit_ui_files[unit] += p['ui_code']
        names = {name for name, _, _ in p['imports']}
        for layer, frameworks in LAYERS.items():
            unit_layer_files[unit][layer] += bool(names & frameworks) if layer != 'ui' else p['ui_code']
        for name, exported, testable in p['imports']:
            target = name_to_unit.get(name)
            if target:
                if target != unit and target in unit_module:
                    unit_deps[unit].add(target)
                    if name not in p['header_imports'] or sum(1 for n, _, _ in p['imports'] if n == name) > 1:
                        strong_deps[unit].add(target)
                    if unit_module[target] != mid:
                        if exported:
                            row['exported'].add(unit_module[target]); unit_exported[unit].add(target)
                        if name.endswith(('Implementation', 'Impl')):
                            row['impl_imports'][unit_module[target]].add(rel)
            elif name in APPLE:
                row['apple'][name] += 1; unit_vendors[unit].add(name)
            elif not TOOLING_IMPORT.search(name):
                row['third_party'][name] += 1; unit_vendors[unit].add(name)
                if exported:
                    row['exported'].add(name); unit_exported[unit].add(name)
    per = {mid: row for mid, row in per.items() if row['files']}
    ids = sorted(per)
    units = sorted(unit_module)
    total_loc = sum(per[m]['loc'] for m in ids) or 1
    mass = {m: per[m]['loc'] / total_loc for m in ids}
    unit_mass = {u: unit_loc[u] / total_loc for u in units}
    unit_consumers = defaultdict(set)
    for u, ds in unit_deps.items():
        for d in ds:
            unit_consumers[d].add(u)
    unit_dependents = {u: closure(unit_consumers, u) for u in units}
    unit_requires = {u: closure(unit_deps, u) for u in units}
    members = defaultdict(list)
    for u in units:
        members[unit_module[u]].append(u)
    deps = {m: sorted({unit_module[d] for u in members[m] for d in unit_deps[u]} - {m}) for m in ids}
    consumers = {m: sorted(n for n in ids if m in deps[n]) for m in ids}
    dependents = {m: {unit_module[d] for u in members[m] for d in unit_dependents[u]} - {m} for m in ids}
    requires = {m: {unit_module[d] for u in members[m] for d in unit_requires[u]} - {m} for m in ids}
    n = len(ids)
    propagation = sum(len(dependents[m]) + 1 for m in ids) / (n * n) if n else 0
    mass_propagation = sum(unit_mass[u] * sum(unit_mass[d] for d in unit_dependents[u] | {u}) for u in units)
    cycles = sccs(units, strong_deps)
    # A module map's kinds are authoritative. Discovery infers hosts: an app has an entry point and no consumers; a
    # composition root is small wiring that only apps import. A sizeable feature importing many implementations is
    # the defect under audit, not a composition root.
    for m in ids if not mapping else ():
        kind = modules[m].get('kind', 'library')
        if per[m]['app_marker'] and not consumers[m] and kind in ('library', 'unowned'):
            kind = 'app'
        elif kind == 'library' and len(per[m]['impl_imports']) >= 4 and mass[m] < .05 and all(per[c]['app_marker'] for c in consumers[m]):
            kind = 'composition'
        modules[m] = {**modules[m], 'kind': kind}

    def present(counts, files):
        # A layer is present when a meaningful slice of files uses it, not when two stray files import a framework.
        return sorted(layer for layer, count in counts.items() if count >= 3 or files and count / files >= .05 and count)

    def layer_set(m):
        counts, files = Counter(), 0
        for u in members[m]:
            counts.update(unit_layer_files[u]); files += unit_files[u]
        return present(counts, files)

    module_rows = {}
    for m in ids:
        r = per[m]
        bypass = {} if modules[m]['kind'] in ('app', 'composition', 'unowned') else {t: len(fs) for t, fs in r['impl_imports'].items()}
        module_rows[m] = {'kind': modules[m]['kind'], 'import_names': modules[m].get('import_names', []),
                          'files': len(r['files']), 'loc': r['loc'], 'mass_share': round(mass[m], 4),
                          'public_declarations': r['public'], 'fan_out': len(deps[m]), 'fan_in': len(consumers[m]),
                          'transitive_dependents': len(dependents[m]), 'transitive_dependencies': len(requires[m]),
                          'dependents_share': round(len(dependents[m]) / max(n - 1, 1), 4),
                          'dependents_mass_share': round(sum(mass[d] for d in dependents[m]), 4),
                          'third_party': sorted(r['third_party']), 'exported': sorted(r['exported']),
                          'layers': layer_set(m), 'implementation_imports': bypass}
    hosts = {m for m in ids if modules[m]['kind'] in ('app', 'composition', 'unowned')}
    excluded_names = {Path(e.rstrip('/')).name for e in excludes}
    library_mass = sum(mass[m] for m in ids if m not in hosts) or 1
    library_reach = {}
    for m in ids:
        reached = {unit_module[d] for u in members[m] for d in unit_dependents[u]} - {m} - hosts
        library_reach[m] = sum(mass[d] for d in reached) / library_mass
        module_rows[m]['library_dependents_mass_share'] = round(library_reach[m], 4)
    candidates = []

    def add(archetype, modules_, metrics, severity, trigger):
        candidates.append({'id': f'C-{archetype}-{len([c for c in candidates if c["archetype"] == archetype]) + 1}',
                           'archetype': archetype, 'principle': OWNERS[archetype], 'modules': sorted(modules_),
                           'severity_floor': severity, 'trigger': trigger, 'metrics': metrics})

    # Monolithic host: one target owns the codebase, and its folders reference each other densely.
    for m in ids:
        share = mass[m]
        if share >= .25 and (per[m]['loc'] >= 3000 or len(per[m]['files']) >= 20):
            split = divisibility(per[m]['files'], parsed)
            # Folders that reference each other in both directions cannot be extracted one at a time.
            dense = split and split.get('density') is not None and (split['density'] >= .35 or split['mutual_pairs'] / split['possible_pairs'] >= .1)
            severity = 'high' if share >= .4 or share >= .25 and dense else 'medium'
            add('monolithic-module', [m], {'mass_share': round(share, 3), 'loc': per[m]['loc'], 'files': len(per[m]['files']),
                'kind': module_rows[m]['kind'], 'divisibility': split}, severity,
                f'{share:.0%} of first-party code in one target' + (f'; {split["mutual_pairs"]} of {split["possible_pairs"]} folder pairs reference each other' if dense else ''))
    # Contamination hub: a consumed target most library code depends on that drags dependencies, vendors or mixed layers along.
    # Hosts (app/composition/unowned) depend on everything by design, so reach counts library code only; dirt must sit
    # in the same target consumers import, which keeps an Implementation behind an Interface from counting.
    for m in ids:
        best = None
        for u in members[m]:
            reach_modules = {unit_module[d] for d in unit_dependents[u]} - {m} - hosts
            reach = sum(mass[d] for d in reach_modules) / library_mass
            # Only dragged vendors are dirt: ones most of the hub's consumers do not already import themselves.
            consumers_u = [c for c in unit_consumers[u] if unit_module[c] not in hosts]
            vendors = {v for v in unit_vendors[u] if v not in APPLE and v not in excluded_names
                       and sum(v in unit_vendors[c] for c in consumers_u) < max(1, len(consumers_u)) / 2}
            layers = present(unit_layer_files[u], unit_files[u])
            imposed = {unit_module[d] for d in unit_requires[u]} - {m}
            dirt = [k for k, ok in (('drags a dependency tree', len(imposed) >= max(8, .1 * n)),
                    ('drags vendors', len(vendors) >= 2), ('re-exports', bool(unit_exported[u])),
                    ('mixes layers', len(layers) >= 2), ('large', unit_mass[u] >= .08)) if ok]
            if reach >= .25 and len(dirt) >= 2 and (best is None or (len(dirt), reach) > (len(best[1]), best[0])):
                best = (reach, dirt, u, sorted(vendors), layers, len(imposed), len(reach_modules))
        if best:
            reach, dirt, u, vendors, layers, imposed, reached = best
            severity = 'high' if reach >= .5 and len(dirt) >= 3 else 'medium'
            add('contamination-hub', [m], {'target': u, 'library_dependents_mass_share': round(reach, 3),
                'library_dependents': reached, 'imposed_dependencies': imposed, 'vendors': vendors, 'layers': layers,
                'exported': sorted(unit_exported[u]), 'target_mass_share': round(unit_mass[u], 4), 'dirt': dirt}, severity,
                f'{reach:.0%} of library code depends on {u}; ' + ', '.join(dirt))
    # Tangled graph: cycles, high propagation cost or implementation edges that bypass declared interfaces.
    if cycles:
        biggest = max(cycles, key=len)
        add('tangled-graph', {unit_module[u] for c in cycles for u in c}, {'cycles': cycles, 'largest_cycle': len(biggest)},
            'high', f'{len(cycles)} dependency cycle(s); largest spans {len(biggest)} modules')
    if n >= 8 and mass_propagation >= .3:
        # Root the propagation at the modules that drive it most (own size × reach), not at every widely imported module.
        ripple = sorted((m for m in ids if m not in hosts and library_reach[m] >= .25), key=lambda m: -mass[m] * library_reach[m])
        add('tangled-graph', ripple[:10], {'propagation_cost': round(propagation, 3), 'mass_propagation_cost': round(mass_propagation, 3),
            'ripple_modules': {m: round(library_reach[m], 3) for m in ripple[:10]}, 'widely_imported_modules': len(ripple)},
            'high' if mass_propagation >= .5 else 'medium', f'a change reaches {mass_propagation:.0%} of code on average')
    bypass = {m: sorted(module_rows[m]['implementation_imports']) for m in ids if module_rows[m]['implementation_imports']}
    if bypass:
        affected = set(bypass) | {t for ts in bypass.values() for t in ts}
        add('tangled-graph', affected, {'implementation_imports': bypass},
            'medium' if len(affected) / max(n, 1) < .15 else 'high', f'{sum(map(len, bypass.values()))} imports bypass an Interface target')
    # Missing separation of concerns: a sizeable library mixing UI with persistence or networking. Hosts are judged as monoliths.
    for m in ids:
        row = module_rows[m]
        if m not in hosts and 'ui' in row['layers'] and len(row['layers']) >= 2 and (row['mass_share'] >= .03 or row['loc'] >= 3000):
            mixed_files = sum(1 for rel in per[m]['files'] if parsed[rel]['ui_code'] and
                              {i[0] for i in parsed[rel]['imports']} & (LAYERS['persistence'] | LAYERS['networking']))
            if mixed_files < 3 and len(row['layers']) < 3:
                continue
            add('mixed-concerns', [m], {'layers': row['layers'], 'mixed_files': mixed_files, 'mass_share': row['mass_share']},
                'high' if row['mass_share'] >= .1 and len(row['layers']) == 3 else 'medium',
                f'{" + ".join(row["layers"])} in one target; {mixed_files} files mix layers')
    # Parallel abstractions: competing mechanisms for one concern, by vendor family and by generic first-party protocols.
    usage = defaultdict(lambda: defaultdict(set))
    for m in ids:
        for name in set(per[m]['third_party']) | set(per[m]['apple']):
            for concern, families in CONCERNS.items():
                family = families.get(name)
                if family:
                    usage[concern][family].add(m)
    protocols = defaultdict(lambda: defaultdict(set))
    for rel, p in parsed.items():
        for kind, name in p['decls']:
            if kind == 'protocol':
                role = generic_role(name)
                if role:
                    protocols[role][name].add(assignment[rel])
    for concern in sorted(set(usage) | set(protocols)):
        families = {f: sorted(ms) for f, ms in usage[concern].items()}
        mechanisms = defaultdict(set)
        for name, ms in protocols[concern].items():
            mechanisms[re.sub(r'(Protocol|Interface|Type|ing|able)$', '', name) or name] |= ms
        mechanisms = {k: sorted(v) for k, v in mechanisms.items()}
        owners = {m for ms in mechanisms.values() for m in ms}
        competing = families if concern != 'reactive' or len([f for f in families if f != 'Combine']) else {}
        vendor_parallel = len(competing) >= 2
        # Infrastructure roles a codebase should have once can compete even inside one module; storage and analytics
        # legitimately have several per-domain types, so they need more evidence.
        protocol_parallel = (len(mechanisms) >= 3 and len(owners) >= 2 if concern in ('persistence', 'analytics')
                             else len(mechanisms) >= 2)
        if not (vendor_parallel or protocol_parallel):
            continue
        touched = {m for ms in families.values() for m in ms} | owners
        # The minority mechanism's spread decides severity: one stray import is a migration leftover, not a split codebase.
        spreads = sorted((sum(mass[m] for m in ms), len(ms)) for ms in families.values()) if vendor_parallel else []
        minority_mass, minority_modules = spreads[-2] if len(spreads) >= 2 else (0, 0)
        if vendor_parallel and minority_mass >= .15 and minority_modules >= 3 or protocol_parallel and len(mechanisms) >= 4 and len(owners) >= 3:
            severity = 'high'
        elif vendor_parallel and (minority_modules >= 2 or minority_mass >= .05) or protocol_parallel and len(owners) >= 2:
            severity = 'medium'
        else:
            severity = 'low'
        add('parallel-abstractions', touched, {'concern': concern, 'vendor_families': families, 'generic_protocols': mechanisms,
            'minority_mass_share': round(minority_mass, 3), 'touched_mass_share': round(sum(mass[m] for m in touched), 3)}, severity,
            f'{concern}: ' + ', '.join(filter(None, [f'{len(competing)} competing libraries ({", ".join(sorted(competing))})' if vendor_parallel else '',
                                                       f'{len(mechanisms)} generic mechanisms in {len(owners)} module(s)' if protocol_parallel else ''])))
    order = {'high': 0, 'medium': 1, 'low': 2}
    candidates.sort(key=lambda c: (order[c['severity_floor']], -sum(mass.get(m, 0) for m in c['modules'])))
    top = sorted(ids, key=lambda m: -mass[m])
    hhi = sum(v * v for v in mass.values())
    return {'policy': POLICY, 'root': str(root), 'module_source': 'map' if mapping else 'discovered',
            'repository': {'modules': n, 'files': len(parsed), 'loc': total_loc,
                           'largest_module': top[0] if top else None, 'largest_share': round(mass[top[0]], 4) if top else None,
                           'top3_share': round(sum(mass[m] for m in top[:3]), 4), 'concentration_hhi': round(hhi, 4),
                           'effective_modules': round(1 / hhi, 1) if hhi else None,
                           'propagation_cost': round(propagation, 4), 'mass_propagation_cost': round(mass_propagation, 4),
                           'cycles': len(cycles), 'unowned_share': round(sum(mass[m] for m in ids if module_rows[m]['kind'] in ('unowned', 'app')), 4)},
            'modules': module_rows, 'consumers': consumers, 'module_weights': {m: per[m]['loc'] for m in ids},
            'consumer_graph_provenance': {'source': f'{POLICY} regex import scan of first-party sources', 'tests_included': include_tests},
            'candidates': candidates}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--map', type=Path, help='Module map: {"modules": {"ID": {"kind", "import_names", "sources"}}}')
    parser.add_argument('--app', action='append', default=[], help='Directory of an app/extension target for unowned code')
    parser.add_argument('--exclude', action='append', default=[], help='Repository-relative path prefix to skip')
    parser.add_argument('--include-tests', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    mapping = json.loads(args.map.read_text(encoding='utf-8')) if args.map else None
    result = json.dumps(scan(args.root, mapping, args.app, args.include_tests, args.exclude), indent=2) + '\n'
    if args.output:
        args.output.write_text(result, encoding='utf-8')
    else:
        print(result, end='')
