# P4 — Connect features through entry points

Core issue: a caller knows another feature’s internal construction or flow recipe, so initiating that capability spreads destination-owned decisions across callers.

Trace an actual cross-feature invocation: who initiates it, what domain input/outcome is exchanged, who builds the destination and who owns the work after handoff. Inspect screen navigation as well as deep links, app intents, notifications, share/widget extensions, background tasks and headless capabilities where present. These are example invocation surfaces, not a required list or an instruction to create separate modules for each one.

The caller owns its intent and integration/presentation context; the destination owns its private assembly and internal continuation. Follow factories, routes, closures and exported operations, rather than searching only for types named EntryPoint or Coordinator. Check handoff inputs, callbacks, cancellation and retained per-invocation state when they reveal construction/flow ownership.

Example:

```swift
// Caller chooses the destination and context.
documentDetailEntryPoint.open(documentID: documentID, in: navigationController)

// A problematic cross-feature recipe in the caller:
let interactor = DocumentDetailInteractor(repository: repository)
let model = DocumentDetailViewModel(interactor: interactor)
router.push(DocumentDetailView(viewModel: model))
```

Finding threshold: establish distinct feature/capability ownership, show caller dependence on destination assembly/internal flow, and explain an actual change scenario or inconsistent-construction consequence. Also check whether destination code improperly takes over caller-owned navigation/integration policy. Names and a long argument list alone establish neither defect nor correctness.

Correct the actual handoff boundary: a destination-owned factory, operation, route handler or other focused entry point can suffice. Show the simplified caller and destination construction, preserving inputs, outcomes, lifetime, cancellation and presentation ownership. Do not require coordinators, a public view type, one entry point per screen, or `attach(...).start()`.

Domain IDs, relevant configuration, callbacks and presentation context are legitimate inputs. Returning a view/controller for the caller to present is valid. An application root selecting implementations, reusable component composition and a feature’s own internal screen/worker assembly are not cross-feature violations. The screen example above illustrates the ownership rule; apply it to the repository’s actual invocation model.
