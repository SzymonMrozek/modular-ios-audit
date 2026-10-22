# Concrete correction examples

These are illustrative shapes, not repository findings or mandatory frameworks. Adapt each finding's before/after to verified symbols, source layout, lifetimes and behavior. Identify proposed APIs, supporting caller/manifest changes and uncompiled context. In the final report, split these illustrative flat sketches into module/scope → file/type → code groups for every problem, including same-file edits; keep the core fix code visible. Do not apply these changes during an audit.

## P1: parallel capabilities become separate importable modules

Before, two independent consumers import the same aggregate:

```swift
// ReportScreen and UploadFlow both import CommonKit.
.target(name: "CommonKit") // values + formatting + upload + retry
.target(name: "ReportScreen", dependencies: ["CommonKit"])
.target(name: "UploadFlow", dependencies: ["CommonKit"])
```

After, show the complete capability map, not just the first extraction:

```swift
.target(name: "CoreValues")
.target(name: "MeasurementFormatting", dependencies: ["CoreValues"])
.target(name: "AttachmentUpload", dependencies: ["CoreValues"])
.target(name: "RetryPolicy")
.target(name: "ReportScreen", dependencies: ["MeasurementFormatting"])
.target(name: "UploadFlow", dependencies: ["AttachmentUpload"])

// ReportScreen
import MeasurementFormatting // no upload or retry dependency
```

Keep upload-private views, models, assets and tests with AttachmentUpload. CoreValues must not re-export/depend on the components merely to keep old umbrella imports convenient. Actual XcodeGen/Tuist/SPM syntax follows the repository. An upload-only edit no longer changes ReportScreen's module dependency node; exact rebuild/test behavior still depends on tooling.

## P2: model the missing meaning or ownership rule

Prefer a type/model/operation change over adding instructions to a weak contract. A state model can eliminate ambiguous sentinel values:

```swift
// Current: [] has several hidden meanings.
protocol Documents { var documents: [Document] { get } }

// Proposed: include only states established by source tracing.
enum DocumentAvailability {
    case notLoaded
    case loading
    case available([Document])
}
protocol Documents { var availability: DocumentAvailability { get } }
```

An explicit value type can encode a unit at construction and conversion, rather than requiring every caller to inspect a formatter:

```swift
struct Percentage {
    let points: Decimal
    private init(points: Decimal) { self.points = points }
    static func percentPoints(_ value: Decimal) -> Self { Self(points: value) }
    static func fraction(_ value: Decimal) -> Self { Self(points: value * 100) }
}
// Boundary and caller: values retain their exact current meaning.
func configure(tolerance: Percentage)
configure(tolerance: .percentPoints(1))
```

When consumers must register a change stream before awaiting a snapshot, move registration into a synchronous owner operation returning a typed subscription. A sample operation on that already-registered subscription cannot accidentally register after its await. Keep changes-only consumption available. Preserve independent subscribers, buffering, cancellation, observation lifetime and caller-specific initial-state policy. A snapshot-plus-buffered-changes pair does not establish atomic current-and-future ordering; do not promise that without implementing and testing it. Show owner implementation, typed contract and changed caller, not just an interface sketch.

A unit-bearing name can be the complete repair for a simple established contract. When competing interpretations require construction/conversion rules, use a domain value; comments then explain residual guarantees. Do not add a wrapper indiscriminately or change scheduling, storage or runtime behavior merely to fit this example. When a smaller existing type/operation expresses the necessary meaning, reuse it.

## P8: honor the context at the owning assembly

```swift
// Before: the accepted scope controls only part of the graph.
func makeEditor(context: EditorContext = .default) -> Editor {
    Editor(
        loader: Loader(client: context.client),
        tracker: Tracker(sink: Global.container.analytics)
    )
}

// Proposed: choose the default once; use selected collaborators here.
func makeEditor(context: EditorContext = .default) -> Editor {
    Editor(
        loader: Loader(client: context.client),
        tracker: Tracker(sink: context.analytics)
    )
}
```

For a deeper child, let the existing owning assembly capture the selected collaborator in a child factory or provide its narrow dependency directly. Do not add an analytics parameter to unrelated app/navigation ancestors. Check reference identity/scope, callbacks, cancellation and retention. Intentional process-wide services outside the advertised override contract can remain global.

## P8: inject the focused subject's actual collaborators

Assume source tracing establishes that ResultModel uses only ResultsClient. A test helper that fills an entire FeatureDependencies bag still constructs unrelated objects. Change the production consumption boundary first:

```swift
// Before: ResultModel looks up the module-global client.
FeatureDependencies.container = FeatureDependencies(
    client: failingClient, clock: ClockMock(), tracker: TrackerMock()
)
let sut = ResultModel()

// Proposed members inside ResultModel:
private let client: ResultsClient
init(client: ResultsClient) {
    self.client = client
}
// Its operations use this stored client, without module-global lookup.

// Focused test: only the SUT's actual collaborator.
let sut = ResultModel(client: failingClient)

// Production: the owning assembly selects the implementation once.
let model = ResultModel(client: selectedContext.client)
```

Reuse an existing narrow initializer where available. Otherwise show the new initializer or narrow factory, its production assembly call and the test; ensure exercised descendants/default arguments do not silently fall back to the global bag. Preserve lazy work, cancellation, instance identity and per-test freshness. No DI framework or protocol per property is required.

Full-module test defaults are a migration aid or legitimate integration-test composition, not the main fix for a focused subject requiring unrelated collaborators. A SUT may meaningfully use several collaborators; supply those directly or through a focused dependency type. Keep helpers limited to that real construction surface. For repeated equivalent feature-entry recipes, use an owner-owned convenience operation while retaining configurable construction for legitimate differences.

## Other correction shapes

Use the code that expresses the actual repair: a domain operation replacing mutable backing access (P3), destination-owned construction (P4), removed redundant indirection (P5), policy moved from composition to its owner (P6), or an explicit manifest edge/removal of dead public plumbing (P7). Include the changed consumer, not only a new protocol that nobody uses. Explain behavior/concurrency invariants and what remains unverified. A generic example from this reference cannot substitute for repository-specific evidence.

These are examples of corrections, not definitions of the principles or a complete validation checklist. A finding may require a different repair—for example, a non-UI feature handoff, explicit error meaning, deterministic implementation selection, a cycle check or an owner-managed lifecycle operation. Choose from the established cause and preserve useful existing boundaries.

For a responsibility move, show the concrete source/destination file paths and focused diff hunks. A placement sketch can support the diff:

```text
CURRENT                               PROPOSED
App / Registration.swift              App / Registration.swift
  construct collaborators               construct + retain + start lifecycle
  decide whether to end a session ───► SessionImplementation / Lifecycle.swift
                                        existing session-ending decision
```

Nest the relevant code inside its module/file container in HTML. Keep the caller and destination visible together; identify any new behavior separately from the moved logic. For example, an owner operation that now recomputes validity is a behavioral repair as well as a relocation. Do not imply that moving an unchanged direct setter fixes its missing recomputation.
