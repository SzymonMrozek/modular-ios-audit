# P3 — Expose small contracts and hide decisions

Core issue: consumers depend on decisions or mutable invariants that should belong to another module, spreading implementation changes or allowing callers to bypass the owner’s rules.

Inspect public and effectively reachable boundaries: exported types/operations, access control, mutable references, generic constraints, callbacks/events and actual callers. Trace which decisions are intended to vary behind the owner and which are meaningful parts of the public contract. A small contract requires little implementation knowledge; few declarations alone do not make it small.

Discovery lenses include vendor/transport representations, storage/query models, internal view/navigation objects, mutable state graphs, scheduling/resource mechanisms and leaked algorithms or policy steps. These are not a closed defect list. Ask whether a plausible change of an owned decision forces consumers to change, or whether a consumer can violate an owner-maintained invariant. Trace consequences beyond the mere presence of a concrete type.

Good:

```swift
public protocol SearchHistoryRepository {
    /// Saved entries, newest first; empty when none exist.
    func recentEntries() throws -> [SearchHistoryEntry]
    func save(_ entry: SearchHistoryEntry) throws
}
```

Bad:

```swift
public protocol SearchHistoryRepository {
    var context: NSManagedObjectContext { get }
    func fetch(_ request: NSFetchRequest<SearchHistoryEntity>)
        throws -> [SearchHistoryEntity]
}
```

The latter exposes query construction and managed-entity lifecycle to consumers. Validate actual caller coupling before reporting.

Finding threshold: identify the leaked decision/invariant, actual consumer dependence or mutation, and a plausible owner change or bypass consequence. Missing behavioral or concurrency documentation is a finding only when a meaningful ambiguity has a consumer consequence. Do not require comments on every declaration.

Platform types, concrete APIs in standalone modules, public SwiftUI components, several clear operations and absent wrappers are not defects by themselves. Establish the leaked decision/invariant and its consequence rather than exempting or condemning a boundary by its syntax or module kind. A single generic `execute` operation can expose more complexity than several domain operations.

Choose operations, values, access restrictions or capabilities that hide the demonstrated decision while preserving legitimate configuration and interaction. Show owner and caller changes together; a wrapper that merely renames the same representation may provide no isolation. The database example is illustrative, not a requirement to wrap every platform API.

## Qualification and consequence

A public domain value, primitive, read-only property or meaningful configuration is not an information-hiding failure merely because it lacks a wrapper. Ask what decision belongs to the owner, what guarantee it maintains, and how a caller depends on or bypasses it. Unit naming alone belongs to P2 unless a separate hidden representation/authority consequence is established.

Distinguish a cosmetic contract improvement (unscored suggestion), verified replaceable representation coupling (typically low/medium), reachable bypass of an actual owner invariant (high when consequential), and a demonstrated serious failure (critical). Public writability establishes possible access; inspect the real invariant, legitimate configuration paths and reachability before assigning bypass severity. No observed production misuse must remain an explicit qualification. Avoid cross-tagging one unit ambiguity as two defects. Apply consequence weights, user dispositions and separate hard gates from scoring.md.
