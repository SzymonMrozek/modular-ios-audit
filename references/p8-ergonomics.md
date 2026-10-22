# P8 — Make boundaries ergonomic

Core issue: using or changing a module requires avoidable work or knowledge in consumers that do not own those decisions. Examples include repeated plumbing, manual adaptation/lifecycle ceremony and ignored configuration or dependency scope; no one DI style defines ergonomics.

Trace representative consumer tasks: construct/configure a feature or service, supply a collaborator, invoke work, handle its result/cancellation/lifetime and test it in isolation. Compare equivalent paths across modules to distinguish owner-required choices from incidental ceremony. Inspect signatures, builders/factories, adapters, value/error conversions, state/event handoffs, defaults, DI resolution and test setup where relevant. Do not limit discovery to an entry-point signature, repeated recipe or a particular container pattern.

## Recurring forms of friction

1. **Forward-only chains.** A leaf collaborator requires parameters/properties through unrelated ancestors. Show that intermediate layers only forward it; meaningful configuration or scope selection can justify a chain.
2. **Partially honored injection.** An entry point/factory accepts an explicit context, but descendants/default arguments choose a global container, singleton, environment or separate resolver for those same advertised collaborators. Trace both sources, operations and actual override/test callers. An intentional outer default differs from bypassing an explicitly supplied context.
3. **Broad dependency bags at narrow consumers.** Focused consumers/tests must construct unrelated collaborators because the boundary requires the whole bag. Show actual fields consumed and extra construction forced by a collaborator change; a long initializer alone proves nothing.
4. **Repeated equivalent construction.** Callers/modules repeat identical lifecycle/default recipes, adapters or conversions without owning a meaningful choice. Compare all reasonable matching callers; exclude different authorization, presentation or lifetime policies.
5. **Repeated test plumbing.** A module dependency change makes unrelated focused suites rebuild the same full container/mocks because subjects resolve globals or accept broad bags. Check whether narrow SUT injection exists or should be introduced. Test setup is boundary consumption evidence, not automatically "just test code."
6. **Consumer-side adaptation or lifecycle ceremony.** Equivalent callers rebuild the same representation/error conversion, callback/event bridge, subscription retention or cleanup recipe because the module does not offer a useful consumption boundary. Show the repeated steps and the owner that can absorb them; caller-specific presentation, retry or cancellation policy may justify differences.

These are search lenses, not a required finding list. Report other patterns meeting the same threshold; do not match only names/symptoms from a previous repository. Group recurring occurrences under their actual root cause while preserving each module/caller example.

## Correction and code evidence

Contrast the actual path with the smallest equivalent assembly:

```text
Forwarding: app -> coordinator -> model -> leaf (only leaf uses service)
Local:      app selects implementation -> owning assembly supplies leaf

Mixed scope: supplied context A -> owning factory -> hidden global B
Consistent:  supplied context A -> owning factory -> its scoped children

Test friction: focused suite -> full module bag -> hidden global lookup
Local:         focused suite -> SUT(actual collaborators only)
Production:    owning assembly -> selects and supplies collaborators
```

Show before/after Swift for the relevant consumption path, not just "use DI," "add a helper" or "add a container." Choose the repair from the demonstrated burden: a focused domain operation, owner-local adapter/lifecycle handle, smaller input/result type, meaningful defaults or narrow injection can each be appropriate. Do not prescribe a DI rewrite for a non-DI problem. Prefer capturing/resolving the contract at the owning assembly, honoring the accepted context, or a focused factory/operation. For focused-test friction, prioritize required injection of the collaborators actually used by the SUT (or an equally narrow capability/factory), adding that boundary when absent. Show the changed production consumer, its owning assembly and the simplified test. Trace nested/default construction too: a narrow initializer does not help if exercised descendants still resolve a full global container. Do not fix a hidden global by forwarding every service through every navigation ancestor. Retain configurable APIs for meaningful caller choices. See [fix-examples.md](fix-examples.md).

A helper that constructs the whole module bag hides repetition but still initializes unrelated dependencies and preserves the global/broad boundary. Treat it as a migration aid, or as legitimate setup for tests intentionally exercising the full assembled graph, rather than the primary architectural fix for focused tests. Reuse existing narrow injection and remove unnecessary global setup when possible. A subject may legitimately use several collaborators; the goal is to avoid unrelated construction, not to force one argument or one mock per test. Test helpers can provide fresh defaults for the subject's actual collaborators without recreating an entire module.

Preserve instance/scope identity, per-operation cancellation, weak delegates, retention, initialization order, per-test freshness/reset and actor/scheduler constraints as applicable. No DI framework, property wrapper, global locator or constructor style is required. Module-owned constructor assembly or narrow `Has...` compositions can already be ergonomic.

Finding threshold: demonstrate actual unrelated forwarding, repeated construction, avoidable adaptation/lifecycle ceremony, ignored advertised scope or change amplification, with a simpler equivalent preserving behavior. Do not count fields/containers as defects. Deliberate app-global system services and meaningful caller-owned configuration are counterexamples. Do not call an entire DI pattern bad because one path is faulty; equally, do not accept recurring friction merely because each initializer is typed.

P4/P6 assess who owns assembly/selection; P8 assesses consumption work. Cross-tag an ignored-scope/hidden-selection cause where appropriate and count it once.
