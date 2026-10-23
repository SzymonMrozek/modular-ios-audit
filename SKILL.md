---
name: modular-ios-audit
description: Audit an iOS codebase for modular architecture health. Runs a deterministic structure scan, then evaluates eight principles with a dedicated evaluator each — routing structural problems (monolithic targets, contamination hubs, mixed concerns, parallel abstractions, tangled graphs) to the principle they violate — and scores each principle as the severity-weighted share of modules that own or import its defects, headlined by the worst principle. Use for an architecture assessment, boundary review, or modularity audit; supports skipping principles. Excludes build-speed and agent-workflow optimization advice.
license: MIT
compatibility: Requires repository read and shell access, Python 3.10+, and Pygments for highlighted diffs. Independent evaluations require subagents. Browser tooling is optional.
metadata:
  version: "0.2.0"
---

# Modular iOS audit

Evaluate the design principles in [Modular iOS Architecture for Agentic Coding](https://mrozek.dev/posts/modular-ios-architecture-for-agentic-coding). The rubrics incorporate the author's reviewed interpretation. Exclude operational advice about cache tuning, selective testing, scaffolding, linking, and workflow telemetry. Explaining a boundary's dependency-node invalidation radius is in scope; claiming measured rebuild/cache/test effects requires evidence.

Deliver a complete, evidence-backed inventory with concise explanations and concrete code corrections, ordered so the most consequential, structural problems come first. The risk score is the primary signal: it must follow the module counts a reader sees and rank a tangled codebase above a well-modularized one. Audit code; do not change it unless separately requested. Respect the audited repository’s instructions, validation requirements and write permissions.

## Runtime portability

Resolve bundled files relative to this SKILL.md, never the audited repository's working directory. Run helper scripts by their resolved paths using an available Python 3 interpreter. Keep generated reports in a durable user-accessible output folder; never write into the installed skill. The HTML template is a working synthetic example, not source evidence for the current audit.

An installation may be a symlink. Resolve its real directory before directory-wide searches; if a glob does not follow the link, read the referenced resource directly rather than treating it as missing.

Use the host agent’s own repository, shell, delegation and browser tools. No Codex-specific MCP server, Claude-only command, project generator, DI library or simulator is required. A read-only architecture audit does not require building an iOS app. Run a build or negative probe only when it is relevant, permitted and available; state unverified checks rather than assuming success. Pygments is the only report-rendering package dependency; Node and Playwright are optional development-test dependencies.

## Select scope

Interpret selections by ID or name: “P1, P3”, “skip P5 and P8”, or equivalent natural language. Default to all eight. The structure scan always runs; its candidates for a skipped principle are listed as skipped. Ask only if selection is ambiguous or contradictory. State the selected scope before evaluation. Skipped principles get no evaluator and no verdict. Accept explicit modules to ignore as names or stable paths; resolve ambiguous matches before evaluating. Offer a concise optional “Modules to ignore?” input when no exclusion preference is known, continue independent discovery, and default to none if omitted. Record exclusions/reasons in the shared map and report; never infer them from a module name. Read scoring.md for scope filtering and denominator changes.

| ID | Principle | Evaluator reference |
|---|---|---|
| P1 | One clear responsibility | [p1-responsibility.md](references/p1-responsibility.md) |
| P2 | Local understanding | [p2-local-understanding.md](references/p2-local-understanding.md) |
| P3 | Information hiding | [p3-information-hiding.md](references/p3-information-hiding.md) |
| P4 | Feature entry points | [p4-entry-points.md](references/p4-entry-points.md) |
| P5 | Abstraction when useful | [p5-useful-abstraction.md](references/p5-useful-abstraction.md) |
| P6 | Explicit composition | [p6-composition.md](references/p6-composition.md) |
| P7 | Enforced dependency graph | [p7-dependencies.md](references/p7-dependencies.md) |
| P8 | Ergonomic boundaries | [p8-ergonomics.md](references/p8-ergonomics.md) |

## Prepare shared facts

Start with the deterministic structure scan: `python3 scripts/structure_scan.py <repo> --output structure.json` (see [structure-scan.md](references/structure-scan.md)). Check its module discovery against the real build system; when it disagrees, write a module map from the resolved manifests and rerun. Its module IDs and direct consumer graph become the frozen inventory and graph; its per-module code size is a fact, not a score weight. Its repository metrics (code concentration, effective modules, propagation cost, cycles) and per-module metrics are shared facts; each candidate names its owning principle (P1, P5 or P7) and goes only to that evaluator.

Inspect the repository’s actual module/build system, ownership, public contracts, feature/service invocation paths, composition roots and relevant instructions. Map declared dependencies, standalone versus split modules, source/resource/test membership and validation entry points. Follow data/state ownership and platform/vendor boundaries where relevant. Distinguish authored from generated/vendor code. Include tests as evidence of contracts and consumption; do not assume a particular UI, concurrency, DI or project-generation framework.

For broad libraries, map parallel exported capabilities, actual consumers of each, their internal interdependence, and capability-specific dependencies/resources. Identify targets serving two roles: foundational dependency and umbrella of independently usable components. A shared name or technical layer does not establish one responsibility.

Read [scoring.md](references/scoring.md) before building the shared map and dispatching evaluators. Freeze the logical module inventory and scoring policy; retain per-principle module classifications, root-cost module identities, unique affected-module sets and cross-cutting gates.

Record repository/ref or working-tree state and requested scope. Include relevant uncommitted changes. Do not reset, stash, or overwrite work. If code changes during evaluation, re-evaluate affected evidence before reporting.

The shared map contains facts, not preliminary verdicts. Enumerate candidates systematically before deep tracing. For each supported problem, sweep its related declarations, callers, composition and tests across the selected scope; do not stop after one convincing example. Distinguish verified occurrences, search matches, justified cases and uninspected candidates. Large repositories may limit verification; disclose those limits rather than silently capping examples or claiming exhaustiveness.

## Discover from principles, not example matches

Each rubric states a general criterion; its examples, search terms and inspection lenses are illustrative and non-exhaustive. Derive candidates from the repository’s responsibilities, contracts, workflows and change scenarios before searching for familiar symptoms. Use past findings as illustrations, not a closed catalog of defects.

For every enabled principle, inspect relevant mechanisms beyond the named examples and record which surfaces/scenarios were covered or unavailable. A repository can satisfy the criterion with a different module structure or idiom. Neither an absent example pattern nor a matching type name establishes a verdict. Apply the evidence threshold to novel patterns, examine counterexamples and explain the causal connection to that principle. Do not force a finding or a fixed number of lenses/examples when the code does not support one.

Keep discovery separate from correction and presentation. The correction sketches and grouped HTML layout illustrate how to explain a verified finding; they do not prescribe the architecture every repository must adopt. Preserve iOS-specific lifecycle/platform constraints where present, while choosing the smallest repair suited to the actual owner and interaction model.

## Delegate independently

Create exactly one dedicated evaluator per enabled principle. P1, P5 and P7 also receive their structural candidates and must confirm or dismiss each one. Each reads its assigned reference and relevant source, declarations, callers, and checks. Give it:

- Its principle ID and reference path, this skill's evidence and return requirements, and requested scope.
- Repository location/state, the shared factual module inventory/map, and [scoring.md](references/scoring.md)'s counting, coverage and gate requirements.
- Permission to inspect and run permitted nonmutating checks, but no permission to fix code, change configuration, or message other chats.

Do not give principle evaluators the scan candidates, suspected findings or other evaluators' conclusions before their independent assessments; scan metrics are facts they may use. Bound concurrency by available slots, scheduling remaining evaluators as slots free up. Do not merge principles into one evaluator to save slots. If delegation is unavailable, disclose that independent evaluation cannot be fulfilled and offer a labeled single-agent alternative; never claim independence.

### Evidence requirements

- Inspect declarations and consumers before making a finding. Apply the principle's specific evidence threshold.
- Return all supported distinct problems and all reasonable verified examples found for each, grouped by root cause. Operations in one consumer can be supporting occurrences; search matches and repeated references are not additional defects.
- Explain a concrete change scenario: what changes, which boundary makes unrelated consumers participate, and why. Separate structural coupling from observed failures or measured cost. "Shared change surface" alone is not an explanation.
- Prioritize changes to abstractions, types, domain models, owner operations and access boundaries that remove the knowledge requirement or enforce the missing guarantee. For competing units requiring conversion/validation, use an explicit unit/value model; for sequencing-sensitive operations put the sequence behind an owner-controlled operation or subscription. Use a precise name when it fully expresses a simple established meaning; use types/owner operations when they enforce a real unit, state or interaction distinction. A public primitive, absent wrapper or missing comment alone is a suggestion, not an architectural error. Comments supplement remaining constraints. Preserve correct behavior and justify any new lifetime, scheduling or conversion policy; do not invent a runtime failure or add an abstraction without a demonstrated responsibility.
- Show a small before/after code example for every problem, grounded in inspected declarations and callers. Include manifest/import or composition changes where those are the fix. Label proposed APIs and omitted context; do not claim snippets compile or preserve behavior without checking. Read [fix-examples.md](references/fix-examples.md) when preparing corrections.
- Consider legitimate counterexamples, configuration, lifetimes, and ownership. One implementation, many imports, missing comments, or `AnyView` proves no violation on its own.
- Separate observations from inferences. Unrun checks have not passed; inspected logic is not proof that a check successfully rejected a violation.
- Do not edit the repository to demonstrate failure. Any necessary negative probe uses an isolated temporary fixture exercising the actual enforcement logic, not a rewritten imitation.
- Return uncertainty for insufficient evidence. Skipped by user is distinct from unable to evaluate.

### Evaluator return contract

Return these fields concisely:

```text
principle: Pn
status: issue | clear-in-scope | uncertain
coverage: modules/files, discovery surfaces/scenarios traced, checks inspected/run, uninspected areas
ledger: one module identity -> issue | clear | not-applicable | unassessed, with inspection basis
hard_gates: legacy check observations, with reason and evidence; no overall gate override
check_unknowns: required checks not demonstrated
findings:
  - title: concrete boundary defect
    kind: issue | suggestion, justified by a traced consequence or its absence
    severity: low | medium | high | critical, using the anchors in scoring.md, with consequence-based reason (independent of graph popularity)
    archetype, candidate_ids, floor_override_reason: findings that confirm structural candidates; see structure-scan.md
    implementation_only: true when the defect lives only in an implementation target that consumers reach through an interface
    rootCostModuleIDs: unique module identities containing the defect, with evidence
    reach_modules: verified semantic consumers; affectedModuleIDs are computed separately from the frozen direct-consumer graph
    external_scopes: app targets/tooling outside the module inventory
    evidence: absolute paths with verified line numbers and relevant symbols
    trace: caller -> contract -> implementation/check, as applicable
    consequence: concrete change/behavior and the coupling mechanism
    correction: smallest useful code/interface/ownership correction
    fix_example:
      before: relevant current code, with source provenance
      diff: git-style unified excerpt with red removals, green additions, replacement emphasis and module/file identity
      after: proposed code and affected boundary/composition changes
      invariants: behavior, scope, lifetime and concurrency to preserve
      validation: inspected | compiled | behavior-probed, with actual limits
    examples:
      - label: distinct repository occurrence or capability cluster
        evidence: verified declaration and consumer paths/lines
        trace: actual consumption/assembly path
        consequence: how this occurrence demonstrates the problem
    counterevidence: alternatives/exceptions considered
excluded: checked candidates that are justified or insufficiently supported
limitations: missing evidence, unverified matches or uninspected scope
```

Use `issue` when at least one supported finding exists, preserving any uncertainty elsewhere. `clear-in-scope` means no issue found within stated coverage, never a guarantee about uninspected code. Prioritize by demonstrated consequence, not number of violated principles. Assess the largest and most-imported modules first; an unassessed hub is a bigger gap than many unassessed leaves. Evaluators that receive structural candidates also return `resolutions: candidate -> confirmed (finding id) | dismissed (reason, evidence)`.

## Reconcile and present

Check evaluator evidence against its rubric. Ask the same evaluator to resolve missing traces or contradictions. Combine duplicate causes into one finding tagged with relevant IDs; a structural finding keeps its owning principle and is cross-tagged where other evaluators found the same cause. Independent defects at one location remain separate. Do not manufacture one finding per principle. Score with [scoring.md](references/scoring.md): the severity-weighted share of modules that own or directly import an open defect, each module counted once at its strongest defect. The headline is the worst principle's risk, **Risk N% · worst principle Pn**, with its LOW / MEDIUM / HIGH band and the modules involved across all principles beside it as a count; it is withheld while any structural candidate of a selected principle is unresolved. Show the top problems by risk with their defect/involved module counts under the headline, each principle's risk and coverage, and no aggregate PASS/FAIL badge.

When feedback challenges a finding or its correction, revisit its mechanism and counterevidence and broaden the related consumer sweep. When a score contradicts an informed reviewer's ranking of repositories, check the structure scan's discovery and the candidate resolutions before adjusting rubrics. Generalize recurring causes across modules rather than adding filters for the named example or assuming the user's hypothesis is always a defect. If asked to improve this skill, encode the general decision rule and correction shape, not repository-specific names or a closed list of past failures.

Before final assembly, read [report.md](references/report.md) and inspect/render [report-template.html](assets/report-template.html). Default to its visual, self-contained HTML: one blunt sentence in each of “Describe the problem”, “Why it’s a problem” and “How to fix it”; current-only visuals under the problem; proposed visuals first under the fix, followed by syntax-highlighted git diffs. Preserve useful dot/dash capability tables. Outside those three comments use facts, labels, tables, diagrams and code; keep full reasoning in closed Evidence, not visible prose. Adapt the template to the actual findings; do not concatenate evaluator reports into a prose-heavy page. Honor a user-requested format/style; plain Markdown is the fallback. List every supported problem in P1 → P8 order, with all verified examples available beneath its problem; do not impose a top-three or one-example quota. Keep the hierarchy clear: principle → distinct problem/module case → supporting occurrences. A brief chat handoff may link the complete report. Every problem needs its consequence mechanism, concrete fix example, verified evidence and rule. Group every problem's current/proposed source changes by module or repository scope → file/type → code, including same-file API edits, callers, tests and lint/configuration changes. For visual reports, selecting a principle shows every issue as a readable, collapsed disclosure with root-cost/affected metrics. Give each issue a stable direct link; open the correct principle and issue for deep links, preserve browser Back/Forward and keyboard navigation, and expose all grouped fixes when expanded. Use the template’s embedded navigation behavior; collapse nested occurrence/source inventories by default. Never show summed per-owner consumer counts as affected modules. Include explicit module exclusions and compact Resolved / Invalid for this repo / Acceptable for this project checkboxes, with no reason field or confirmation. Recalculate on change; provide one score-header Recalculate button, and keep import/export/reset closed. Only user choices remove a finding from adjusted risk. Show low or medium issues with observed impact under 2% as compact rows in one closed Suggestions & tiny issues group, retaining full fixes and evidence through deep links. Show relocations through actual source/destination file identities and diff hunks. Omit generic MOVES/STAYS badges. Use the concise section labels and phase ordering in report.md. Highlight whole Swift/Python/shell/Objective-C and other iOS snippets before slicing diff hunks; preserve source text and multiline syntax state. Do not fill every section with a generic box/arrow chain; use a dependency topology, call sequence, state/authority model, protocol capability map or rule-result comparison that explains the actual mechanism. Omit a diagram when the diff or text is sufficient.

Deliver an accessible local URL using [prepare_report.py](scripts/prepare_report.py); prefer opening the OS default external browser rather than an agent-only preview. Verify the saved report and its links are readable, print/link its file URL, and state any browser-opening limitation. Follow [report.md](references/report.md) for the self-contained interactive report contract.
