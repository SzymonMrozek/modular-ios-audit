# Structure scan

The scan ([structure_scan.py](../scripts/structure_scan.py)) supplies deterministic facts for every evaluator and structural **candidates** for the principle that owns each one. A candidate is a lead, not a verdict: the owning evaluator confirms it as a finding in its principle or dismisses it with counterevidence. The score is withheld while any candidate of a selected principle is unresolved, so the most fundamental problems cannot be skipped.

## Run it

```sh
python3 scripts/structure_scan.py <repo> --output structure.json [--map module-map.json] [--app <dir>] [--exclude <prefix>] [--history-days 365 | --no-history]
```

Discovery maps imported module names to directories (`Name/`, `Name/Sources`, `Module/Interface` → `ModuleInterface`) and collapses Interface/Implementation/Proto/Testing targets under their owner. Code no module claims falls to its top-level directory; directories with `@main`/`UIApplicationMain` become `app`. Tests, manifests, generated code and vendored directories are skipped.

Discovery rules, so you know what to check:

- `--exclude` matches whole path components (`RecurringBuy/` and `RecurringBuy` both skip that folder, never `RecurringBuyFlow`), works on single files, and accepts globs (`Api/SecretApiLayer*.swift`).
- Module names supplied by dependency managers or binary frameworks (`Podfile.lock`, `Cartfile.resolved`, `Package.resolved`, `*.framework`, `*.xcframework`) never claim a first-party folder, unless that folder has its own build file.
- A folder nested inside another module only becomes a module when it has its own build file (`Package.swift`, `Project.swift`, `BUILD`, `project.yml`, `*.podspec`, `*.xcodeproj`). When one name matches several folders, a folder with a build file wins, then the shallowest.
- Test hosts and mock targets (`*TestHost`, `*-tests-host`, `*Mocks`, `*TestUtils`) are tests. Folders whose `Info.plist` declares `NSExtension` are host targets, like the app.
- An edge seen only as `#import <X/Header.h>` does not create a cycle: a target may include its own public-header namespace.

Discovery is a heuristic. Compare it with the real build manifests (Tuist, XcodeGen, SPM, CocoaPods, Xcode projects). Common misreads: an app folder named like a library module (per-feature dependency registration folders), two directories claiming one module name, or a nested feature folder named like a shared module. When anything disagrees, write a module map from the manifests — `{"modules": {"ID": {"kind", "import_names", "sources", "targets": {"TargetName": ["path"]}}}, "include_files": [...]}` — and rerun. Map kinds are authoritative. `sources` entries may be folders or single files; `include_files`, when present, limits the scan to exactly the files the build compiles (use it when targets compile a subset of a folder, or when orphan files sit next to real sources). A file compiled into two targets belongs to the target that owns it; note the other membership in the shared map.

The scan cannot read `.xcodeproj` targets or Bazel rules itself. For Xcode projects, list each target's source folders and synchronized groups from the project. For Bazel, use `bazel query` when it is available, or read the `BUILD` files' `srcs` and `deps` declaratively; never execute repository files to evaluate them. Keep both runs in the output folder. Freeze the scan's module IDs as the inventory and copy `consumers`, `consumer_graph_provenance` and `module_weights` into audit data; keep the full scan under `structure` and its candidates under `structural.candidates`.

Reach is computed on the **target** graph and projected to logical modules: consumers that import only `FeatureInterface` do not inherit `FeatureImplementation`'s dependencies. Hosts (`app`, `composition`, `unowned`) depend on everything by design, so hub reach counts library code only.

## Change history

In a git checkout the scan adds `history`: facts about how each module actually changed during the `--history-days` (default 365) window ending at the audited commit's date, so a rerun at the same ref gives the same counts. `--no-history` skips it; outside git it reports `available: false` with a reason.

- **Change set**: one first-parent commit with its merge diff, so a squash-merged request and a merged branch each count once. Paths map to the module owning their nearest current folder, so tests, resources, manifests and deleted files inside a module's folders count as changes to it.
- **Fix**: a conventional `fix`/`bugfix`/`hotfix` type, a fix branch in a merge subject, bug/crash/regression/fix words or a revert. It is a commit-message heuristic: report it as "fix change sets", never as defects or incidents.
- **Sweep**: a change set touching more than a quarter of the modules (at least 10) is a rename, format or toolchain bump; it is counted in `sweeps_excluded` and nowhere else.

Per module: `changes`, `fixes`, `with_consumers` (change sets that also edited a direct library importer), `fixes_with_consumers`, `coordinated` (edited with 2+ library importers), `library_consumers`, `consumers_co_changed` (distinct importers ever edited with it), and for modules with three or more major folder groups `group_changes`/`single_group_changes`. Hosts (app, composition) never count as co-changed importers, because they wire every change by design.

With at least 50 change sets in the window, history supports a **high** P1 floor (`p1_floor`, `p1_floor_basis`) when it shows the high anchor's "broad coordinated change":

