# P2 — Make changes understandable locally

Core issue: changing a module requires reconstructing knowledge outside its responsibility because the consumed boundaries omit necessary meaning, rules or interaction requirements. Locality is about the knowledge needed, not the number of files opened.

## Discover hidden knowledge requirements

Trace concrete changes to presentation, domain behavior, data/state handling, platform integration or lifecycle. Start from the behavior being changed, then follow its contracts, tests/resources and relevant wiring. Ask what the developer must learn and why that knowledge is not available at an appropriate boundary. Consider, without limiting discovery to:

- Domain meanings, units, identity and error distinctions hidden in primitives or external implementation details.
- Operation sequencing, preconditions, idempotency, transaction/ownership rules or initialization order that callers reconstruct.
- State/event timing, cancellation, concurrency/isolation and resource lifetime requirements.
- Configuration, persistence or integration assumptions that unnecessarily determine a local change.

Example: `[Document]` secretly conflates not loaded, loading and a valid empty result. Editor must inspect document/cache implementations to choose its presentation. An exported `DocumentsState` with the established cases lets Editor decide locally. This illustrates missing meaning; it is not an array/optional lint rule or the only contract shape to inspect.

Finding threshold: demonstrate a concrete change, the missing knowledge, the external recovery path and the unnecessary consequence. An untraced suspicion stays uncertain. Knowing several well-defined contracts, validating consumers after a shared-contract change, debugging a faulty implementation or following meaningful cross-feature requirements is legitimate work.

## Prefer the smallest boundary correction

Distinguish unclear exported meaning from missing runtime behavior. Prefer a type/domain model, narrow capability or owner-controlled operation that removes the knowledge requirement: unit values make construction/conversion explicit; a subscription handle or operation can own registration-before-snapshot sequencing. A precise unit-bearing name can fully resolve a simple naming ambiguity; do not require a wrapper when a name or applicable documented convention establishes the contract. Prefer a type where it enforces competing units, validation or conversion rules, and owner operations for sequencing/invariants. Preserve the established interaction model, source values, scheduling and lifetime unless a demonstrated defect requires changing them. Show owner and caller changes and targeted checks; do not claim a typed wrapper establishes atomic delivery by itself.

When behavior is absent, repair its owner or reuse a suitable abstraction. Express demonstrated distinctions through domain cases or operations, and keep sequencing/invariants with their owner where appropriate. Do not force a state enum, protocol, wrapper or framework for every ambiguity. Use documentation to supplement residual constraints, or as a fallback when no proportionate safe interface/implementation correction addresses them; explain that limit. See [fix-examples.md](fix-examples.md) for illustrative domain-state and publisher corrections.

Preserve errors, atomicity, ordering, lifetime and concurrency. In stream cases, inspect initial delivery, later subscriptions and scheduling before promising replay; a separately sampled snapshot can leave a subscription gap, and a publisher does not itself guarantee asynchronous dispatch. Apply equivalent scrutiny to the actual interaction under review rather than restricting the audit to publishers.

Sweep all verified consumers of each established missing meaning. Keep intentionally coarser contracts, changes-only consumers and other justified alternatives as counterexamples. Documented conventions can resolve meaning when actually applicable; neither missing comments nor an undocumented declaration alone proves a defect.

P2 assesses knowledge required for a change; P3 assesses exposed decisions. Cross-tag a shared cause without counting it twice.

## Qualification and consequence

A public numeric property alone is not a finding. Inspect its name, surrounding domain model, unit conventions, construction and actual consumers before proposing a change. Distinguish four outcomes: meaning is already local (clear); a more precise name would be pleasant but no consequence is traced (unscored suggestion); an ambiguity makes a caller recover knowledge/duplicate conversion elsewhere (usually low or medium issue); competing interpretations cause reachable incorrect behavior (higher severity only with that evidence). Do not infer a runtime bug from a possible interpretation.

Score the supported consequence under scoring.md; broad imports do not turn a naming issue into a major architectural failure. Trace semantic users separately from raw import exposure. Naming, explicit unit types and owner-controlled conversion are alternative repair sizes; choose the smallest one that resolves the demonstrated ambiguity. User-confirmed intended contracts remain visible and can be excluded from adjusted risk through dispositions.
