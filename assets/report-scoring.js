/* No dependencies. Python scorer is authoritative; parity fixtures verify this browser projection. */
(() => {
  const units = {low: 1, medium: 2, high: 8, critical: 14}, rank = {low: 0, medium: 1, high: 2, critical: 3};
  const EPS = 1e-12;
  const band = v => v === null ? null : v < 0.1 - EPS ? 'LOW' : v < 0.25 - EPS ? 'MEDIUM' : 'HIGH';
  const measure = v => ({score: v, percent: v === null ? null : v * 100, health: v === null ? null : Math.round((1 - v) * 100), band: band(v)});
  const normalize = d => ({...d, status: d.status === 'intended' ? 'accepted' : d.status});
  function compute(data) {
    const excluded = new Set((data.excluded_modules || []).map(e => e.module));
    const modules = data.modules.filter(m => !excluded.has(m));
    const eligible = new Set(modules), graph = data.consumers || {}, N = modules.length;
    const authority = ['source', 'authority'].some(k => typeof data.consumer_graph_provenance?.[k] === 'string' && data.consumer_graph_provenance[k].trim());
    const complete = data.consumer_graph_complete === true && authority && modules.every(m => Object.hasOwn(graph, m));
    const weight = Object.fromEntries(modules.map(m => [m, data.module_weights ? data.module_weights[m] : 1]));
    const mass = modules.reduce((a, m) => a + weight[m], 0);
    const roots = f => (f.evidencedRootCostModuleIDs || f.rootCostModuleIDs || f.observed_modules || []).filter(m => eligible.has(m));
    const exposure = (rs, implementationOnly = false) => implementationOnly ? [...new Set(rs)] : [...new Set([...rs, ...rs.flatMap(m => graph[m].filter(n => eligible.has(n)))])];
    const footprint = (fs, external = false, implementationOnly = false) => {
      const owners = [...new Set(fs.flatMap(roots))].sort();
      const spreading = implementationOnly ? [] : [...new Set(fs.filter(f => f.implementation_only !== true).flatMap(roots))];
      const available = !external && complete && N > 0;
      const affected = available ? [...new Set(spreading.flatMap(m => graph[m].filter(n => eligible.has(n))))].sort() : null;
      const exposed = available ? [...new Set([...owners, ...affected])] : null;
      return {rootCostModules: external ? null : owners.length, rootCostModuleIDs: owners, affectedModules: affected?.length ?? null, affectedModuleIDs: affected,
        impact: measure(exposed ? exposed.reduce((a, m) => a + weight[m], 0) / mass : null)};
    };
    const risk = pairs => {
      if (!complete || !N) return measure(null);
      const values = new Map();
      for (const [f, pid] of pairs) for (const m of exposure(roots(f), f.implementation_only === true)) {
        const row = values.get(m) || new Map();
        row.set(pid, Math.max(row.get(pid) || 0, units[f.severity])); values.set(m, row);
      }
      let total = 0;
      for (const [m, row] of values) total += weight[m] * (1 - [...row.values()].reduce((clean, u) => clean * (1 - u / 20), 1));
      return measure(total / mass);
    };
    const owners = {'monolithic-module': 'P1', 'contamination-hub': 'P1', 'mixed-concerns': 'P1', 'parallel-abstractions': 'P5', 'tangled-graph': 'P7'};
    const skipped = new Set(data.principles.filter(p => p.skipped).map(p => p.id));
    const candidates = (data.structural?.candidates || []).map(c => ({...c, principle: c.principle || owners[c.archetype]})), resolutions = data.structural?.resolutions || {};
    const inReview = candidates.filter(c => !skipped.has(c.principle));
    const unresolved = inReview.map(c => c.id).filter(id => !resolutions[id]).sort();
    const firstPrinciple = new Map();
    const tagged = new Map();
    for (const p of data.principles) for (const f of p.findings || []) { if (!firstPrinciple.has(f.id)) firstPrinciple.set(f.id, p.id); tagged.set(f.id, [...(tagged.get(f.id) || []), p.id]); }
    const allOpen = [], allObserved = [];
    const principles = data.principles.map(p => {
      if (p.skipped) return {id: p.id, gate: 'skipped'};
      const fs = p.findings || [];
      const external = p.scoring_scope === 'external-only' || fs.length > 0 && fs.every(f => !(f.rootCostModuleIDs || f.observed_modules || []).length);
      const findings = fs.map(f => {
        const decision = normalize(data.decisions?.[f.id] || {status: 'open'});
        const inScope = roots(f).length > 0 || !(f.rootCostModuleIDs || f.observed_modules || []).length && f.external_scopes?.length > 0;
        const kind = f.kind || 'issue';
        const observed = inScope && kind === 'issue';
        const active = observed && decision.status === 'open';
        const findingExternal = !(f.rootCostModuleIDs || f.observed_modules || []).length && Boolean(f.external_scopes?.length);
        const originalRisk = findingExternal ? measure(null) : risk(observed ? [[f, p.id]] : []), implementationOnly = f.implementation_only === true;
        const presentation = kind === 'suggestion' ? 'suggestion' : originalRisk.score !== null && originalRisk.score < 0.01 - EPS ? 'tiny' : 'issue';
        return {...f, evidencedRootCostModuleIDs: f.rootCostModuleIDs || f.observed_modules || [], kind, presentation, decision, in_scope: Boolean(inScope), active,
          structural: Boolean(f.candidate_ids?.length), ...footprint(active ? [f] : [], findingExternal, implementationOnly), observed: footprint(observed ? [f] : [], findingExternal, implementationOnly),
          risk: findingExternal ? measure(null) : risk(active ? [[f, p.id]] : []), observed_risk: originalRisk};
      });
      const observed = findings.filter(f => f.in_scope && f.kind === 'issue'), open = observed.filter(f => f.active);
      const ledger = p.ledger || {};
      const counts = Object.fromEntries(['issue', 'clear', 'not-applicable', 'unassessed'].map(s => [s, modules.filter(m => (ledger[m]?.status || 'unassessed') === s).length]));
      const applicable = N - counts['not-applicable'];
      const applicableMass = modules.filter(m => ledger[m]?.status !== 'not-applicable').reduce((a, m) => a + weight[m], 0);
      const assessedMass = modules.filter(m => ['issue', 'clear'].includes(ledger[m]?.status)).reduce((a, m) => a + weight[m], 0);
      const cases = p.enforcement_cases || [];
      const enforcement = {evaluated_families: cases.length, failed: cases.filter(c => c.outcome === 'failed').length, unknown: cases.filter(c => c.outcome === 'unknown').length};
      const current = external ? measure(null) : risk(open.map(f => [f, p.id])), baseline = external ? measure(null) : risk(observed.map(f => [f, p.id]));
      const attention = Boolean(p.hard_gates?.length || enforcement.failed || open.some(f => f.severity === 'critical'));
      const gate = current.band === 'HIGH' ? 'fail'
        : unresolved.some(id => candidates.find(c => c.id === id).principle === p.id) || p.check_unknowns?.length || enforcement.unknown || external && !cases.length || !external && (counts.unassessed || applicable && !complete) ? 'incomplete'
        : !external && !applicable ? 'not-applicable' : current.band === 'MEDIUM' || attention ? 'watch' : 'pass';
      if (!external) { allOpen.push(...open); allObserved.push(...observed); }
      return {id: p.id, ...footprint(open, external), external, observed: footprint(observed, external), risk: current, observed_risk: baseline, counts, applicable,
        assessed_mass: applicableMass ? assessedMass / applicableMass : null,
        accepted_findings: observed.filter(f => f.decision.status === 'accepted').length, resolved_findings: observed.filter(f => f.decision.status === 'resolved').length, invalid_findings: observed.filter(f => f.decision.status === 'invalid').length,
        external_enforcement: enforcement, attention_required: attention, gate, findings};
    });
    const included = principles.filter(p => !p.external && !['skipped', 'not-applicable'].includes(p.gate));
    const unique = fs => [...new Map(fs.map(f => [f.id, [f, firstPrinciple.get(f.id)]])).values()];
    const overall = (fs, field) => {
      const known = included.every(p => p[field].score !== null);
      const withheld = unresolved.length ? 'structural candidates unresolved' : known ? null : 'unknown principle risk';
      return {...(withheld ? measure(null) : risk(unique(fs))), withheld, included_principles: included.map(p => p.id),
        coverage_complete: !unresolved.length && included.every(p => !p.counts.unassessed && !(data.principles.find(source => source.id === p.id).check_unknowns || []).length),
        assessed_mass_min: included.some(p => p.assessed_mass !== null) ? Math.min(...included.filter(p => p.assessed_mass !== null).map(p => p.assessed_mass)) : null};
    };
    const adjusted = overall(allOpen, 'risk');
    const seen = new Set(), ranking = [];
    for (const p of principles) for (const f of p.findings || []) if (f.kind === 'issue' && f.in_scope && f.observed_risk.score !== null && !seen.has(f.id)) {
      seen.add(f.id); ranking.push({id: f.id, principles: tagged.get(f.id), structural: f.structural, severity: f.severity, impact: f.observed_risk.score, open: f.active});
    }
    const tie = d => Math.abs(d) > EPS ? d : 0;
    ranking.sort((a, b) => tie(b.impact - a.impact) || Number(b.structural) - Number(a.structural) || rank[b.severity] - rank[a.severity] || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    const gates = new Set(principles.map(p => p.gate));
    const gate = gates.size === 1 && gates.has('skipped') ? 'skipped' : [...gates].every(g => ['skipped', 'not-applicable'].includes(g)) ? 'not-applicable' : adjusted.score === null ? 'incomplete' : adjusted.band === 'HIGH' ? 'fail' : adjusted.band === 'MEDIUM' ? 'watch' : 'pass';
    return {total: N, inventory_total: data.modules.length, risk: adjusted, observed_risk: overall(allObserved, 'observed_risk'), overall_gate: gate, ranking,
      structural: {screened: Boolean(data.structural), candidates: inReview.length, unresolved}, structure: data.structure?.repository || null, principles};
  }
  globalThis.ModularAuditScoring = {compute};
  if (typeof document === 'undefined') return;
  const embedded = document.getElementById('audit-data');
  if (!embedded) return;
  const original = JSON.parse(embedded.textContent), auditID = embedded.dataset.auditId;
  if (!auditID) throw new Error('Missing audit identity; prepare this report with prepare_report.py');
  let state = {decisions: Object.fromEntries(Object.entries(original.decisions || {}).map(([id, d]) => [id, normalize(d)])), excluded_modules: structuredClone(original.excluded_modules || [])};
  const initial = structuredClone(state), storageKey = 'modular-audit:' + auditID;
  const message = document.createElement('output'); message.className = 'review-message'; message.setAttribute('role', 'status');
  const controls = document.createElement('details'); controls.className = 'audit-controls'; controls.dataset.overview = '';
  controls.innerHTML = `<summary>Scope & saved choices</summary><div class="audit-control-body"><label>Ignored modules<select multiple size="6" data-module-scope></select></label><button type="button" data-apply-scope>Apply scope</button><div class="decision-actions"><button type="button" data-export>Export choices</button><label class="import-label">Import choices<input type="file" accept="application/json" data-import></label><button type="button" data-reset>Reset choices & scope</button></div></div>`;
  controls.append(message); document.getElementById('scores')?.after(controls);
  const scope = controls.querySelector('[data-module-scope]'); for (const m of original.modules) scope.add(new Option(m, m));
  const issueOrder = new Map([...document.querySelectorAll('details.issue')].map((issue, i) => [issue.id, i]));
  const statusLabels = {open: 'Open', resolved: 'Resolved', invalid: 'Invalid for this repo', accepted: 'Acceptable for this project'};
  function validate(value) {
    if (!value || typeof value.decisions !== 'object' || Array.isArray(value.decisions) || !value.decisions || !Array.isArray(value.excluded_modules)) throw new Error('Invalid choices file');
    const ids = new Set(original.principles.flatMap(p => (p.findings || []).map(f => f.id))), seen = new Set();
    for (const [id, raw] of Object.entries(value.decisions)) {
      const d = normalize(raw); if (!ids.has(id) || !['open', 'resolved', 'invalid', 'accepted'].includes(d.status) || d.status !== 'open' && d.decided_by && d.decided_by !== 'user') throw new Error('Choices require known findings and a supported status');
      value.decisions[id] = d;
    }
    for (const e of value.excluded_modules) { if (!original.modules.includes(e.module) || seen.has(e.module)) throw new Error('Unknown or duplicate module'); seen.add(e.module); e.reason ||= 'User-selected scope'; }
  }
  try { const saved = localStorage.getItem(storageKey); if (saved) { const parsed = JSON.parse(saved); validate(parsed); state = parsed; } }
  catch { message.textContent = 'Storage unavailable. Export to keep your choices.'; }
  const text = (parent, tag, value, cls = '') => { const el = document.createElement(tag); el.textContent = value; el.className = cls; parent.append(el); return el; };
  const percent = r => r.score === null ? 'N/A' : r.percent.toFixed(2) + '%';
  const chip = (parent, r) => text(parent, 'span', r.band || 'N/A', 'impact-band ' + (r.band?.toLowerCase() || ''));
  function persist() { try { localStorage.setItem(storageKey, JSON.stringify(state)); message.textContent = 'Saved.'; } catch { message.textContent = 'Export to keep your choices.'; } }
  function arrange(panel) {
    const shells = [...panel.querySelectorAll('.issue-shell')].sort((a, b) => Number(a.dataset.order) - Number(b.dataset.order));
    if (!shells.length) return;
    let group = panel.querySelector(':scope>.minor-issues');
    if (!group) { group = document.createElement('details'); group.className = 'minor-issues'; text(group, 'summary', ''); text(group, 'div', '', 'minor-list'); shells[0].before(group); }
    let small = 0;
    for (const shell of shells) { if (shell.classList.contains('issue-shell--small')) { if (shell.parentElement !== group.lastElementChild) group.lastElementChild.append(shell); small++; } else group.before(shell); }
    group.firstElementChild.textContent = `Suggestions & tiny issues · ${small}`; group.hidden = small === 0;
    const status = panel.querySelector('.principle-heading .status'); if (status) status.textContent = [shells.length - small ? `${shells.length - small} issues` : '', small ? `${small} small findings` : ''].filter(Boolean).join(' · ');
  }
  function render() {
    const focusID = document.activeElement?.id;
    const result = compute({...original, ...state}), scores = document.getElementById('scores');
    if (scores) {
      scores.replaceChildren(); const verdict = text(scores, 'div', '', 'verdict');
      text(verdict, 'h2', result.risk.withheld ? `Architecture health · withheld (${result.risk.withheld})` : `Architecture health · ${result.risk.health}/100`);
      chip(verdict, result.risk).setAttribute('aria-label', 'Overall risk band');
      const recalculate = text(verdict, 'button', 'Recalculate'); recalculate.type = 'button'; recalculate.id = 'audit-recalculate'; recalculate.dataset.recalculate = ''; recalculate.addEventListener('click', () => { persist(); render(); });
      text(verdict, 'span', result.risk.coverage_complete ? 'Coverage: complete' : 'Coverage: partial', 'fact-chip');
      const facts = text(scores, 'div', '', 'score-overall'); text(facts, 'span', `Risk ${percent(result.risk)}`); text(facts, 'span', `Observed ${result.observed_risk.health ?? 'N/A'}/100`);
      text(facts, 'span', `${result.total}/${result.inventory_total} modules in scope`); text(facts, 'span', original.module_weights ? 'Weighted by code mass' : 'Equal module weights');
      if (result.risk.assessed_mass_min !== null) text(facts, 'span', `Assessed mass ≥ ${(result.risk.assessed_mass_min * 100).toFixed(0)}%`);
      text(facts, 'span', result.structural.screened ? `Structural candidates ${result.structural.candidates - result.structural.unresolved.length}/${result.structural.candidates} resolved` : 'Structure scan missing');
      const st = result.structure;
      if (st) { const structure = text(scores, 'div', '', 'score-structure'); for (const label of [`Effective modules ${st.effective_modules}`, `Largest ${st.largest_module} ${(st.largest_share * 100).toFixed(0)}%`, `Change reaches ${(st.mass_propagation_cost * 100).toFixed(0)}% of code`, `Cycles ${st.cycles}`]) text(structure, 'span', label); }
      const top = result.ranking.filter(r => r.open).slice(0, 5);
      if (top.length) {
        const list = text(scores, 'ol', '', 'top-problems'); list.setAttribute('aria-label', 'Top problems by impact');
        for (const r of top) { const item = text(list, 'li', ''); const link = text(item, 'a', document.getElementById(r.id + '-title')?.textContent || document.getElementById(r.id)?.querySelector('h3')?.textContent || r.id); link.href = '#' + r.id; text(item, 'span', `${r.principles?.join(', ') || ''}${r.structural ? ' · structural' : ''} · ${r.severity} · ${(r.impact * 100).toFixed(1)}% risk`, 'score-sub'); }
      }
      const head = text(scores, 'div', '', 'score-head'); for (const label of ['Principle', 'Root cost', 'Affected', 'Risk / observed', 'Local status']) text(head, 'span', label);
      for (const p of result.principles) {
        const source = original.principles.find(s => s.id === p.id), row = text(scores, 'div', '', 'score-row');
        const link = text(row, 'a', p.id + ' ' + (source.title || ''), 'score-name'); link.href = '#' + p.id.toLowerCase();
        if (p.gate === 'skipped') { for (let i = 0; i < 3; i++) text(row, 'div', '—'); text(row, 'div', 'SKIPPED'); continue; }
        text(link, 'span', p.external ? 'Rule families' : `${p.counts.issue + p.counts.clear}/${p.applicable} classified`, 'score-sub');
        text(row, 'div', p.external ? '—' : String(p.rootCostModules)); text(row, 'div', p.external ? '—' : `${p.affectedModules ?? '?'}/${result.total}`);
        const value = text(row, 'div', ''); chip(value, p.risk); text(value, 'strong', p.external ? `${p.external_enforcement.failed}/${p.external_enforcement.evaluated_families} failed checks` : percent(p.risk));
        if (!p.external) text(value, 'span', 'Observed ' + percent(p.observed_risk), 'score-sub'); text(text(row, 'div', ''), 'span', p.gate.toUpperCase(), 'gate ' + p.gate);
      }
      const key = text(scores, 'div', '', 'score-key score-policy'); text(key, 'span', 'Health = 100 × (1 − risk). Risk: code mass exposed to open defects; strongest consequence per dimension, combined across dimensions.');
    }
    for (const p of result.principles) {
      if (p.gate === 'skipped') continue;
      const panel = document.getElementById(p.id.toLowerCase());
      let summary = panel?.querySelector(':scope>.principle-score');
      if (panel && !summary) { summary = document.createElement('div'); summary.className = 'principle-score'; panel.querySelector('.principle-heading')?.after(summary); }
      if (summary) { summary.replaceChildren(); text(summary, 'span', p.external ? 'External checks' : `Root cost ${p.rootCostModules} · Affected ${p.affectedModules ?? '?'}/${result.total}`); text(summary, 'strong', 'Risk ' + percent(p.risk)); text(summary, 'span', 'Observed ' + percent(p.observed_risk)); text(summary, 'span', p.gate.toUpperCase(), 'gate ' + p.gate); const handled = p.accepted_findings + p.resolved_findings + p.invalid_findings; if (handled) text(summary, 'span', `${handled} handled`); }
      const nav = document.querySelector(`[data-principle-link][href="#${p.id.toLowerCase()}"] .nav-result`); if (nav) nav.textContent = p.external ? `${p.external_enforcement.failed}/${p.external_enforcement.evaluated_families} checks` : percent(p.risk);
      for (const f of p.findings) {
        const issue = document.getElementById(f.id); if (!issue || issue.closest('.principle') !== panel) continue;
        issue.dataset.disposition = f.in_scope ? f.kind === 'suggestion' ? 'suggestion' : f.decision.status : 'out-of-scope';
        issue.dataset.presentation = f.presentation; issue.classList.toggle('issue--tiny', f.presentation === 'tiny'); issue.classList.toggle('issue--suggestion', f.presentation === 'suggestion');
        let shell = issue.parentElement;
        if (!shell.classList.contains('issue-shell')) { shell = document.createElement('div'); shell.className = 'issue-shell'; issue.before(shell); shell.append(issue); shell.dataset.order = issueOrder.get(f.id); }
        shell.classList.toggle('issue-shell--small', f.presentation !== 'issue');
        const metrics = issue.querySelector('.finding-metrics');
        if (metrics) { metrics.replaceChildren(); text(metrics, 'span', !f.in_scope ? 'Out of scope' : f.decision.status !== 'open' ? statusLabels[f.decision.status] : f.presentation === 'suggestion' ? 'Suggestion · unscored' : f.presentation === 'tiny' ? 'Tiny issue' : 'Open');
          if (f.presentation === 'issue') { text(metrics, 'span', p.external ? 'External checks' : `Root cost ${f.rootCostModules} · Affected ${f.affectedModules ?? '?'}/${result.total}`); chip(metrics, f.risk); }
          text(metrics, 'strong', 'Risk ' + percent(f.risk)); }
        if (!p.external) {
          let inventory = issue.querySelector('.counted-modules'); if (!inventory) { inventory = document.createElement('details'); inventory.className = 'counted-modules'; (issue.querySelector('.issue-body') || issue).prepend(inventory); }
          const wasOpen = inventory.open; inventory.replaceChildren(); text(inventory, 'summary', `Modules · ${f.rootCostModules} root cost · ${f.affectedModules ?? '?'} affected`);
          const columns = text(inventory, 'div', '', 'module-lists'); for (const [label, ids] of [['Root cost', f.rootCostModuleIDs], ['Affected', f.affectedModuleIDs]]) { const column = text(columns, 'div', ''); text(column, 'h4', `${label} · ${ids?.length ?? '?'}`); const list = text(column, 'ul', ''); for (const id of ids || []) text(text(list, 'li', ''), 'code', id); } inventory.open = wasOpen;
        }
        let editor = shell.querySelector(':scope>.decision-controls');
        if (!editor) {
          issue.querySelector('.decision-controls')?.remove(); editor = text(shell, 'div', '', 'decision-controls'); editor.setAttribute('role', 'group'); editor.setAttribute('aria-label', 'Review ' + (issue.querySelector('h3')?.textContent || f.id));
          for (const status of ['resolved', 'invalid', 'accepted']) {
            const label = text(editor, 'label', ''); const input = document.createElement('input'); input.type = 'checkbox'; input.value = status; input.id = `${f.id}-${status}`; input.name = `${f.id}-review`; label.append(input); text(label, 'span', statusLabels[status]);
            input.addEventListener('change', () => { state.decisions[f.id] = {status: input.checked ? status : 'open', decided_by: 'user'}; persist(); render(); });
          }
        }
        for (const input of editor.querySelectorAll('input')) { input.checked = f.decision.status === input.value; input.disabled = !f.in_scope; }
      }
      if (panel) arrange(panel);
    }
    for (const option of scope.options) option.selected = state.excluded_modules.some(e => e.module === option.value);
    if (focusID) document.getElementById(focusID)?.focus({preventScroll: true});
  }
  controls.querySelector('[data-apply-scope]').addEventListener('click', () => { const old = new Map(state.excluded_modules.map(e => [e.module, e.reason])); state.excluded_modules = [...scope.selectedOptions].map(o => ({module: o.value, reason: old.get(o.value) || 'User-selected scope'})); persist(); render(); });
  controls.querySelector('[data-export]').addEventListener('click', () => { const blob = new Blob([JSON.stringify({audit_id: auditID, ...state}, null, 2)], {type: 'application/json'}), url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = 'audit-decisions.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); });
  controls.querySelector('[data-import]').addEventListener('change', async event => { try { const file = event.target.files[0]; if (!file) return; const parsed = JSON.parse(await file.text()); if (parsed.audit_id !== auditID) throw new Error('Choices belong to a different audit'); validate(parsed); state = {decisions: parsed.decisions, excluded_modules: parsed.excluded_modules}; persist(); render(); } catch (error) { message.textContent = error.message; } event.target.value = ''; });
  controls.querySelector('[data-reset]').addEventListener('click', () => { state = structuredClone(initial); persist(); render(); });
  render();
})();
