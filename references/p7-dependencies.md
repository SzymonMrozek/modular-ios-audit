# P7 — Enforce the dependency graph

Core issue: boundaries rely on convention while tooling permits undeclared or forbidden relationships.

Cycles, propagation cost and Interface bypass are also screened structurally ([systemic.md](systemic.md)); P7 owns whether tooling enforces the intended graph.

Establish the intended graph rules from module ownership and applicable project policy, then inspect the effective build graph, source/API references, visibility, check logic, exclusions and validation invocation. Do not infer policy solely from target suffixes or assume every local architectural convention applies everywhere.

Consider graph properties independently: declared direct edges, allowed direction/layer or implementation access, cycles (including contract-only cycles), and coverage/bypasses of those checks. Inspect generated/re-exported/conditional relationships, target source membership and SDK/vendor boundaries where they affect the effective graph. Adapt to packages, projects, mixed-language or generated code rather than assuming a particular manifest generator. These are discovery lenses; the import example is one enforcement case. Compiler/build-generation enforcement can suffice; a custom linter is not mandatory.

Good:

```text
EditorImplementation -> DocumentStoreInterface
AppComposition -> DocumentStoreImplementation
DocumentStoreTests -> DocumentStoreImplementation
Automated validation rejects EditorImplementation -> DocumentStoreImplementation
```

Bad: guidelines prohibit cross-feature implementation imports, but Editor imports DocumentStoreImplementation and ordinary validation permits it.

Report separately:

- Actual violation: the forbidden/undeclared edge, supported by imports/manifests and applicable boundary policy.
- Enforcement gap: a prohibited relationship existing checks fail to reject. A currently clean graph can still have this gap.
- Uncertainty: enforcement or coverage cannot be inspected sufficiently.

State graph observations and enforcement confidence separately: inspected edges can satisfy the policy while check logic or invocation remains unavailable. A prose assertion about validation is not execution evidence, and uncertainty about enforcement is not an observed graph violation.

Read actual check logic, coverage, and invocation. Its filename or existence proves no enforcement. Distinguish inspected logic from execution evidence. Claim successful rejection only with execution evidence. Use an isolated fixture for any negative probe; do not inject violations into the user's checkout.

When recommending a new or changed graph check, include a concrete lint-rule example in the fix, rather than only saying "add validation." Show its inputs, rejection condition, actionable diagnostic and proposed local/CI invocation, with one forbidden case and its corrected passing case. For a direct-import finding specifically, compare each imported local module with the importing target's effective **direct** dependencies; transitive availability is insufficient. Obtain source membership and dependencies from resolved build metadata (including applicable templates, exclusions, configuration conditions and generator replacement semantics), and imports from a syntax-aware source. Keep SDK/vendor classification and legitimate target-specific exceptions explicit. A regex that bans an import suffix cannot enforce this graph relationship.

Match the enforcement example to the violated property: a cycle or forbidden-direction finding needs the corresponding graph check, not just direct-import comparison. A runnable comparison core over normalized graph/import records is useful for that specific case, but label any missing extraction adapter and do not present fixture success as end-to-end repository enforcement. Distinguish a proposed rule from installed linting, and state which properties it checks; direct-import validation alone does not establish cycle or forbidden-layer enforcement. See [report.md](report.md) for presentation.

For import/manifest sweeps, verify dependency-owned symbol use for every reported edge. Classify unused-import-only mismatches as hygiene rather than an active behavioral dependency. A public signature still creates a type dependency when its stored collaborator is unused; consider removing that dead API/plumbing before adding an unnecessary dependency. Preserve all verified edges and distinguish them from raw candidate counts.

Accept composition's implementation imports, tests of their own implementation, and imports of standalone components/shared values. An `Interface` counterpart is not mandatory. Evaluate the actual graph policy: it can govern implementation access, layer direction, cycles or other declared restrictions. Standalone modules still need their actual dependency relationships encoded; their names do not make them exempt. Generated dependencies are valid when they explicitly encode the actual graph.

Assess repository-specific exceptions rather than enforcing suffixes blindly. A cycle through implementation modules does not become acceptable merely because two features need to open each other.
