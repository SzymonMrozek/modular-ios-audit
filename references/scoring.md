# Architecture health scoring

Read before mapping modules or dispatching evaluators. The headline answers one question: **how much of the codebase is exposed to open, consequential defects?** It must order repositories the way an experienced reviewer would: a tangled, monolithic codebase scores clearly below a well-modularized one, however many small issues the latter has. Scores are project policy, not industry benchmarks or a probability of failure.

## Scope and inventory

Freeze the first-party logical-module inventory at the audited ref, using the structure scan's module IDs ([systemic.md](systemic.md)). App, extension and composition targets **are** inventory modules: they own code, and a monolithic host is a defect owner. Collapse Interface/Implementation/Proto/resources/tests under the owning module; exclude generated/vendor code and empty placeholders. Record tooling outside the inventory as external scope.

Accept explicit user module exclusions as `excluded_modules: [{"module":"Modules/…","reason":"…"}]`. Resolve names to unique inventory IDs before evaluation; ask only for ambiguous matches. Do not infer exclusions from a module's name or purpose. Excluded modules leave classification, exposure and the mass denominator; their edges are dropped without splicing transitive paths. Compare scores only with the same scope; a denominator change is not an improvement.

Use the scan's direct consumer graph (deduplicated logical consumers, no self edges, production imports). Label it snapshot import exposure, not resolved build-graph truth. `consumer_graph_complete: true` requires every eligible module as a key and a nonempty `source` or `authority` in `consumer_graph_provenance`; otherwise risk is N/A.

**Code mass.** Copy the scan's `module_weights` (non-blank, non-comment source lines per module) into audit data. Every module's share of the score equals its share of the code. Without weights the scorer falls back to equal module weights and reports `weighting: equal`; disclose that it under-represents large modules.

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
| medium | 0.2 | Repeated cross-boundary knowledge, conversion or representation coupling; several consumers must change together. |
| high | 0.4 | An invariant or authority can be bypassed, or a structure forces broad coordinated change: monolithic host, contamination hub, cycle, competing mechanisms used across the codebase. |
| critical | 0.7 | Demonstrated serious impact: unauthorized state change, data loss or a security boundary bypass. |

Systemic findings must meet their candidate's `severity_floor` unless `floor_override_reason` records verified counterevidence. That floor is what keeps the same repository from scoring differently between runs.

## Exposure and risk

`rootCostModuleIDs` are evidenced defect owners. A finding **exposes** its roots plus their direct consumers (`affectedModuleIDs`). Owners count: a defect in a leaf or app target still exposes that target's code.

Per module, take the strongest open consequence **within each dimension** — each principle P1–P8, and each systemic archetype — then combine dimensions:

`moduleRisk = 1 − Π_dimensions (1 − maxWeight)`

`risk = Σ mass(module) × moduleRisk / Σ mass(eligible)`

Splitting one problem into several findings in the same dimension cannot raise the score; distinct kinds of problems on the same code compound. A cross-tagged identical finding counts once, under its first principle. External-only P7 enforcement keeps rule-family counts and never enters risk.

**Architecture health = round(100 × (1 − risk)).** Bands use the exact risk fraction, not the rounded health: LOW < 10%, MEDIUM 10–< 25%, HIGH ≥ 25%. Principle rows show the same formula restricted to that principle. Each finding's impact is its own risk; `ranking` orders open and reviewed findings by impact, systemic first on ties — present the top problems in that order.

The score is **withheld** (N/A) while any systemic candidate is unresolved, or any included principle's risk is unknown. Never average only the known parts.

Calibration (structure scan, systemic findings at their floors, before principle findings): a Tuist-modularized app with Interface/Implementation pairs → health 100; three tangled production apps with dominant app targets and hubs → 38, 25 and 21. Principle findings then lower clean repositories modestly and messy ones further.

## Compact findings and review choices

A verified issue with **impact strictly below 1%** is a **tiny issue** in presentation; suggestions remain unscored. Unknown impact is not tiny. Presentation never changes the original kind, consequence, score or evidence.

