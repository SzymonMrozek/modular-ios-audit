# Structure scan

The scan ([structure_scan.py](../scripts/structure_scan.py)) supplies deterministic facts for every evaluator and structural **candidates** for the principle that owns each one. A candidate is a lead, not a verdict: the owning evaluator confirms it as a finding in its principle or dismisses it with counterevidence. The score is withheld while any candidate of a selected principle is unresolved, so the most fundamental problems cannot be skipped.

## Run it

```sh
python3 scripts/structure_scan.py <repo> --output structure.json [--map module-map.json] [--app <dir>] [--exclude <prefix>]
```

Discovery maps imported module names to directories (`Name/`, `Name/Sources`, `Module/Interface` → `ModuleInterface`) and collapses Interface/Implementation/Proto/Testing targets under their owner. Code no module claims falls to its top-level directory; directories with `@main`/`UIApplicationMain` become `app`. Tests, manifests, generated code and vendored directories are skipped.

Discovery is a heuristic. Compare it with the real build manifests (Tuist, XcodeGen, SPM, CocoaPods, Xcode projects). Common misreads: an app folder named like a library module (per-feature dependency registration folders), two directories claiming one module name, or a nested feature folder named like a shared module. When anything disagrees, write a module map from the manifests — `{"modules": {"ID": {"kind", "import_names", "sources", "targets": {"TargetName": ["path"]}}}}` — and rerun. Map kinds are authoritative. Keep both runs in the output folder. Freeze the scan's module IDs as the inventory and copy `consumers`, `consumer_graph_provenance` and `module_weights` into audit data; keep the full scan under `structure` and its candidates under `structural.candidates`.

Reach is computed on the **target** graph and projected to logical modules: consumers that import only `FeatureInterface` do not inherit `FeatureImplementation`'s dependencies. Hosts (`app`, `composition`, `unowned`) depend on everything by design, so hub reach counts library code only.

## Candidates by owning principle

| Archetype | Owner | Trigger | Verify before confirming |
|---|---|---|---|
| `monolithic-module` | P1 | One target holds ≥25% of first-party code (and ≥3k lines or ≥20 files). Floor **high** at ≥40%, or ≥25% with folder reference density ≥35%. | Do its folders hold several features or domains, and construct each other's concrete types (density matrix)? A large module that passes P1's cohesion test is not a monolith. |
| `contamination-hub` | P1 | A consumed target that ≥25% of library code depends on, with ≥2 of: a large imposed dependency tree, ≥2 vendors, re-exports, UI mixed with persistence/networking, ≥8% of code. Floor **high** at ≥50% reach with ≥3 signals. | Do consumers use the dirt (vendor types in public API, re-exported symbols, layer types), or only a small stable core? Which clusters does each consumer need? |
| `mixed-concerns` | P1 | A library mixes UI with persistence or networking: ≥3 files import both, or all three layers appear; ≥3% of code or ≥3k lines. | Does UI code read or write storage or the network directly, or are imports incidental (e.g. `UIImage` in a model)? |
| `parallel-abstractions` | P5 | ≥2 competing libraries for one concern (networking, persistence, reactive streams, DI, images, logging, layout, keychain, JSON mapping), or ≥3 generic first-party mechanisms (`HTTPClient`, `APIClient`, `Router`, `Coordinator`, `Storage`, `Container`…) in ≥2 modules. Severity follows the minority mechanism's spread. | Do they serve the same need, or different ones (WebSocket vs HTTP, cache vs database)? Is a migration in progress with an owner and end state? Must callers know which one to use? |
| `tangled-graph` | P7 | Dependency cycles; a mass-weighted propagation cost ≥30%; or library imports of another module's `Implementation` while it exposes an `Interface`. | Are cycles real build edges? Which ripple modules drive propagation, through contracts or implementations? Are bypassing imports in libraries, or only in composition? |

Thresholds are conservative screens: a well-modularized repository should produce few or no candidates. Do not lower a floor because a pattern is common.

## Confirm or dismiss

Each principle evaluator receives only its own candidates, plus the scan's metrics as shared facts.

1. Read the metrics, inspect the named modules, their public surface and representative consumers, and trace one concrete change.
2. **Confirm** with a finding in the owning principle: `archetype`, `candidate_ids`, `rootCostModuleIDs` (the modules that own the structure; for propagation, the ripple modules), severity at or above the candidate's `severity_floor`, evidence and the principle's correction. Merge candidates sharing one root cause into one finding listing all their IDs.
3. Going **below the floor** requires `floor_override_reason` stating verified counterevidence.
4. **Dismiss** only with a reason and evidence: `{"status": "dismissed", "reason": "…", "evidence": ["path:line"]}`. Say why the metric does not describe a real cost here, not that the pattern is common.

Record resolutions in `structural.resolutions`. Candidates of a principle the user skipped stay listed as skipped and do not block the score. Show dismissed candidates with their reason in that principle's Evidence so readers can see the screen ran.
