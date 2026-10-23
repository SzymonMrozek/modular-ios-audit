# Risk scoring

Read before mapping modules or dispatching evaluators. Each principle answers one question a reader can check against the counts on the page: **what share of the modules own or directly import its open defects, weighted by how serious they are?** The headline is the worst principle. Fourteen defect modules reaching 36 of 40 modules must read as HIGH, never as a small number. Scores are project policy, not industry benchmarks or a probability of failure.

## Scope and inventory

Freeze the first-party logical-module inventory at the audited ref, using the structure scan's module IDs ([structure-scan.md](structure-scan.md)). App, extension and composition targets **are** inventory modules: they own code, and a monolithic host is a defect owner. Collapse Interface/Implementation/Proto/resources/tests under the owning module; exclude generated/vendor code and empty placeholders. Record tooling outside the inventory as external scope.

Accept explicit user module exclusions as `excluded_modules: [{"module":"Modules/…","reason":"…"}]`. Resolve names to unique inventory IDs before evaluation; ask only for ambiguous matches. Do not infer exclusions from a module's name or purpose. Excluded modules leave classification, exposure and the module denominator; their edges are dropped without splicing transitive paths. Compare scores only with the same scope; a denominator change is not an improvement.

Use the scan's direct consumer graph (deduplicated logical consumers, no self edges, production imports). Label it snapshot import exposure, not resolved build-graph truth. `consumer_graph_complete: true` requires every eligible module as a key and a nonempty `source` or `authority` in `consumer_graph_provenance`; otherwise risk is N/A.

Every module counts as one module. The scan's `module_weights` (lines of code) may stay in audit data as a fact for P1's monolith analysis, but they never weight the score: a reader must be able to recompute it from module counts.

## Qualify a finding before scoring it

- `kind: issue`: a verified owner defect with a concrete consumer/change consequence and evidence.
- `kind: suggestion`: a possible clarity/polish improvement without that consequence. Unscored; it never makes a module an issue owner.
- Insufficient inspection is `unassessed`/uncertain, not clear and not a verified issue.

For P2 inspect recoverability of meaning, competing interpretations and actual caller work. For P3 distinguish meaningful domain values/read-only access from leaked representation or owner invariants. A unit ambiguity belongs to P2; do not duplicate it under P3 without a separate exposed decision.

## Severity anchors

Severity follows consequence, never popularity. Use the anchor that matches the traced mechanism; when two fit, take the lower unless the evidence shows the higher one's consequence.

| Severity | Weight | Anchor |
|---|---:|---|
| low | 0.1 | Local clarity or maintenance cost; one owner and its direct callers; no invariant at risk. |
| medium | 0.4 | Repeated cross-boundary knowledge, conversion or representation coupling; independent components bundled in one module; several consumers must change together. |
| high | 1.0 | An invariant or authority can be bypassed, or a structure forces broad coordinated change: monolithic host, contamination hub, cycle, competing mechanisms used across the codebase. |
| critical | 1.0 | Demonstrated serious impact: unauthorized state change, data loss or a security boundary bypass. |

Findings that confirm a structural candidate must meet its `severity_floor` unless `floor_override_reason` records verified counterevidence. That floor is what keeps the same repository from scoring differently between runs.

## Exposure and risk

`rootCostModuleIDs` are evidenced defect owners. Owners always count: a defect in a leaf or app target still exposes that target's code. Who else a defect reaches is set per finding with `exposure`:

| `exposure` | Reaches | Use when |
|---|---|---|
| `importers` (default) | every direct importer of the roots | every importer inherits the defect: an umbrella or two-role module, a contamination hub, a leaked representation in the module's core contract |
| `verified` | the roots plus `reach_modules` (consumers the evaluator traced) | the defect sits in one API of a widely imported module and only some importers use it; list those importers in `reach_modules` |
| `owners` | the roots only | the importers do not inherit it: an edge or manifest defect (undeclared, forbidden or cyclic import), or a defect behind an interface that consumers never import (`implementation_only: true` is the legacy spelling) |

Root the defect where it lives. An edge or manifest defect is rooted at the **importing** module with `exposure: owners`: the importer's own consumers are not affected by its undeclared import. If that importer is outside the inventory (e.g. a test-only target), record it under `external_scopes` with no roots. Targets that consumers reach only through another target of the same module (Data or Assembly behind Domain, Implementation behind Interface) count as behind an interface.

**One mechanism bypassed at several sites** (formatting, decoding or validation re-implemented in N modules) has one convention, so defect-module counts stay comparable between runs:

- If a shared owner already offers the operation and modules bypass it, the defect is in each copy: root at the bypassing modules with `exposure: owners`.
- If no module owns the operation yet, or its contract forces the copies (missing capability, wrong unit), root at the module that should own it with `exposure: verified` and list the copying modules in `reach_modules`.

Both forms involve the same modules and score the same; the convention decides what "defects in N modules" means.

A module is **involved** when it owns or is reached by an open defect. Each involved module counts once, at the strongest open defect that reaches it:

`risk = Σ over involved modules of maxWeight / number of eligible modules`

- **Principle risk** applies it to that principle's findings: "P1 · defects in 14/40 · 36/40 involved · 33.8%".
- **Overall risk** (the headline) is the **worst principle's risk**: "Risk 33.8% · worst principle P1 One clear responsibility". It never exceeds the rows below it. The union of involved modules across all principles ("37/40 modules involved across all principles") and the defect-module count stay beside it as counts, not as the score: added across eight principles they read like a sum and would put a repository with only moderate principle rows into HIGH.
- **Finding impact** applies it to one finding; `ranking` orders findings by impact, structural first on ties. The report lists the top five as "Top problems by risk" with principle, severity, defect modules and involved modules.

