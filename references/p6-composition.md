# P6 — Keep composition explicit

Core issue: wiring is scattered, hidden, or contains business decisions, obscuring which implementations run and where behavior belongs.

Trace application entry -> owning assembly -> implementation selection/binding -> consumer resolution and relevant lifetime. Registration is one possible mechanism; constructor assembly, generated factories, environments and other inspectable wiring can serve the same role. An application composition root selects implementations, an owning module assembles its internals, and domain behavior remains with its feature/service.

Discover where choices happen, not only where a container is declared. Inspect initialization paths, lazy factories, overrides, runtime resolver calls and scope/lifetime ownership. Look for implicit/competing registrations, order-dependent selection, hidden defaults or service creation during behavior, duplicated private assembly and policy computed by wiring. Trace the selected instance and the actual caller consequence before reporting; several roots/files or dynamic selection alone are not defects.

Good: `AppComposition` calls `EditorImplementationModule.register()` and `ExportPolicyImplementationModule.register()`. Editor's registration supplies its internal collaborators. The export policy implementation owns document export rules.

Bad: `AppComposition` reads the current document, computes `isReady && permissions.contains(.export)`, and constructs `EditorViewModel(canExport: ...)` inside the editor registration factory. It owns Editor's private assembly and domain policy. Identify these decisions in actual source rather than assuming any conditional registration is business logic.

Finding threshold: show an actual selection/ownership/lifetime trace with hidden or conflicting wiring, another module’s misplaced assembly, or a specific business decision in composition, and explain the consequence. Inspect registration behavior; a container or register method proves little by itself.

“One root” means one discoverable composition path per application entry point. Apps, extensions, tests, and previews may have separate roots and multiple composition files.

Accept constructor injection, lazy resolution, generated inspectable wiring, environment-specific implementation selection, configuration passing, and factories constructing collaborators. Do not require a global container, specific DI library, or one physical file. Composition may select a policy implementation; it should not calculate that policy's domain outcomes.

Correct selection, assembly or lifetime at the appropriate owner and simplify the consuming path. Move an existing domain rule into its owner when that is the demonstrated issue; do not prescribe relocating code for every composition finding. Environment/build-mode selection is legitimate wiring, while calculating a document’s export eligibility is domain behavior. The example is illustrative rather than the only distinction to audit.