- **Importer coupling**: 10+ coordinated change sets, and 10+ library importers co-changed, or 10+ fix change sets edited it with an importer and 5+ importers co-changed.
- **Monolith traffic**: at least half of all change sets went through the module, and at least 60% of its 20+ folder-touching change sets stayed inside one folder group — independent work queued through one target.

Co-change with a few importers is ordinary feature work, so history never sets a medium or low floor, never lowers one, and lifts only medium P1 findings: a low finding forces no code change by definition.

Renames inside a module and moves of a whole module are followed back through the window, so a module whose folder moved keeps its history. A move counts as whole when the old folder is gone and at least 90% of the files leaving it kept their place inside one module. Files split out of a module that lives on, or out of one dissolved into several, are not followed: their earlier changes stay with the folder they came from, so a new module's history starts at the split. History creates no candidates: it only weighs a P1 finding an evaluator has confirmed from the code. P1 candidates carry their modules' history rows in `metrics.history`.

For an umbrella or monolith finding, count how its evaluated clusters change with the cluster helper:

```sh
python3 scripts/history_scan.py <repo> --clusters clusters.json --output cluster-history.json
# clusters.json: {"module": "Modules/UI", "clusters": {"Button": ["Modules/UI/Sources/Button*.swift"], "Card": ["…"]}}
```

It reports change sets per cluster, how many touched exactly one cluster, and which pairs ever changed together: direct evidence for the cohesion test's "independent clusters".

## Candidates by owning principle

| Archetype | Owner | Trigger | Verify before confirming |
|---|---|---|---|
| `monolithic-module` | P1 | One target holds ≥25% of first-party code (and ≥3k lines or ≥20 files). Floor **high** at ≥40%, or ≥25% with dense folders: ≥35% one-way reference density, or ≥10% of folder pairs referencing each other. Folder groups expand any folder holding most of the code into its children while its siblings stay groups, so a wrapper folder never hides the folders beside it. | Do its folders hold several features or domains, and construct each other's concrete types (density matrix)? A large module that passes P1's cohesion test is not a monolith. |
| `contamination-hub` | P1 | A consumed target that ≥25% of library code depends on, with ≥2 of: a large imposed dependency tree, ≥2 vendors its consumers do not already import themselves (Apple and excluded vendored modules never count), re-exports, two layers each used by ≥3 files or ≥5% of its files, ≥8% of code. Floor **high** at ≥50% reach with ≥3 signals. | Do consumers use the dirt (vendor types in public API, re-exported symbols, layer types), or only a small stable core? Which clusters does each consumer need? |
| `mixed-concerns` | P1 | A library mixes UI code (views, view controllers, view modifiers; not a bare `import UIKit`) with persistence or networking: ≥3 UI files import storage or transport, or all three layers appear; ≥3% of code or ≥3k lines. | Does UI code read or write storage or the network directly, or are imports incidental (e.g. `UIImage` in a model)? |
| `parallel-abstractions` | P5 | ≥2 competing libraries for one concern (networking, persistence, reactive streams, DI, images, logging, layout, keychain, JSON mapping), or competing generic first-party protocols: ≥2 networking, navigation, DI or logging mechanisms (`HTTPClient` and `APIClient`, `Router` and `Coordinator`), even inside one module, or ≥3 storage or analytics protocols in ≥2 modules. Severity follows the minority mechanism's spread. The screen cannot see concrete duplicate stacks (two HTTP clients, two loggers): P5 must search for them. | Do they serve the same need, or different ones (WebSocket vs HTTP, cache vs database)? Is a migration in progress with an owner and end state? Must callers know which one to use? |
| `tangled-graph` | P7 | Dependency cycles; a mass-weighted propagation cost ≥30%, rooted at its ten biggest drivers (own size × reach), with the count of all widely imported modules in the metrics; or library imports of another module's `Implementation` while it exposes an `Interface`. | Are cycles real build edges? Which ripple modules drive propagation, through contracts or implementations? Are bypassing imports in libraries, or only in composition? |

Thresholds are conservative screens: a well-modularized repository should produce few or no candidates. Do not lower a floor because a pattern is common.

## Confirm or dismiss

Each principle evaluator receives only its own candidates, plus the scan's metrics as shared facts.

1. Read the metrics, inspect the named modules, their public surface and representative consumers, and trace one concrete change.
2. **Confirm** with a finding in the owning principle: `archetype`, `candidate_ids`, `rootCostModuleIDs` (the modules that own the structure; for propagation, the ripple modules), severity at or above the candidate's `severity_floor`, evidence and the principle's correction. Merge candidates sharing one root cause into one finding listing all their IDs.
3. Going **below the floor** requires `floor_override_reason` stating verified counterevidence.
4. **Dismiss** only with a reason and evidence: `{"status": "dismissed", "reason": "…", "evidence": ["path:line"]}`. Say why the metric does not describe a real cost here, not that the pattern is common.

Record resolutions in `structural.resolutions`. Candidates of a principle the user skipped stay listed as skipped and do not block the score. Show dismissed candidates with their reason in that principle's Evidence so readers can see the screen ran.
