# Consequence, reach and principle-average scoring

Read before mapping modules or dispatching evaluators. A report answers three separate questions: where defects live, how far their dependencies reach, and how consequential the supported problems are. Scores are project policy, not industry benchmarks or a probability of failure.

## Scope and inventory

Freeze the first-party logical-module inventory at the audited ref. Collapse Interface/Implementation/Proto/resources/tests under the owning manifest; exclude generated/vendor ownership and empty placeholders. Record app/extension/tooling outside that inventory separately.

Accept explicit user module exclusions as `excluded_modules: [{"module":"Modules/…","reason":"…"}]`. Resolve names to unique inventory IDs before evaluation; ask only for ambiguous matches. Do not infer exclusions from a module's name or purpose. Preserve the full inventory, excluded IDs/reasons and eligible count in every report/export. Excluded modules are outside audit classification, owner counts, consumer reach and the denominator; exclude edges into/from them, without splicing transitive paths. Keep excluded findings visible as out of scope when narrowing an existing report. Broader changes require a new source audit. Compare scores only with the same scope; a denominator change is not an improvement.

Use a frozen direct source-import consumer graph. Deduplicate logical consumers across files/targets; exclude self edges and external app targets. Include real production/test imports with their provenance and disclosed scope. Declared unused/phantom dependencies and transitive consumers create no direct edge. Publish the full graph, including known leaves. A graph based on regex imports can miss syntax or overinclude inactive configurations; label it snapshot import exposure, not resolved build-graph truth. Unknown mappings are not empty sets. `consumer_graph_complete: true` requires scanning all eligible roots in the stated scope; missing eligible keys or missing authority makes reach/risk N/A. Record authority as a nonempty `source` or `authority` string in `consumer_graph_provenance`.

## Qualify a finding before scoring it

- `kind: issue`: a verified owner defect with a concrete consumer/change consequence and evidence. Severity follows consequence, not primitive types, public declarations, missing wrappers/comments or graph fan-out.
- `kind: suggestion`: a possible clarity/polish improvement without that consequence. Keep it available in Evidence or a compact suggestion row; it contributes zero risk and cannot fail a gate. Do not label its module `issue` solely for the suggestion.
- Insufficient inspection is `unassessed`/uncertain, not clear and not a verified issue.

For P2 inspect recoverability of meaning, competing interpretations and actual caller work. A clear unit-bearing name or established contract may be enough. For P3 distinguish meaningful domain values/read-only access from leaked representation or owner invariants. A unit ambiguity belongs to P2; do not duplicate it under P3 without a separate exposed decision. See the individual rubrics. Types/owner operations are preferred when they enforce a real distinction; a proportionate name change is valid when it completely resolves the problem.

## Root cost and affected modules

`rootCostModuleIDs` are evidenced defect owners, not files to edit or consumers exposed to a bad contract. `affectedModuleIDs = union(consumers[root] for every root)`, filtered to eligible scope. Roots count once; affected consumers count once. Do not automatically add roots or expand transitively. A root can be affected by another root. Keep semantic consumer traces (`reach_modules`) separate from import exposure.

Keep both identity lists/counts for findings and principles. Repository unions are descriptive scope facts only; **they do not produce the overall architecture score**. Neither many imports nor a single public property establishes a severe issue.

## Consequence-weighted risk

Policy: `overall-risk-and-simple-review-v5`. Preserve raw affected/N reach alongside risk.

| Severity | Weight | Evidence needed |
|---|---:|---|
| low | 0.10 | Local maintenance/clarity cost with a traced consequence; no broken invariant |
| medium | 0.40 | Repeated cross-boundary knowledge, conversion or representation coupling |
| high | 1.00 | Reachable consequential authority/invariant bypass or broad mandatory owner coordination |
| critical | 1.00 | Demonstrated serious impact, such as unauthorized state change/data loss |

A merely possible type/name improvement is a suggestion with weight 0. A shared library's popularity changes reach; it does not upgrade severity.

For each affected module, take the **maximum severity weight** of open issues whose root it directly consumes. Then:

`principleRisk = sum(maxWeightPerAffectedModule) / eligibleModuleCount`

A module exposed to several findings counts once at the strongest supported consequence. An individual finding uses its own weight × distinct affected/N. A leaf can have zero propagation risk while still owning a defect. Keep consequence and check results as evidence; they do not override the overall numeric gate. Do not call zero risk an absence of issues.

Use exact fractions for bands: LOW <3%, MEDIUM ≥3% and <10%, HIGH ≥10%. Show the consequence weight, raw roots/affected and weighted risk in compact facts; put arithmetic details in policy/Evidence. Do not show sums of per-root consumer counts. A high raw footprint alone no longer creates a Fail.

**Overall risk is the equal arithmetic mean of the selected, applicable module-principle risks**, including assessed zero-risk principles. Display the included IDs and partial coverage. Skipped, external-only and not-applicable principles do not enter that mean. An unknown applicable risk makes the mean N/A; never silently average only known values. P7 external enforcement uses failed/passed/unknown rule-family counts, never fake module percentages. If P7 has real module findings it participates normally. Cross-tagged findings must be identical; within a principle they are deduplicated. The same defect may affect multiple principle assessments; disclose cross-tags without manufacturing distinct issues.

## Compact findings and review choices