Splitting one problem into several findings cannot raise the score, and a module with several defects still counts once. A cross-tagged identical finding counts once. When one cause is cross-tagged but its consequence differs by principle, keep the record identical and set `principle_severity: {"P8": "low"}`; each principle row then weighs it at its own severity. Principle rows also show their open issue count, because several issues on the same module do not add risk. External-only P7 enforcement keeps rule-family counts and never enters risk. A principle is external-only when `scoring_scope: external-only` is set or every one of its **issues** has no roots; rooted suggestions do not change that.

Bands use the exact fraction: **LOW < 3%, MEDIUM 3–< 10%, HIGH ≥ 10%**. There is no derived health index; show the risk percentage with the module counts it comes from.

With fewer than 10 eligible modules (`small_inventory: true`) one module is at least 10% of the denominator, so any medium finding in the app reads HIGH and the score saturates on the host. The report says so; compare such repositories by their issue counts and principle rows, not by the headline alone.

The score is **withheld** (N/A) while any structural candidate of a selected principle is unresolved, or any included principle's risk is unknown. Never take the worst of only the known parts.

Calibration from full audits (worst principle; union of involved modules in brackets): an Interface/Implementation-modularized app with a design-system umbrella imported by 24 of 64 modules → 20.0% HIGH, P1 (41/64); the same app after splitting the umbrella into per-component modules → 6.7% MEDIUM, P8 (56/153); a feature-modular app with a shared umbrella imported by 31 of 40 modules → 33.8% HIGH, P1 (37/40).

## Compact findings and review choices

A low or medium issue that involves **at most 2 modules** and has **impact strictly below 2%** is a **tiny issue** in presentation; high and critical issues never are. The module limit keeps a large inventory from hiding most medium findings, where 2% alone would mean eight or more modules; suggestions remain unscored. Unknown impact is not tiny. Presentation never changes the original kind, consequence, score or evidence.

Show full issues first. Put tiny issues and suggestions in one closed **Suggestions & tiny issues** group per principle, using short rows with a title and risk. Keep the complete problem, fix, code and Evidence behind each row's disclosure; deep links open both levels. A tiny issue still contributes its small risk until handled.

Keep source findings/ledger immutable. Apply a separate `decisions` map keyed by stable finding ID:

```json
{"p2-f1":{"status":"resolved","decided_by":"user"}}
```

Statuses: `open`, `resolved`, `invalid` (**Invalid for this repo**), `accepted` (**Acceptable for this project**). Show three compact, mutually exclusive checkboxes; selecting one replaces any earlier choice and recalculates immediately. Uncheck it to reopen. **No reason, text field, confirmation or per-issue Apply step.** Provide one optional **Recalculate** button in the score header. These are user review annotations, not agent-verified code repairs. Only explicit user input may assign a non-open status.

Resolved/invalid/accepted findings remain visible with source evidence and status, but leave adjusted risk and open root/affected sets. The "before review choices" risk retains the original evidence under the same scope. The original ledger does not become clear because of a checkbox. Legacy `intended` choices migrate to `accepted`.

Persist choices locally when possible; keep Export/Import/Reset and module scope in one closed **Scope & saved choices** disclosure. Exports retain the exact audit-input fingerprint, choices and exclusions; reject a mismatched audit or unknown finding/module IDs. After code/ref/evidence changes, revalidate annotations.

## Coverage and gates

Each selected principle keeps a module ledger: `issue`, `clear`, `not-applicable`, `unassessed`, with a basis. Missing = unassessed. Ledger issue owners equal the union of evidenced `kind: issue` roots. Coverage is classified/applicable modules; `coverage_min` is the weakest included principle. Assess the largest and most-imported modules first. Scores remain observed lower bounds with unassessed code.

Per-principle numeric HIGH is a local Fail; unknown classifications/checks, or unresolved structural candidates, keep a principle Incomplete. These local statuses do not become a report-wide verdict: show the overall risk and band, not an overall PASS/FAIL badge. `overall_gate` stays in the scorer output only for older machine consumers and follows the adjusted band.

## Helpers and input

Run `python3 scripts/structure_scan.py <repo> --output structure.json` first, then `python3 scripts/score_audit.py audit-data.json --output scores.json`. Python stdlib is enough.

Audit data retains `modules`, `consumers`, `consumer_graph_complete`, provenance, optional `module_weights` (a fact, not a weight), `structure` (scan output), `structural` (`candidates` from the scan, each with its owning `principle`, and `resolutions`) and `principles`. Optional `excluded_modules` and `decisions` default empty. Findings require `id`, `severity`, `severity_reason`, `rootCostModuleIDs`, `reach_modules`, `external_scopes`, `evidence`; findings confirming candidates add `archetype` and `candidate_ids`; `exposure` and `principle_severity` are optional. Ledger rows require status/basis. Legacy `hard_gates` stay check observations. `scoring_scope: external-only` and per-family `enforcement_cases` keep P7's separate denominator. Audits without `structural` still score but report `structural.screened: false`; never deliver one as a complete audit.

The scorer rejects duplicate IDs, unknown modules, self edges, conflicting cross-tags, confirmations that name no finding in the owning principle, findings below their structural floor without a reason, dismissals without evidence, and custom thresholds.

Prepare the populated HTML with `python3 scripts/prepare_report.py audit-data.json report.html`. It validates data/anchors, embeds canonical input and the shared browser scoring/navigation assets, prints a `file://` URL and requests the default **external** browser. Use `--no-open` for automated verification. Exported decisions can be applied with `score_audit.py audit-data.json --decisions audit-decisions.json --output scores.json`. Browser and Python arithmetic must pass parity tests after changes.
