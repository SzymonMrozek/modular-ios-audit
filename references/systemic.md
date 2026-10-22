# S — Systemic structure

Core issue: a structural property of the whole module graph makes most changes expensive, regardless of how clean individual contracts are. These problems dominate an audit. Find and decide them **before** principle-level findings, and rank them first when their impact is comparable.

The scan ([structure_scan.py](../scripts/structure_scan.py)) supplies deterministic facts and **candidates**. A candidate is a lead, not a verdict. The systemic evaluator confirms each one as an `S` finding or dismisses it with counterevidence. The score is withheld while any candidate is unresolved.

## Run the scan

```sh
python3 scripts/structure_scan.py <repo> --output structure.json [--map module-map.json] [--app <dir>] [--exclude <prefix>]
```

Discovery maps imported module names to directories (`Name/`, `Name/Sources`, `Module/Interface` → `ModuleInterface`) and collapses Interface/Implementation/Proto/Testing targets under their owner. Code no module claims falls to its top-level directory; directories with `@main`/`UIApplicationMain` become `app`. Tests, manifests, generated code and vendored directories are skipped. When discovery disagrees with the real build graph, write a module map (`{"modules": {"ID": {"kind", "import_names", "sources", "targets"?}}}`) from the resolved manifests and rerun. Freeze the scan's module IDs as the audit inventory, copy `consumers`, `consumer_graph_provenance` and `module_weights` into audit data, and keep the full scan under `structure`.

Reach is computed on the **target** graph and projected to logical modules: consumers that import only `FeatureInterface` do not inherit `FeatureImplementation`'s dependencies. Hosts (`app`, `composition`, `unowned`) depend on everything by design, so hub reach counts library code only.

## Archetypes

| Archetype | Trigger (scan) | Verify before confirming | Typical correction |
|---|---|---|---|
| `monolithic-module` | One target holds ≥25% of first-party code (and ≥3k lines or ≥20 files). Floor **high** at ≥40%, or ≥25% with folder reference density ≥35%. | Do its folders hold several features or domains? Do they construct each other's concrete types (the density matrix)? Is anything already extracted? A large module with one cohesive responsibility and low density is not indivisible. | Make the target composition-only. Extract the most-referenced seam first behind an interface; show the full target map. |
| `contamination-hub` | A consumed target that ≥25% of library code depends on, and ≥2 of: imposes a large dependency tree, imports ≥2 vendors, re-exports, mixes UI with persistence/networking, holds ≥8% of code. Floor **high** at ≥50% reach with ≥3 signals. | Do consumers use the dirt (vendor types in public API, re-exported symbols, layer types), or only a small stable core? Which capability clusters do actual consumers need? | Split the stable foundation (values, contracts) from the capabilities that drag dependencies; consumers import the foundation. |
| `tangled-graph` | Dependency cycles; a mass-weighted propagation cost ≥30% (a change reaches that share of code on average); or library imports of another module's `Implementation` while it exposes an `Interface`. | Are cycles real build edges or regex artefacts? Which ripple modules cause most propagation, and is it through contracts or implementations? | Break cycles with an owned contract; route feature-to-feature access through interfaces; move composition to the app. |
| `mixed-concerns` | A library mixes UI with persistence or networking: ≥3 files import both, or all three layers appear; ≥3% of code or ≥3k lines. | Is UI code reading/writing storage or the network directly, or are imports incidental (e.g. `UIImage` in a model)? | Separate the data/service capability from presentation; UI depends on an owner operation, not storage or transport. |
| `parallel-abstractions` | Two or more competing libraries for one concern (networking, persistence, reactive streams, DI, images, logging, layout, keychain, JSON mapping), or ≥3 generic first-party mechanisms (`HTTPClient`, `APIClient`, `Router`, `Coordinator`, `Storage`, `Container`…) declared in ≥2 modules. Severity follows the minority mechanism's spread. | Do the mechanisms serve the same need, or different ones (WebSocket vs HTTP, cache vs database)? Is a migration in progress, with an owner and an end state? Do callers have to know which one to use? | Choose one mechanism per concern; adapt the other behind it; show the migration boundary and the rule that blocks new use. |
| `other` | Not produced by the scan. | Use when verification exposes a whole-graph defect none of the above describes (e.g. a shared mutable singleton every feature reaches). Apply the same evidence threshold. | — |

Thresholds are deliberately conservative screens: a clean modular repository should produce few or no candidates. Do not lower a floor because a pattern is common in the ecosystem.

## Confirm or dismiss

For each candidate:

1. Read the scan metrics, then inspect the named modules, their public surface and representative consumers. Trace one concrete change through the graph.
2. **Confirm** with an `S` finding: `archetype`, `candidate_ids`, `rootCostModuleIDs` (the modules that own the structure; for propagation, the ripple modules), severity at or above the candidate's `severity_floor`, evidence and a correction. Merge candidates that share one root cause into one finding listing all their IDs.
3. Going **below the floor** requires `floor_override_reason` stating the verified counterevidence (e.g. "consumers use only the value types; vendors never appear in public signatures").
4. **Dismiss** only with a reason and evidence: `{"status": "dismissed", "reason": "…", "evidence": ["path:line", …]}`. A dismissal says why the metric does not describe a real cost here, not that the problem is common.

Record resolutions in `systemic.resolutions`. A principle evaluator can also tag a systemic cause it independently finds (e.g. P1 overbroad module that is also the contamination hub); reconciliation merges duplicates into the `S` finding and keeps principle-specific consequences separate.

## Presentation

The S panel comes first. Each finding names the archetype, the scan metric that triggered it and the module or folder map that shows the mechanism (density matrix, hub dependency fan, cycle, competing-mechanism table). List dismissed candidates with their reason in Evidence so readers can see the screen ran.
