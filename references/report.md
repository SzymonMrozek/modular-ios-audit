# Visual report

Use [report-template.html](../assets/report-template.html). Produce one self-contained local HTML file outside the source checkout. Honor the user's requested format. Keep every supported issue and its evidence; cut presentation chatter.

## Default reading surface

- Header: title, audited ref/date, module/issue counts, compact verification flags.
- Scoreboard: headline **Risk N% · X/N modules involved** with the LOW / MEDIUM / HIGH chip (<3%, 3–<10%, ≥10%; "Risk withheld · reason" when unknown). Under it: defect modules, risk before review choices, modules in scope, weakest classification coverage and structural candidates resolved; then one labelled "Structure scan:" line of facts; then a titled **Top problems by risk** list, each row with principle, severity, defect modules, involved modules and risk; then the principle table (**Defect modules**, **Involved**, risk and band, local status) and a one-line formula key. Every number must be recomputable from the module counts shown. Counts are descriptive unique sets; do not sum overlapping consumers. Do not display an overall gate or aggregate PASS/WATCH/FAIL badge. Follow [scoring.md](scoring.md). P7 tooling uses evaluated enforcement families, not a zero-module percentage.
- Structural findings live in their owning principle (P1, P5, P7). Each names its archetype and triggering scan metric and shows the structure that causes it (folder reference matrix, hub dependency fan, cycle, competing-mechanism table). Dismissed candidates and their reasons sit in that principle's Evidence.
- Principle: short name, separate root-cost/affected metrics and all supported issues as readable, closed native disclosures. No repeated methodology paragraph or duplicate introduction.
- Issue summary: full short title, root-cost/affected counts and impact/severity facts. Expanded body: module lists, the three sections below, then one closed **Evidence** disclosure.
- Elsewhere: diagrams, tables, labels, chips, paths and code. No explanatory paragraphs, verbose legends, caveat footers or motivational copy. Put complete audit reasoning, checks and limitations in Evidence or linked companions.

Visible commentary belongs only in these three sections. Use one blunt sentence, roughly 10–25 words, for each; clarity wins over an exact quota. Never remove a finding, verified occurrence or material qualification to hit a word count.

### Describe the problem

Name the current defect. Show only the **current architecture**: real owners, dependencies, calls, state or capability usage. Do not leak proposed types, future target columns or repair mappings into this section.

Prefer capability/consumer tables with **● used**, **— not used**, **? unverified** when those show the mechanism. Give symbols accessible labels; only mark usage/nonusage established by the source trace. A dot matrix is useful evidence, not decoration.

### Why it’s a problem

One concrete consequence: which change or operation makes another owner participate, or which invariant can be bypassed. Avoid repeating the problem or narrating the diagram. Keep potential effects distinct from observed failures; a short factual badge can carry that distinction.

### How to fix it

Order the content:

1. **Proposed architecture diagram first.** Keep it entirely in this section.
2. One blunt correction sentence.
3. Syntax-highlighted git-style code diffs, grouped by module → file.

Use precise names for simple meaning; prefer typed domain values, state models, narrow capabilities and owner-controlled operations when they enforce a demonstrated distinction. Do not force wrappers for cosmetic improvements. Match the diagram, code and ownership. Preserve existing correct behavior; mark proposed/uncompiled code as a compact fact. See [fix-examples.md](fix-examples.md).

Choose the right visual: dependency/capability topology, call-sequence lanes, read/write authority, protocol inheritance, or enforcement input/result matrix. Use actual symbols and relationships. Keep node labels short; put full signatures in diffs. Stack comparison lanes on narrow screens or scroll wide diagrams deliberately instead of breaking identifiers mid-word. Omit a visual when it adds no information. No forced box/arrow chains, generic MOVES/STAYS rows or paragraph notes inside diagrams. Show concrete source/destination files for relocations.

## Delivery and review controls

Prepare the populated HTML with `python3 scripts/prepare_report.py audit-data.json report.html`; this embeds validated canonical data, static scores and [report-scoring.js](../assets/report-scoring.js), followed by navigation. The template is illustrative: replace its example findings and include every selected principle/finding ID before preparation. Do not leave sample audit data in a real report. Use `--no-open` during tests.

The helper prints an absolute `file://` URL and requests the OS default **external browser**. Verify the file exists/is readable and that local anchors/assets work. Give the user that URL as a clickable link, not only a filesystem path or an agent-only preview. A local loopback URL is also suitable when the environment serves artifacts reliably; bind locally, expose only report assets and state the server lifetime. Never substitute a public upload. If launching a browser is unavailable/blocked, give the verified URL and state that limit without claiming it opened.

Each issue has one compact checkbox row: **Resolved**, **Invalid for this repo**, **Acceptable for this project**. They are mutually exclusive, with no reason field or per-issue form/Apply. Selecting recalculates immediately; unchecking reopens. Put one optional **Recalculate** button in the score header. Keep module scope and export/import/reset in a closed **Scope & saved choices** disclosure. Preserve original evidence/observed risk and user annotations. See scoring.md for persistence and audit binding.

A low or medium issue whose observed impact is **<2%** becomes a compact **Tiny issue** row; exactly 2% stays full, and high/critical issues are never tiny. Suggestions remain unscored. Group both under one closed **Suggestions & tiny issues** disclosure per principle, after full issues. Expand a row for its full source/fix/evidence; deep links must open both group and issue. Unknown risk stays full. A reviewed large issue does not become tiny merely because its adjusted risk is zero. Preserve all findings and syntax-highlighted diffs in the DOM.

