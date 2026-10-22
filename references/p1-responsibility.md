# P1 — One clear responsibility

Core issue: a module boundary combines independently changing responsibilities or splits one responsibility so its decisions must be maintained across owners. Evaluate cohesion by the capability, policy or invariant delivered and the consumers/reasons for change, not by technical labels.

Whole-target concentration (a monolithic app or module) and contamination hubs are screened by the systemic evaluator ([systemic.md](systemic.md)); P1 still evaluates responsibility boundaries inside and around them, and cross-tags rather than duplicates a confirmed S finding.

Inspect public APIs, internal collaboration, consumers, tests, resources and declared dependencies. Different technical layers can serve one responsibility: search history may own values, persistence, behavior and tests; a feature may own views, state and internal navigation. A shared technical layer is not sufficient cohesion.

## Discover responsibilities

Trace public operations, state/data ownership, workflows and the rules they maintain. Look across product features, domain policies, infrastructure services, platform integrations and shared components; these are discovery lenses, not required module categories. Compare actual independent change scenarios and the types that must collaborate to preserve an invariant. A module name, folder, public-type count or UI layer does not define its responsibility.

Also inspect coherent rules fragmented across targets: if changing one owned decision requires synchronized edits in modules that each expose only a mechanical step, consider bringing those private collaborators together. Separate implementations, deployment targets and deliberately reusable contracts can justify a split. Do not treat every cross-module workflow as fragmentation.

## Parallel capabilities and multiple module roles

Look for exported sibling components that are independently useful and do not collaborate to deliver one feature or invariant. This applies to services, storage, networking, formatting, controls and other components; do not frame the rule around a particular library name or a visual design system.

Trace contrasting consumers and component-specific behavior/dependencies. For example, a common library exports measurement formatting, attachment upload and retry policy. One caller needs formatting, another needs upload, and a background service needs retry. Coexistence in one directory is not the defect: the only importable boundary makes three independent capabilities one dependency node.

A particularly clear case is a module with two roles: consumers import it for foundational values (for example IDs, colors or configuration values), while the same target exports independent higher-level components using those foundations. The foundational consumer must take the umbrella too. Separate these roles: independent components depend on a focused foundation boundary; foundations must not require the aggregate component module.

## Explain the consequence

Name an independent change and trace the affected graph:

```text
Before: ReportScreen ┐
        UploadFlow ──┼─> CommonKit [formatting | upload | retry]
        SyncJob ─────┘                         ↑ upload-only change

After:  ReportScreen -> MeasurementFormatting -> CoreValues
        UploadFlow  -> AttachmentUpload -> CoreValues
        SyncJob     -> RetryPolicy
```

In a module-granular dependency/validation system, an upload-only edit can invalidate the shared CommonKit node. Consumers of formatting or retry can consequently need revalidation because their dependency is that whole node. Splitting the graph lets the change follow AttachmentUpload's actual dependents. Inspect actual edges; distinguish this structural invalidation radius from measured compiler, cache or test-run behavior. Do not assert that every compiler rebuilds every dependent or every test must run without evidence of the toolchain's rules. No cache-tuning recommendation is needed to explain the consequence.

Also explain public-contract, ownership or resource coupling where present. A past bug or measured build cost is not required for a structural finding, but "shared change surface" cannot replace the trace.

## Correction

When independence is established, recommend a separately importable module for **each independent component/capability identified**, with its private collaborators, tests and resources. Do not dilute this to "extract one someday" or leave independent siblings in the umbrella without justification. A staged first step can be useful, but show the complete target boundary map.

Use the repository’s real boundary mechanism: an independently consumable and enforced target, product or submodule can provide this separation without a separate project/package or a particular generator. Verify that consumers can select the capability and its actual dependency boundary independently; a namespace or wrapper inside the same inseparable aggregate is not equivalent.

This is not one module per Swift type. Helpers and tightly collaborating types supporting one capability stay together. Common foundations may be their own focused module. A composition convenience aggregate can remain if justified and consumers can directly import narrower modules. A standalone component does not require an Interface/Implementation pair.

Show the proposed manifest/import graph and changed consumer import in code; see [fix-examples.md](fix-examples.md). Enumerate verified component clusters and actual consumers under each overbroad module problem, with nested evidence collapsed in visual reports.

Finding threshold: for an overbroad module, establish independently consumed capabilities, why they are parallel rather than one cohesive feature, and how their combined boundary broadens change/invalidation or ownership. For fragmentation, show a coherent owned decision spread across mechanical module boundaries, the synchronized changes it requires, and why those splits provide no independent capability, reuse or deployment boundary. Do not flag size, type count, multiple layers, private helpers or hypothetical splittability alone. Equally, do not dismiss clear independent components merely because they share styling or a broad label.
