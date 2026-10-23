/* No dependencies. Python scorer is authoritative; parity fixtures verify this browser projection. */
(() => {
  const units = {low: 1, medium: 4, high: 10, critical: 10}, rank = {low: 0, medium: 1, high: 2, critical: 3};
  const EPS = 1e-12;
  // Integer numerators keep band boundaries exact: LOW < 3%, MEDIUM < 10%, HIGH from 10%.
  const measure = (num, den) => num === null || !den ? {score: null, percent: null, band: null}
    : {score: num / den, percent: num * 100 / den, band: num * 100 < 3 * den ? 'LOW' : num * 100 < 10 * den ? 'MEDIUM' : 'HIGH'};
  const normalize = d => ({...d, status: d.status === 'intended' ? 'accepted' : d.status});
  function compute(data) {
    const excluded = new Set((data.excluded_modules || []).map(e => e.module));
    const modules = data.modules.filter(m => !excluded.has(m));
    const eligible = new Set(modules), graph = data.consumers || {}, N = modules.length;
    const authority = ['source', 'authority'].some(k => typeof data.consumer_graph_provenance?.[k] === 'string' && data.consumer_graph_provenance[k].trim());
    const complete = data.consumer_graph_complete === true && authority && modules.every(m => Object.hasOwn(graph, m));
    const roots = f => (f.evidencedRootCostModuleIDs || f.rootCostModuleIDs || f.observed_modules || []).filter(m => eligible.has(m));
    const exposureMode = f => f.exposure || (f.implementation_only === true ? 'owners' : 'importers');
    // Modules besides the owners that a defect reaches: every importer, verified consumers only, or none.
    const reached = f => {
      const own = new Set(roots(f)), mode = exposureMode(f);
      if (mode === 'owners') return [];
      if (mode === 'verified') return (f.reach_modules || []).filter(m => eligible.has(m) && !own.has(m));
      return [...new Set([...own].flatMap(m => graph[m].filter(n => eligible.has(n))))];
    };
    const severity = (f, pid) => f.principle_severity?.[pid] || f.base_severity || f.severity;
    const footprint = (fs, external = false) => {
      const owners = [...new Set(fs.flatMap(roots))].sort();
      const available = !external && complete && N > 0;
      const affected = available ? [...new Set(fs.flatMap(reached))].sort() : null;
      const exposed = available ? [...new Set([...owners, ...affected])] : null;
      return {rootCostModules: external ? null : owners.length, rootCostModuleIDs: owners, affectedModules: affected?.length ?? null, affectedModuleIDs: affected,
        impact: measure(exposed ? exposed.length : null, N)};
    };
    const risk = pairs => {
      if (!complete || !N) return {...measure(null, N), units: null, involved_modules: null};
      const values = new Map();
      for (const [f, pid] of pairs) for (const m of new Set([...roots(f), ...reached(f)])) values.set(m, Math.max(values.get(m) || 0, units[severity(f, pid)]));
      const sum = [...values.values()].reduce((a, b) => a + b, 0);
      return {...measure(sum, 10 * N), units: sum, involved_modules: values.size};
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
      const issues = fs.filter(f => (f.kind || 'issue') === 'issue');
      const external = p.scoring_scope === 'external-only' || issues.length > 0 && issues.every(f => !(f.rootCostModuleIDs || f.observed_modules || []).length);
      const findings = fs.map(f => {
        const decision = normalize(data.decisions?.[f.id] || {status: 'open'});
        const inScope = roots(f).length > 0 || !(f.rootCostModuleIDs || f.observed_modules || []).length && f.external_scopes?.length > 0;
        const kind = f.kind || 'issue';
        const observed = inScope && kind === 'issue';
        const active = observed && decision.status === 'open';
        const findingExternal = !(f.rootCostModuleIDs || f.observed_modules || []).length && Boolean(f.external_scopes?.length);
        const originalRisk = findingExternal ? measure(null, N) : risk(observed ? [[f, p.id]] : []), own = severity(f, p.id);
        const presentation = kind === 'suggestion' ? 'suggestion' : originalRisk.score !== null && originalRisk.units * 100 < 2 * 10 * N && originalRisk.involved_modules <= 2 && ['low', 'medium'].includes(own) ? 'tiny' : 'issue';
        return {...f, evidencedRootCostModuleIDs: f.rootCostModuleIDs || f.observed_modules || [], kind, presentation, decision, in_scope: Boolean(inScope), active,
          structural: Boolean(f.candidate_ids?.length), base_severity: f.base_severity || f.severity, severity: own, exposure: exposureMode(f), ...footprint(active ? [f] : [], findingExternal), observed: footprint(observed ? [f] : [], findingExternal),
          risk: findingExternal ? measure(null, N) : risk(active ? [[f, p.id]] : []), observed_risk: originalRisk};
      });
      const observed = findings.filter(f => f.in_scope && f.kind === 'issue'), open = observed.filter(f => f.active);
      const ledger = p.ledger || {};
      const counts = Object.fromEntries(['issue', 'clear', 'not-applicable', 'unassessed'].map(s => [s, modules.filter(m => (ledger[m]?.status || 'unassessed') === s).length]));
      const applicable = N - counts['not-applicable'];
      const cases = p.enforcement_cases || [];
      const enforcement = {evaluated_families: cases.length, failed: cases.filter(c => c.outcome === 'failed').length, unknown: cases.filter(c => c.outcome === 'unknown').length};
      const current = external ? measure(null, N) : risk(open.map(f => [f, p.id])), baseline = external ? measure(null, N) : risk(observed.map(f => [f, p.id]));
      const attention = Boolean(p.hard_gates?.length || enforcement.failed || open.some(f => f.severity === 'critical'));
      const gate = current.band === 'HIGH' ? 'fail'
        : unresolved.some(id => candidates.find(c => c.id === id).principle === p.id) || p.check_unknowns?.length || enforcement.unknown || external && !cases.length || !external && (counts.unassessed || applicable && !complete) ? 'incomplete'
        : !external && !applicable ? 'not-applicable' : current.band === 'MEDIUM' || attention ? 'watch' : 'pass';
      if (!external) { allOpen.push(...open); allObserved.push(...observed); }
      return {id: p.id, ...footprint(open, external), external, open_issues: open.length, observed_issues: observed.length, observed: footprint(observed, external), risk: current, observed_risk: baseline, counts, applicable,
        coverage: applicable ? (counts.issue + counts.clear) / applicable : null,
        accepted_findings: observed.filter(f => f.decision.status === 'accepted').length, resolved_findings: observed.filter(f => f.decision.status === 'resolved').length, invalid_findings: observed.filter(f => f.decision.status === 'invalid').length,
        external_enforcement: enforcement, attention_required: attention, gate, findings};
    });
    const included = principles.filter(p => !p.external && !['skipped', 'not-applicable'].includes(p.gate));
    const unique = fs => [...new Map(fs.map(f => [f.id, [f, firstPrinciple.get(f.id)]])).values()];
    const overall = (fs, field) => {
      const known = included.every(p => p[field].score !== null);
      const withheld = unresolved.length ? 'structural candidates unresolved' : known ? null : 'unknown principle risk';
      const union = risk(unique(fs));
      const worst = withheld ? null : included.reduce((best, p) => best === null || p[field].units > best[field].units ? p : best, null);
      const value = withheld ? {...measure(null, N), units: null} : worst === null ? {...union} : {...worst[field]};
      return {...value, withheld, worst_principle: worst?.id ?? null, worst_involved_modules: worst ? worst[field].involved_modules : null,
        involved_modules: withheld ? null : union.involved_modules, included_principles: included.map(p => p.id),
        coverage_complete: !unresolved.length && included.every(p => !p.counts.unassessed && !(data.principles.find(source => source.id === p.id).check_unknowns || []).length),
        coverage_min: included.some(p => p.coverage !== null) ? Math.min(...included.filter(p => p.coverage !== null).map(p => p.coverage)) : null};
    };
    const adjusted = overall(allOpen, 'risk');
    const seen = new Set(), ranking = [];
    for (const p of principles) for (const f of p.findings || []) if (f.kind === 'issue' && f.in_scope && f.observed_risk.score !== null && !seen.has(f.id)) {
      seen.add(f.id); ranking.push({id: f.id, principles: tagged.get(f.id), structural: f.structural, severity: f.severity, impact: f.observed_risk.score, defect_modules: f.observed.rootCostModules, involved_modules: f.observed_risk.involved_modules, open: f.active});
    }
    const tie = d => Math.abs(d) > EPS ? d : 0;
    ranking.sort((a, b) => tie(b.impact - a.impact) || Number(b.structural) - Number(a.structural) || rank[b.severity] - rank[a.severity] || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    const gates = new Set(principles.map(p => p.gate));
    const gate = gates.size === 1 && gates.has('skipped') ? 'skipped' : [...gates].every(g => ['skipped', 'not-applicable'].includes(g)) ? 'not-applicable' : adjusted.score === null ? 'incomplete' : adjusted.band === 'HIGH' ? 'fail' : adjusted.band === 'MEDIUM' ? 'watch' : 'pass';
    return {total: N, inventory_total: data.modules.length, small_inventory: N < 10, ...footprint(allOpen), risk: adjusted, observed_risk: overall(allObserved, 'observed_risk'), overall_gate: gate, ranking,
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
  const percent = r => r.score === null ? 'N/A' : (Math.floor(r.percent * 10 + 0.5) / 10).toFixed(1) + '%';
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
      scores.replaceChildren(); const verdict = text(scores, 'div', '', 'verdict'), N = result.total;
      const worst = result.risk.worst_principle, worstTitle = worst ? `${worst} ${original.principles.find(p => p.id === worst)?.title || ''}`.trim() : '';
      text(verdict, 'h2', result.risk.withheld ? `Risk withheld · ${result.risk.withheld}` : worst ? `Risk ${percent(result.risk)} · worst principle ${worstTitle}` : `Risk ${percent(result.risk)}`);
      chip(verdict, result.risk).setAttribute('aria-label', 'Overall risk band');
      const recalculate = text(verdict, 'button', 'Recalculate'); recalculate.type = 'button'; recalculate.id = 'audit-recalculate'; recalculate.dataset.recalculate = ''; recalculate.addEventListener('click', () => { persist(); render(); });
      text(verdict, 'span', result.risk.coverage_complete ? 'Coverage: complete' : 'Coverage: partial', 'fact-chip');
      const facts = text(scores, 'div', '', 'score-overall');
      for (const label of [`${result.risk.involved_modules ?? '?'}/${N} modules involved across all principles`, `Defects in ${result.rootCostModules ?? '?'}/${N} modules`, `Before review choices ${percent(result.observed_risk)}`, `${N}/${result.inventory_total} modules in scope`,
        result.risk.coverage_min !== null ? `Lowest principle classification ${Math.floor(result.risk.coverage_min * 100)}%` : 'Classification unknown',
        result.structural.screened ? `Structural candidates ${result.structural.candidates - result.structural.unresolved.length}/${result.structural.candidates} resolved` : 'Structure scan missing',
        ...(result.small_inventory ? [`Only ${N} modules: one module is at least 10% of every score, so read the issue counts too`] : [])]) text(facts, 'span', label);
      const st = result.structure;
      if (st) { const structure = text(scores, 'div', '', 'score-structure'); for (const label of ['Structure scan:', `effective modules ${st.effective_modules}`, `largest ${st.largest_module} holds ${(st.largest_share * 100).toFixed(0)}% of code`, `a change reaches ${(st.mass_propagation_cost * 100).toFixed(0)}% of code`, `cycles ${st.cycles}`]) text(structure, 'span', label); }
      const top = result.ranking.filter(r => r.open).slice(0, 5);
      if (top.length) {
        text(scores, 'h3', 'Top problems by risk', 'top-problems-title');
        const list = text(scores, 'ol', '', 'top-problems'); list.setAttribute('aria-label', 'Top problems by risk');
        for (const r of top) {
          const item = text(list, 'li', ''); const link = text(item, 'a', document.getElementById(r.id + '-title')?.textContent || document.getElementById(r.id)?.querySelector('h3')?.textContent || r.id); link.href = '#' + r.id;
          text(item, 'span', `${r.principles.join(', ')}${r.structural ? ' · structural' : ''} · ${r.severity} · defects in ${r.defect_modules} ${r.defect_modules === 1 ? 'module' : 'modules'} · ${r.involved_modules}/${N} involved · ${percent({score: r.impact, percent: r.impact * 100})} risk`, 'score-sub');
        }
      }
      const head = text(scores, 'div', '', 'score-head'); for (const label of ['Principle', 'Defect modules', 'Involved', 'Risk', 'Local status']) text(head, 'span', label);
      for (const p of result.principles) {
        const source = original.principles.find(s => s.id === p.id), row = text(scores, 'div', '', 'score-row');
        const link = text(row, 'a', p.id + ' ' + (source.title || ''), 'score-name'); link.href = '#' + p.id.toLowerCase();
        if (p.gate === 'skipped') { for (let i = 0; i < 3; i++) text(row, 'div', '—'); text(row, 'div', 'SKIPPED'); continue; }
        text(link, 'span', p.external ? 'Rule families' : `${p.counts.issue + p.counts.clear}/${p.applicable} classified · ${p.open_issues} open ${p.open_issues === 1 ? 'issue' : 'issues'}`, 'score-sub');
        text(row, 'div', p.external ? '—' : `${p.rootCostModules}/${N}`); text(row, 'div', p.external ? '—' : `${p.risk.involved_modules ?? '?'}/${N}`);
        const value = text(row, 'div', ''); chip(value, p.risk); text(value, 'strong', p.external ? `${p.external_enforcement.failed}/${p.external_enforcement.evaluated_families} failed checks` : percent(p.risk));
        if (!p.external) text(value, 'span', 'Before review ' + percent(p.observed_risk), 'score-sub'); text(text(row, 'div', ''), 'span', p.gate.toUpperCase(), 'gate ' + p.gate);
      }
      const key = text(scores, 'div', '', 'score-key score-policy'); text(key, 'span', "Overall risk = the worst principle's risk. Principle risk = severity-weighted share of modules that own or directly import its open defects (low 0.1 · medium 0.4 · high and critical 1.0); each module counts once, at its strongest defect. LOW < 3% · MEDIUM < 10% · HIGH ≥ 10%.");
    }
    for (const p of result.principles) {
      if (p.gate === 'skipped') continue;
      const panel = document.getElementById(p.id.toLowerCase());
      let summary = panel?.querySelector(':scope>.principle-score');
      if (panel && !summary) { summary = document.createElement('div'); summary.className = 'principle-score'; panel.querySelector('.principle-heading')?.after(summary); }
      if (summary) { summary.replaceChildren(); text(summary, 'span', p.external ? 'External checks' : `Defects in ${p.rootCostModules}/${result.total} · ${p.risk.involved_modules ?? '?'}/${result.total} involved`); text(summary, 'strong', 'Risk ' + percent(p.risk)); text(summary, 'span', 'Before review ' + percent(p.observed_risk)); text(summary, 'span', p.gate.toUpperCase(), 'gate ' + p.gate); const handled = p.accepted_findings + p.resolved_findings + p.invalid_findings; if (handled) text(summary, 'span', `${handled} handled`); }
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
          if (f.presentation === 'issue') { text(metrics, 'span', p.external ? 'External checks' : `Defects in ${f.rootCostModules}/${result.total} · ${f.risk.involved_modules ?? '?'}/${result.total} involved`); chip(metrics, f.risk); }
          text(metrics, 'strong', 'Risk ' + percent(f.risk)); }
        if (!p.external) {
          let inventory = issue.querySelector('.counted-modules'); if (!inventory) { inventory = document.createElement('details'); inventory.className = 'counted-modules'; (issue.querySelector('.issue-body') || issue).prepend(inventory); }
          const wasOpen = inventory.open; inventory.replaceChildren(); text(inventory, 'summary', `Modules · ${f.rootCostModules} with the defect · ${f.affectedModules ?? '?'} importing them`);
          const columns = text(inventory, 'div', '', 'module-lists'); for (const [label, ids] of [['Defect modules', f.rootCostModuleIDs], ['Importing modules', f.affectedModuleIDs]]) { const column = text(columns, 'div', ''); text(column, 'h4', `${label} · ${ids?.length ?? '?'}`); const list = text(column, 'ul', ''); for (const id of ids || []) text(text(list, 'li', ''), 'code', id); } inventory.open = wasOpen;
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