Show full issues first. Put tiny issues and suggestions in one closed **Suggestions & tiny issues** group per principle, using short rows with a title and risk. Keep the complete problem, fix, code and Evidence behind each row's disclosure; deep links open both levels. A tiny issue still contributes its small risk until handled.

Keep source findings/ledger immutable. Apply a separate `decisions` map keyed by stable finding ID:

```json
{"p2-f1":{"status":"resolved","decided_by":"user"}}
```

Statuses: `open`, `resolved`, `invalid` (**Invalid for this repo**), `accepted` (**Acceptable for this project**). Show three compact, mutually exclusive checkboxes; selecting one replaces any earlier choice and recalculates immediately. Uncheck it to reopen. **No reason, text field, confirmation or per-issue Apply step.** Provide one optional **Recalculate** button in the score header. These are user review annotations, not agent-verified code repairs. Only explicit user input may assign a non-open status.

Resolved/invalid/accepted findings remain visible with source evidence and status, but leave adjusted risk and open root/affected sets. Observed health retains the original evidence under the same scope. The original ledger does not become clear because of a checkbox. Legacy `intended` choices migrate to `accepted`.

Persist choices locally when possible; keep Export/Import/Reset and module scope in one closed **Scope & saved choices** disclosure. Exports retain the exact audit-input fingerprint, choices and exclusions; reject a mismatched audit or unknown finding/module IDs. After code/ref/evidence changes, revalidate annotations.

## Coverage and gates

Each selected principle keeps a module ledger: `issue`, `clear`, `not-applicable`, `unassessed`, with a basis. Missing = unassessed. Ledger issue owners equal the union of evidenced `kind: issue` roots. The `S` ledger is implied by the scan (every module screened); confirmed roots are its owners. Coverage is reported both as counts and as **assessed code mass**; `assessed_mass_min` is the weakest included principle. Assess the largest modules first: an unassessed giant module is a larger gap than many unassessed leaves. Scores remain observed lower bounds with unassessed code.

Per-principle numeric HIGH is a local Fail; unknown classifications/checks keep a principle Incomplete; S is Incomplete while candidates are unresolved. These local statuses do not become a report-wide verdict: show the health score and band, not an overall PASS/FAIL badge. `overall_gate` stays in the scorer output only for older machine consumers and follows the adjusted band.

## Helpers and input

Run `python3 scripts/structure_scan.py <repo> --output structure.json` first, then `python3 scripts/score_audit.py audit-data.json --output scores.json`. Python stdlib is enough.

Audit data retains `modules`, `consumers`, `consumer_graph_complete`, provenance, `module_weights`, `structure` (scan output), `systemic` (`candidates` from the scan, `resolutions`) and `principles`, including `{"id":"S","title":"Systemic structure","findings":[…]}`. Optional `excluded_modules` and `decisions` default empty. Findings require `id`, `severity`, `severity_reason`, `rootCostModuleIDs`, `reach_modules`, `external_scopes`, `evidence`; S findings add `archetype` and `candidate_ids`. Ledger rows require status/basis. Legacy `hard_gates` stay check observations. `scoring_scope: external-only` and per-family `enforcement_cases` keep P7's separate denominator. Audits without `systemic` still score but report `systemic.screened: false`; never deliver one as a complete audit.

The scorer rejects duplicate IDs, unknown modules, self edges, conflicting cross-tags, incomplete `module_weights`, systemic findings below their floor without a reason, dismissals without evidence, and custom thresholds.

Prepare the populated HTML with `python3 scripts/prepare_report.py audit-data.json report.html`. It validates data/anchors, embeds canonical input and the shared browser scoring/navigation assets, prints a `file://` URL and requests the default **external** browser. Use `--no-open` for automated verification. Exported decisions can be applied with `score_audit.py audit-data.json --decisions audit-decisions.json --output scores.json`. Browser and Python arithmetic must pass parity tests after changes.
