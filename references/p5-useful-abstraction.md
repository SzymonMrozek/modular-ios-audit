# P5 — Introduce abstraction only when useful

Core issue: an abstraction’s cost is not justified by the decision, variation or invariant it protects, or the abstraction is at the wrong boundary and fails to provide its intended isolation. Evaluate usefulness rather than maximizing or minimizing protocols/modules.

P5 also owns **parallel abstractions**: two or more competing mechanisms for one concern (two networking stacks, Rx and Combine, several router/coordinator or DI systems) that callers must choose between. The structure scan flags them as P5 candidates ([structure-scan.md](structure-scan.md)); confirm or dismiss each. The correction picks one mechanism per concern, adapts the other behind it, and shows the migration boundary and the rule that blocks new use.

Inspect protocols, wrappers, factories, adapters, mappers, generic layers, type erasure and Interface/Implementation splits where present. Trace actual callers and the decisions protected, substitution/configuration requirements, ownership/lifetime, tests and change paths. Look for forwarding chains, duplicate models/conversions, leaked implementation requirements and abstractions consumers must repeatedly work around. These are non-exhaustive lenses, not style bans.

Ask both whether removing a layer would preserve required isolation and whether a demonstrated volatile decision is insufficiently isolated. Recommend an abstraction only for an evidenced benefit; do not invent future vendors, implementations or extensibility needs. A single implementation can still justify a boundary for policy ownership, deterministic tests, platform containment or lifecycle management.

Positive case: independent `EditorInterface` and `DocumentLibraryInterface` contracts let each feature implementation open the other without implementation-to-implementation dependencies. Separation protects actual decisions and consumer access.

Good standalone UI consumption:

```swift
import AvatarComponent
AvatarView(image: image, size: .small)
```

Questionable forced split:

```swift
// AvatarInterface
public protocol AvatarFactory {
    func makeAvatar(image: AvatarImage, size: AvatarSize) -> AnyView
}
// AvatarImplementation
public struct AvatarFactoryImpl: AvatarFactory {
    public func makeAvatar(image: AvatarImage, size: AvatarSize) -> AnyView {
        AnyView(AvatarView(image: image, size: size))
    }
}
```

If the factory only satisfies an “everything needs an interface” convention, it adds module/protocol/implementation/wiring/type erasure without a demonstrated need. Inspect actual substitution, platform, lifetime, and composition requirements before judging.

Finding threshold: demonstrate the abstraction’s consumption/change cost or failed isolation, explain what it actually protects, and show a simpler or better-placed boundary preserving real requirements. Do not flag `AnyView`, a single implementation, a public concrete type, or an interface's existence alone. Nor is absence of an interface module automatically a problem.

For SwiftUI cases, distinguish type erasure (`AnyView`) from opaque results (`some View`). Neither syntax alone proves a design defect; claim runtime/state/performance effects only with evidence relevant to the actual use. The avatar example illustrates unjustified indirection and is not the only abstraction form to evaluate.

Dependency-cycle enforcement belongs primarily to P7. Do not broaden P5 into a general graph audit.
