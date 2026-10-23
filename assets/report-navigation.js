/* Embedded in the delivered HTML. Native disclosures remain usable without JavaScript. */
(() => {
  const panels = [...document.querySelectorAll('.principle[id]')];
  if (!panels.length) return;
  const overview = [...document.querySelectorAll('[data-overview]')];
  const breadcrumb = document.querySelector('.page-navigation');
  const current = document.querySelector('[data-current-principle]');
  const jump = document.querySelector('[data-issue-jump]');
  const motion = () => matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
  const hashID = () => { try { return decodeURIComponent(location.hash.slice(1)); } catch { return ''; } };
  const issueID = issue => issue?.id;
  function active(panel, issue) {
    document.querySelectorAll('[data-principle-link], [data-issue-link], [data-scores-link]').forEach(link => {
      const selected = link.hasAttribute('data-issue-link') ? link.hash === '#' + issueID(issue)
        : link.hasAttribute('data-principle-link') ? link.hash === '#' + panel?.id : !panel;
      if (selected) { link.setAttribute('aria-current', 'page'); const group = link.closest('details'); if (group) group.open = true; } else link.removeAttribute('aria-current');
    });
    document.querySelectorAll('.nav-issues').forEach(list => { list.hidden = list.closest('[data-principle]')?.dataset.principle !== panel?.id; });
    if (jump) jump.value = issueID(issue) || '';
  }
  function apply({ scroll = false, focus = false } = {}) {
    const id = hashID();
    const target = document.getElementById(id);
    const panel = target?.closest('.principle');
    const issue = target?.closest('details.issue');
    panels.forEach(p => { p.hidden = p !== panel; });
    overview.forEach(el => { el.hidden = Boolean(panel); });
    if (breadcrumb) breadcrumb.hidden = !panel;
    if (panel) {
      if (current) current.textContent = panel.id.toUpperCase() + ' · ' + (panel.querySelector('h2')?.textContent.replace(/^\s*(P\d+|S)\s*/i, '').trim() || '');
      if (jump) {
        jump.replaceChildren(new Option('All issues', ''));
        panel.querySelectorAll('details.issue').forEach(d => jump.add(new Option(d.querySelector('h3').textContent, d.id)));
        jump.closest('label').hidden = !panel.querySelector('details.issue');
      }
      // A principle is an index; a deep link opens only the requested issue.
      panel.querySelectorAll('details.issue').forEach(d => { d.open = d === issue; });
      if (panel === target) panel.querySelectorAll('.minor-issues').forEach(d => { d.open = false; });
      if (issue) {
        for (let ancestor = target; ancestor && ancestor !== panel; ancestor = ancestor.parentElement) {
          if (ancestor instanceof HTMLDetailsElement) ancestor.open = true;
        }
      }
    } else if (target) {
      for (let ancestor = target; ancestor; ancestor = ancestor.parentElement) {
        if (ancestor instanceof HTMLDetailsElement) ancestor.open = true;
      }
    }
    active(panel, issue);
    const destination = issue === target ? issue.querySelector('summary') : panel === target ? panel.querySelector('h2') : target || document.querySelector('.hero');
    if (focus && destination) { destination.tabIndex = -1; destination.focus({ preventScroll: true }); }
    if (scroll && destination) destination.scrollIntoView({ behavior: motion(), block: 'start' });
  }
  function navigate(hash) {
    if (hash !== location.hash) history.pushState(null, '', hash);
    apply({ scroll: true, focus: true });
  }
  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('a[href]');
    if (!link || link.target || link.hasAttribute('download')) return;
    const url = new URL(link.href);
    if (url.pathname !== location.pathname || url.search !== location.search || url.origin !== location.origin || !url.hash) return;
    if (!document.getElementById(decodeURIComponent(url.hash.slice(1)))) return;
    event.preventDefault(); navigate(url.hash);
  });
  if (jump) jump.addEventListener('change', () => {
    const panel = panels.find(p => !p.hidden);
    if (panel) navigate('#' + (jump.value || panel.id));
  });
  document.querySelectorAll('details.issue').forEach(issue => issue.addEventListener('toggle', () => {
    const panel = issue.closest('.principle');
    if (panel.hidden) return;
    const selected = document.getElementById(hashID())?.closest('details.issue');
    if (issue.open && selected !== issue) {
      history.pushState(null, '', '#' + issue.id); active(panel, issue);
    } else if (!issue.open && selected === issue) {
      history.replaceState(null, '', '#' + panel.id); active(panel, null);
    }
  }));
  let scheduled = false;
  function restore() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; apply({ scroll: true }); });
  }
  addEventListener('popstate', restore);
  addEventListener('hashchange', restore);
  apply({ scroll: Boolean(location.hash) });
})();