Show the overall average percentage and LOW / MEDIUM / HIGH risk-band label, without an overall gate or aggregate verdict. Individual principle/check statuses remain local. Coverage/unknown checks stay visible separately. Browser-only choices are local until exported and consumed by an agent.

Embed both JS assets; no CDN, fetch or external dependencies. Without JavaScript the static scores, all findings and native disclosures remain readable; interactive recalculation requires JS. Keep controls compact, keyboard accessible, with status/error feedback.

## Website navigation

Use the template’s [report-navigation.js](../assets/report-navigation.js), embedded in the final HTML; no runtime fetch or network dependency.

- Default: score overview. Select Pn: show only that principle, with every issue summary closed and readable on one page.
- Sidebar: principle links and full issue titles for the active principle. Use a full-width issue selector on mobile; no dense pills.
- Stable IDs: `#p1`, `#p1-f1`, `#p1-f1-fix`, `#p1-f1-evidence`. A deep link reveals its principle, opens the issue and any ancestor disclosure, then scrolls to the target.
- Native `<details class="issue" id="…">` / `<summary class="issue-summary">` support pointer and keyboard toggling. Expanding updates the shareable hash. Browser Back/Forward restores the selected principle/issue.
- Keep a Scores breadcrumb, active-link `aria-current`, visible focus and reduced-motion support. Without JavaScript, every principle list and native disclosure remains usable.
- Keep full fixes/evidence in the HTML even when closed. Collapsing is presentation, never an excuse to omit supporting occurrences.

The template uses `.principle[id]`, `details.issue[id]`, `[data-overview]`, `.page-navigation`, `[data-current-principle]`, `[data-issue-jump]`, `[data-principle-link]`, `[data-issue-link]`, `[data-scores-link]` and `.nav-issues` within `[data-principle="p1"]` groups. Preserve those hooks when adapting it.

## Highlighted source diffs

Use [code_diff.py](../scripts/code_diff.py) with Python containing **Pygments**. Prefer an installed copy; otherwise use an isolated temporary virtual environment. This is report tooling, not an app dependency. Example setup when needed:

```sh
python3 -m venv /tmp/modular-audit-render
/tmp/modular-audit-render/bin/python -m pip install Pygments
/tmp/modular-audit-render/bin/python scripts/code_diff.py diff-input.json --output diff.html
```

Input: `{"files":[{"owner":"Module","path":"Sources/File.swift","language":"swift","before":"…","after":"…"}]}`. Language is optional when the path identifies it. A `note` supplies hover context; keep long explanations out of the diff body.

Highlight whole before/after snippets **before** selecting diff hunks, preserving multiline comment/string state. Render red removals, green additions, stronger replacement emphasis and syntax colors together. Keep original whitespace, line numbers, +/- markers and hunk headers. No automatic source reformatting that changes the inspected/proposed code. Escape source and attributes; verify the displayed text equals the input.

Support Swift, Objective-C/Objective-C++, C/C++, Python, shell, Ruby/Fastlane, JSON, YAML, XML/plist/storyboards, TOML, JavaScript/TypeScript, SQL and protobuf. Metal can explicitly use C++ grammar; unknown languages remain labelled plain text. Do not guess a language silently. Embed token markup and the template's syntax CSS: no CDN, runtime highlighter or network requirement in the delivered HTML.

Preserve exact file ownership, changed callers, manifests and relevant test adaptations. Use small hunks; longer mechanical migrations can be closed. Never present a missing current excerpt as proof that an entire existing file is new/deleted. State excerpt-relative numbering once in compact metadata. Full correction code and its uncompiled limits remain available in Evidence.

## Evidence and checks

One closed Evidence disclosure per issue can retain complete evaluator reasoning, source/caller occurrences, code references, counterexamples and actual checks. Clear principles use a compact positive fact with their traced evidence closed. Unknown, not-applicable and user-skipped remain distinct; no verdict for skipped scope. Never turn unassessed modules into passes.

Keep verified source paths, audited ref and one-based lines. Embed captured excerpts; use an archived audited source when the live path no longer exists. Preserve Markdown source companions when useful. The originating article is not proof of a repository defect.

Before delivery:

- Validate Python/browser parity for consequence weights, module-share risk with one count per involved module, implementation-only exposure, structural withholding and ranking, exclusions, resolved/invalid/acceptable/reopen/reset, legacy-choice migration, persisted/exported choices, unknown coverage and an overall risk with a matching LOW/MEDIUM/HIGH band and no aggregate gate badge. Validate <2% vs exactly 2% compact presentation and nested group deep links. Validate 3%/10% boundaries and P7 family denominators. Zero affected means no observed propagation impact; it does not clear an issue or incomplete coverage.
- Check no proposed node/API/mapping appears in a current diagram. Fix sections must start with their proposed visual, before code.
- Verify syntax tokenization and source text for supported languages, multiline strings/comments, escaping and replacement marks.
- Render desktop (~1440px) and mobile (~390px). Check dot/dash matrices, diff scroll, navigation, keyboard disclosures, closed evidence and no page overflow.
- Verify overview → principle → issue, initial deep links, nested anchors, Back/Forward, mobile selector, keyboard toggling and reduced motion. All issue summaries must be reachable; expanding must expose all core fixes. Preserve source snapshots and material limits; compilation or runtime validation is never implied by HTML rendering.

The chat handoff should be short and link the report. Audit depth belongs in the evidence; the reading surface should look like a developer's review, not an essay.