A verified issue with **observed risk strictly below 2%** is a **tiny issue** in presentation; an unverified/polish suggestion remains unscored. Exactly 2% stays a full issue. Use observed risk under the current scope so resolving a large issue does not relabel it tiny merely because adjusted risk becomes zero. Unknown risk is not tiny. Presentation never silently changes the original kind, consequence, score or evidence.

Show full issues first. Put tiny issues and suggestions in one closed **Suggestions & tiny issues** group per principle, using short rows with a title and risk. Keep the complete problem, fix, code and Evidence behind each row's disclosure; deep links open both levels. A numeric tiny issue still contributes its small risk until explicitly handled.

Keep source findings/ledger immutable. Apply a separate `decisions` map keyed by stable finding ID:

```json
{"p2-f1":{"status":"resolved","decided_by":"user"}}
```

Statuses: `open`, `resolved`, `invalid` (**Invalid for this repo**), `accepted` (**Acceptable for this project**). Show three compact, mutually exclusive checkboxes; selecting one replaces any earlier choice and recalculates immediately. Uncheck it to reopen. **No reason, text field, confirmation or per-issue Apply step.** Provide one optional **Recalculate** button in the score header. These are user review annotations, not agent-verified code repairs. Only explicit user input may assign a non-open status; retain unknown IDs/attribution checks without asking for prose.

Resolved/invalid/accepted findings remain visible with source evidence and status, but leave adjusted risk and open root/affected sets. Observed risk retains the original evidence under the same scope. Recompute all levels; another open finding at the same root keeps its contribution. The original ledger does not become clear because of a checkbox. Legacy `intended` choices migrate to `accepted`; existing accepted choices and optional old reasons remain usable.

Persist choices locally when possible; keep Export/Import/Reset and module scope in one closed **Scope & saved choices** disclosure. Do not repeat save instructions beside every issue. Exports retain exact audit-input fingerprint, choices and exclusions; reject a mismatched audit or unknown finding/module IDs. Browser storage alone does not update source JSON: agents consume exported choices for durable follow-up. After code/ref/evidence changes, revalidate annotations. If storage is unavailable, the session still works and export remains available.

## Coverage and gates

Each selected principle keeps a module ledger: `issue`, `clear`, `not-applicable`, `unassessed`, with a basis. Missing = unassessed. Only relevant inspection establishes clear/not-applicable. Ledger issue owners equal the union of evidenced `kind: issue` roots before decisions; suggestions do not create defect owners. Excluded modules are omitted from classification totals. Coverage = (issue + clear) / (eligible − not-applicable); acceptance does not manufacture coverage. Scores remain observed lower bounds with unassessed code.

**Report the individual principle risks and overall average risk, without an overall gate or aggregate verdict.** Show the overall LOW / MEDIUM / HIGH risk-band chip beside the percentage, using the same exact <3%, 3–<10%, ≥10% thresholds as the individual scores; use N/A when unknown. Do not display an overall GATE/PASS/WATCH/FAIL badge. The headline is **Average risk**, using the adjusted mean; the observed baseline and coverage remain small facts. Local principle/check statuses do not become a report-wide judgement.

The scorer retains `overall_gate` only for compatibility with older machine consumers. Do not render it or use it to narrate an overall pass/fail. Its legacy numeric mapping follows the adjusted average (<3% pass, 3–<10% watch, ≥10% fail; unknown incomplete) and does not inherit local failures. The user-facing output is the average itself.

Per-principle numeric HIGH can still be a local Fail; unknown applicable classification/check results remain locally Incomplete. External-only P7 retains N/A module risk and evaluated rule-family counts. Missing classification/check results remain in coverage/verification metadata. No applicable scope is Not applicable; all-skipped gets no numeric average. Check results and source evidence remain available without an aggregate verdict.

## Helpers and input

Run `python3 scripts/score_audit.py audit-data.json --output scores.json`. Python stdlib is enough. Input retains `modules`, `consumers`, `consumer_graph_complete`, graph provenance and `principles`. Optional top-level `excluded_modules` and `decisions` default empty. Findings require `id`, `severity`, `severity_reason`, `rootCostModuleIDs`, `reach_modules`, `external_scopes`, `evidence`; `kind` defaults to `issue` for older data. Ledger rows require status/basis. Legacy `hard_gates` records require id/reason/evidence; retain them as check observations without an overall gate override. `scoring_scope: external-only` and per-family `enforcement_cases` retain P7's separate denominator. Preserve `check_unknowns`.

Outputs retain raw `impact` exposure, root/affected IDs/counts, `risk`, `observed_risk`, review choices, `presentation` (issue/tiny/suggestion), coverage and gates. Overall `risk` uses the mean; root unions are descriptive. Legacy `observed_modules` can supply roots when canonical IDs are absent; conflicting old/new fields are invalid. Reject duplicate IDs, unknown modules, self edges, conflicting cross-tags and unsupported custom thresholds.

Prepare the populated HTML with `python3 scripts/prepare_report.py audit-data.json report.html`. It validates data/anchors, embeds canonical input and the shared browser scoring/navigation assets, prints a `file://` URL and requests the default **external** browser. Use `--no-open` for automated verification or an explicit user preference. Exported decisions can be applied reproducibly with `score_audit.py audit-data.json --decisions audit-decisions.json --output scores.json`. Browser and Python arithmetic must pass parity tests after changes.
