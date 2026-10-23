/* One accepted bundle owns navigation, charts and evidence. No per-record requests. */
(function (root) {
  'use strict';
  const reportNames = {overview:'Overview', channel:'Channels', cohorts:'Cohorts', stages:'Stage loss',
    targeting:'Targeting', skills:'Skill evidence', aging:'Aging', inventory:'Opportunities', sankey:'Sankey'};
  const scopeKeys = ['start', 'end', 'profile', 'source'];
  function scopeFromURL(url) { return Object.fromEntries(scopeKeys.map(k => [k, url.searchParams.get(k) || ''])); }
  function routeFromURL(url) {
    const [report, group = '', subset = 'all'] = url.hash.slice(1).split('/');
    return {report: reportNames[report] ? report : 'overview', group: decodeURIComponent(group), subset};
  }
  function routeURL(url, report, group = '', subset = 'all') {
    const next = new URL(url); next.hash = report + (group ? '/' + encodeURIComponent(group) + '/' + subset : ''); return next.href;
  }
  function createStore(fetcher, changed = () => {}) {
    let sequence = 0;
    const state = {bundle:null, loading:false, stale:false, error:null, requestedScope:null};
    async function load(scope) {
      const ticket = ++sequence;
      state.loading = true; state.stale = !!state.bundle; state.error = null; state.requestedScope = scope; changed(state);
      try {
        const response = await fetcher('/api/reports/snapshot?' + new URLSearchParams(scope), {cache:'no-store'});
        const data = await response.json();
        if (ticket !== sequence) return;
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Report load failed.');
        state.bundle = data; state.stale = false; state.error = null;
      } catch (error) { if (ticket === sequence) {state.error = error.message; state.stale = !!state.bundle;} }
      finally { if (ticket === sequence) {state.loading = false; changed(state);} }
    }
    return {state, load};
  }
  function allGroups(report) {
    return ['groups','comparisons','descriptive','requirements','gap_groups','rejections','current','salary_groups'].flatMap(k => report[k] || []);
  }
  function escape(value) { return String(value ?? 'unavailable').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function safeURL(value) { try { const u = new URL(value); return ['http:','https:'].includes(u.protocol) ? u.href : null; } catch (_) {return null;} }
  const api = {createStore, scopeFromURL, routeFromURL, routeURL, allGroups, escape, safeURL, reportNames};
  if (typeof module !== 'undefined') module.exports = api;
  root.Reporting = api;
  if (typeof document === 'undefined') return;

  const $ = id => document.getElementById(id);
  const form = $('filters');
  const store = createStore((...args) => fetch(...args), render);
  let lastSnapshot = null;
  function link(report, group = '', text = reportNames[report], subset = 'all') {
    return `<a href="${escape(routeURL(location.href, report, group, subset))}">${escape(text)}</a>`;
  }
  function render() {
    const state = store.state;
    $('load-state').innerHTML = state.loading ? 'Loading… Previous snapshot is stale until replacement succeeds.' : state.error ?
      `<p class="error">Load failed: ${escape(state.error)} ${state.bundle ? 'Showing stale data in the previous accepted scope.' : 'No snapshot accepted.'}</p><button id="retry">Retry load</button>` : '';
    if ($('retry')) $('retry').onclick = () => store.load(state.requestedScope);
    const route = routeFromURL(new URL(location.href));
    $('navigation').innerHTML = Object.entries(reportNames).map(([key, name]) => `<a ${key === route.report ? 'aria-current="page"' : ''} href="${escape(routeURL(location.href,key))}">${name}</a>`).join('');
    const bundle = state.bundle;
    if (!bundle) return;
    $('scope').textContent = `Accepted application scope: ${bundle.scope.start || 'all dates'} → ${bundle.scope.end || 'present'} · profile ${bundle.scope.profile || 'all'} · source ${bundle.scope.source || 'all'} · ${bundle.selected_ids.length} applied applications · retrieved ${bundle.retrieved_at}${state.stale ? ' · STALE' : ''}`;
    if (!state.loading && !state.error) {
      for (const key of scopeKeys) {
        const field = form.elements.namedItem(key);
        if (key === 'profile' || key === 'source') field.innerHTML = `<option value="">All ${key === 'profile' ? 'profiles' : 'sources'}</option>` + bundle.filter_options[key].map(v => `<option value="${escape(v)}">${escape(v)}</option>`).join('');
        field.value = bundle.scope[key];
      }
    }
    const changedSnapshot = lastSnapshot !== null && lastSnapshot !== bundle.snapshot_id;
    lastSnapshot = bundle.snapshot_id;
    if (route.group && !findGroup(bundle, route)) {
      history.replaceState(null, '', routeURL(location.href,route.report));
      $('load-state').append(document.createTextNode('The previous evidence selection is no longer available; it has been cleared.'));
      route.group = '';
    }
    $('content').innerHTML = renderReport(bundle, route, link);
    renderEvidence(bundle, route);
    if (route.group && !changedSnapshot) $('evidence-heading')?.focus();
  }
  function findGroup(bundle, route) {
    if (route.report === 'overview' && route.group === 'never-applied') return {label:'Never applied · excluded from outcome denominators', ids:bundle.never_applied_ids};
    if (route.report === 'overview' && route.group === 'unknown-date') return {label:'Unknown applied date · excluded by date range', ids:bundle.unknown_date_excluded_ids};
    return allGroups(bundle.reports[route.report] || {}).find(g => g.key === route.group);
  }
  function renderReport(bundle, route, link) {
    if (api.presentation) return api.presentation(bundle, route, link);
    if (route.report === 'overview') return `<h2>Where to focus next</h2><p>${escape(bundle.brief.message)}</p>` + bundle.brief.leads.map(l => `<p>${link(l.report,l.group_key,l.text)}</p><p>${escape(l.caveat)}</p>`).join('');
    const report = bundle.reports[route.report];
    return `<h2>${escape(report.title)}</h2><p>${escape(report.caveat || report.reason || report.state)}</p>` + allGroups(report).map(g => `<p>${link(route.report,g.key,g.label)}: ${g.denominator}</p>`).join('');
  }
  function renderEvidence(bundle, route) {
    const selected = findGroup(bundle, route), region = $('evidence');
    region.hidden = !selected;
    if (!selected) {region.innerHTML = ''; return;}
    const ids = route.subset === 'numerator' ? selected.numerator_ids || [] : selected.ids;
    const records = route.report === 'inventory' ? bundle.postings : bundle.applications;
    region.innerHTML = `<h2 id="evidence-heading" tabindex="-1">${escape(selected.label)} · ${ids.length} records${route.subset === 'numerator' ? ' · numerator only' : ''}</h2><p>${link(route.report,'','Close evidence')}</p><div class="table-scroll"><table><caption>Exact accepted-snapshot evidence</caption><thead><tr><th>ID</th><th>Company / role</th><th>Recorded details</th></tr></thead><tbody>` + ids.map(id => {
      const r = records[String(id)];
      if (!r) return '';
      const url = safeURL(r.job_url || r.canonical_url);
      return `<tr><th scope="row">${id}</th><td>${escape(r.company)}<br>${escape(r.role)}${url ? `<br><a href="${escape(url)}" rel="noreferrer noopener" target="_blank">External posting</a>` : ''}</td><td><details><summary>Inspect recorded evidence</summary><pre>${escape(JSON.stringify(r,null,2))}</pre></details></td></tr>`;
    }).join('') + '</tbody></table></div>';
  }
  function navigate() {
    const scope = scopeFromURL(new URL(location.href));
    if (!store.state.bundle || JSON.stringify(scope) !== JSON.stringify(store.state.bundle.scope)) store.load(scope);
    else render();
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    const url = new URL(location.href);
    for (const key of scopeKeys) { const value = form.elements.namedItem(key).value; if (value) url.searchParams.set(key,value); else url.searchParams.delete(key); }
    history.pushState(null,'',url); store.load(scopeFromURL(url));
  });
  $('refresh').onclick = () => store.load(scopeFromURL(new URL(location.href)));
  addEventListener('hashchange',navigate); addEventListener('popstate',navigate);
  navigate();
})(typeof globalThis !== 'undefined' ? globalThis : this);
