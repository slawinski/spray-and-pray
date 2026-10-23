(function (root) {
  'use strict';
  const reportNames = {overview:'Overview', channel:'Channels', cohorts:'Cohorts', stages:'Stage loss',
    targeting:'Targeting', skills:'Skill evidence', aging:'Aging', inventory:'Opportunities', sankey:'Sankey'};
  const scopeKeys = ['start', 'end', 'profile', 'source'];
  function scopeFromURL(url) { return Object.fromEntries(scopeKeys.map(k => [k, url.searchParams.get(k) || ''])); }
  function routeFromURL(url) {
    const [report, group = '', subset = 'all'] = url.hash.slice(1).split('/');
    let decoded = ''; try { decoded = decodeURIComponent(group); } catch (_) {}
    return {report: reportNames[report] ? report : 'overview', group: decoded, subset};
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
    function restoreAccepted() {
      ++sequence;
      state.loading = false; state.stale = false; state.error = null; state.requestedScope = state.bundle.scope;
      changed(state);
    }
    return {state, load, restoreAccepted};
  }
  function allGroups(report) {
    return ['groups','comparisons','descriptive','requirements','gap_groups','rejections','current','salary_groups'].flatMap(k => report[k] || []);
  }
  function escape(value) { return String(value ?? 'unavailable').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function safeURL(value) { try { const u = new URL(value); return ['http:','https:'].includes(u.protocol) ? u.href : null; } catch (_) {return null;} }
  function table(caption, headers, rows) {
    return `<div class="table-scroll"><table><caption>${escape(caption)}</caption><thead><tr>${headers.map(h=>`<th scope="col">${escape(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map((cell,i)=>`<${i ? 'td' : 'th scope="row"'}>${cell}</${i ? 'td' : 'th'}>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  function rate(g) { return g.rate == null ? `Unavailable · ${escape(g.reason || 'insufficient data')}` : `${g.numerator}/${g.denominator} · ${(g.rate*100).toFixed(1)}%`; }
  function evidenceTable(report, groups, caption, link, incidence=false) {
    return table(caption, ['Recorded group', incidence ? 'Interview attainment / applications' : 'Distinct applications / postings', 'Coverage / interpretation', 'Inspect'], groups.map(g=>[
      escape(g.label), incidence ? rate(g) : String(g.denominator),
      escape(g.analytical_subset || g.reason || (g.ages ? `Recorded age ${g.ages.min == null ? 'unavailable' : g.ages.min.toFixed(1)+'–'+g.ages.max.toFixed(1)+' days'}; ${g.ages.known} known, ${g.ages.unknown} unknown` : g.partition || 'Distinct recorded members')) +
        (g.raw_variants ? `<details><summary>Raw label variants</summary>${g.raw_variants.map(escape).join('<br>')}</details>` : '') +
        (g.partition ? `<details><summary>Scoring provenance partition</summary><code>${escape(g.partition)}</code></details>` : ''),
      link(report,g.key,'All '+g.denominator) + (incidence ? ' · '+link(report,g.key,'Interviewed '+g.numerator,'numerator') : '')
    ]));
  }
  function barChart(groups, incidence=false, title='Recorded counts') {
    if (!groups.length) return '<p>No groups in this selection.</p>';
    const max = Math.max(1,...groups.map(g=>incidence ? (g.rate ?? 0)*100 : g.denominator));
    const height = groups.length*42+12;
    return `<div class="chart-scroll"><svg class="bars" viewBox="0 0 850 ${height}" role="img" aria-label="${escape(title)}"><title>${escape(title)}</title>` + groups.map((g,i)=>{
      const value = incidence ? (g.rate ?? 0)*100 : g.denominator;
      return `<text x="0" y="${i*42+26}">${escape(g.label)}</text><rect x="310" y="${i*42+10}" width="${value/max*360}" height="20"/><text x="690" y="${i*42+26}">${incidence ? g.rate == null ? 'Unavailable' : `${g.numerator}/${g.denominator}` : g.denominator}</text>`;
    }).join('')+'</svg></div>';
  }
  function sankeyChart(report) {
    const nodes = report.nodes || [], links = report.links || [];
    if (!nodes.length) return '<p>No recorded paths in this selection.</p>';
    const positions = [...new Set(nodes.map(n=>n.position))];
    const lanes = positions.map(p=>nodes.filter(n=>n.position===p));
    const maxCount = Math.max(1,...nodes.map(n=>n.count));
    const height = Math.max(220, ...lanes.map(l=>l.length*100+40));
    const width = Math.max(850,positions.length*310);
    const coordinates = new Map();
    lanes.forEach((lane,p)=>lane.forEach((n,i)=>coordinates.set(n.key,{x:p*310+16,y:i*100+46,h:Math.max(8,n.count/maxCount*45)})));
    const offsetsOut = new Map(), offsetsIn = new Map();
    const paths = links.map(l=>{
      const a=coordinates.get(l.source),b=coordinates.get(l.target);
      if (!a || !b) return '';
      const w = l.count/maxCount*45, out=offsetsOut.get(l.source)||0, inc=offsetsIn.get(l.target)||0;
      offsetsOut.set(l.source,out+w); offsetsIn.set(l.target,inc+w);
      return `<path d="M ${a.x+14} ${a.y+out+w/2} C ${a.x+155} ${a.y+out+w/2}, ${b.x-140} ${b.y+inc+w/2}, ${b.x} ${b.y+inc+w/2}" stroke-width="${w}"/>`;
    }).join('');
    return `<div class="chart-scroll"><svg class="sankey" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="Recorded application transitions; adjacent tables contain exact counts"><title>Recorded transition occurrences, not current-status totals</title>${paths}`+
      nodes.map(n=>{const c=coordinates.get(n.key);const words=(n.label+' · '+n.count).match(/.{1,28}(?:\s|$)|\S+/g)||[];return `<rect x="${c.x}" y="${c.y}" width="14" height="${c.h}"/><text x="${c.x}" y="${c.y-24}">${words.map((word,i)=>`<tspan x="${c.x}" dy="${i?16:0}">${escape(word)}</tspan>`).join('')}</text>`;}).join('')+'</svg></div>';
  }
  function cohortHeatmap(groups, link) {
    const weeks = [...new Set(groups.map(g=>g.week))].filter(Boolean);
    return table('Weekly interview attainment · full cohort denominators', ['UTC week starting Monday','7 recorded days','14 recorded days','30 recorded days'],weeks.map(week=>[
      escape(week), ...[7,14,30].map(h=>{
        const g=groups.find(g=>g.week===week && g.horizon===h);
        return g ? `<div class="heat ${g.rate == null ? 'immature' : 'mature'}">${rate(g)}<br>${g.matured_count}/${g.denominator} matured<br>${link('cohorts',g.key,'Inspect cohort')}</div>` : 'Unavailable';
      })
    ]));
  }
  function safeSankeyChart(report) {
    try {return sankeyChart(report);} catch (_) {return '<p>Visualization unavailable. Read the evidence table below.</p>';}
  }
  function skillMatrix(groups, link) {
    const levels = ['direct','framework_transfer','strong_transfer','framework_depth_gap','partial','none','unknown'];
    return table('Distinct assessed applications · evidence columns can overlap', ['Category / requirement','Demand','Must / core / union','Partial-or-none core/must union',...levels], groups.map(g=>[
      link('skills',g.key,g.label), String(g.denominator), `${g.must_ids?.length || 0} / ${g.core_ids?.length || 0} / ${g.must_core_ids?.length || 0}`,
      link('skills',g.key,String(g.gap_ids?.length || 0),'gap'),
      ...levels.map(level=>link('skills',g.key,String(g.evidence?.[level]?.length || 0),'evidence:'+level))
    ]));
  }
  function stageChart(groups) {
    const stages = [...new Set(groups.map(g=>g.stage))].filter(Boolean);
    const resolutions = ['progressed','rejection','withdrawal','accepted','unresolved','unknown/anomalous'];
    return `<p>${resolutions.map((r,i)=>`<span class="legend legend-${i}">${r}</span>`).join(' ')}</p><div class="chart-scroll"><svg class="stages" viewBox="0 0 850 ${stages.length*50+10}" role="img" aria-label="Recorded stage visit partitions; exact values in the next table">`+stages.map((stage,i)=>{
      const rows=groups.filter(g=>g.stage===stage), count=rows[0].stage_visit_count;
      let x=240;
      return `<text x="0" y="${i*50+30}">${escape(stage)} · ${count} visits</text>`+resolutions.map((r,j)=>{
        const n=rows.find(g=>g.resolution===r)?.denominator || 0,w=count ? n/count*580 : 0;
        const rect=`<rect class="segment-${j}" x="${x}" y="${i*50+10}" width="${w}" height="26"><title>${escape(r)}: ${n}/${count}</title></rect>`;x+=w;return rect;
      }).join('');
    }).join('')+'</svg></div>';
  }
  function salaryChart(groups) {
    return groups.map(g=>{
      const ranges=g.ranges || [], numbers=ranges.flatMap(r=>[r.min,r.max]).filter(Number.isFinite), max=Math.max(1,...numbers);
      return `<h3>${escape(g.label)} · ${g.comparable ? 'Comparable units' : 'Non-comparable / missing units'}</h3><div class="chart-scroll"><svg class="salary" viewBox="0 0 850 ${ranges.length*38+10}" role="img" aria-label="${escape(g.label)} salary ranges, open ends labeled">`+ranges.map((r,i)=>{
        const lo=Number.isFinite(r.min)?r.min:null,hi=Number.isFinite(r.max)?r.max:null;
        return `<text x="0" y="${i*38+24}">Posting ${r.id}</text>`+ (g.comparable && lo!==null && hi!==null ? `<line x1="${160+lo/max*380}" x2="${160+hi/max*380}" y1="${i*38+18}" y2="${i*38+18}"/>` : '')+`<text x="570" y="${i*38+24}">${lo ?? 'open'} – ${hi ?? 'open'}</text>`;
      }).join('')+'</svg></div>';
    }).join('');
  }
  function presentation(bundle, route, link) {
    const name=route.report, reports=bundle.reports;
    if (name==='overview') {
      return `<section class="brief"><h2>Where to focus next</h2><p>${escape(bundle.brief.message)}</p>`+
        (bundle.brief.leads.length ? `<ol>${bundle.brief.leads.map(l=>`<li><h3>${link(l.report,l.group_key,l.text)}</h3><p>${escape(l.caveat)}</p>${l.comparison_group_key ? `<p>${link(l.report,l.comparison_group_key,'Inspect comparison group')}</p>` : ''}</li>`).join('')}</ol>` : `<p>${link('channel','','Inspect channel coverage')} · ${link('targeting','','Inspect assessment coverage')} · ${link('skills','','Inspect requirement evidence')}</p>`)+
        `<details><summary>Evidence sufficiency rules</summary>${bundle.brief.reasons.map(r=>`<p>${escape(r)}</p>`).join('')}</details></section>`+
        `<p class="population">${bundle.selected_ids.length} distinct applied applications · ${link('overview','never-applied',bundle.never_applied_ids.length+' never-applied records excluded')} · ${link('overview','unknown-date',bundle.unknown_date_excluded_ids.length+' unknown applied dates excluded by date range')}</p>`+
        `<section><h2>Recorded application paths</h2><p>${link('sankey','','Open full Sankey and transition evidence')}</p><p>${escape(reports.sankey.caveat)}</p>${safeSankeyChart(reports.sankey)}${evidenceTable('sankey',reports.sankey.current || [],'Current-status counts · separate from transition occurrences',link)}</section>`;
    }
    const report=reports[name];
    let html=`<h2>${escape(report.title)}</h2>`;
    if (name==='inventory') html+='<p class="scope-note">All captured postings · independent discovery-data scope. Application filters are retained for your return.</p>';
    if (report.state==='unavailable' || report.state==='failed') return html+`<p class="error">${escape(report.reason)} Use Refresh records to retry, or open another report.</p>`;
    html+=`<p class="interpretation">${escape(report.caveat)}</p>`;
    if (report.state==='empty') html+='<p class="empty">No matching records. This is an empty selection, not a load failure.</p>';
    if (report.coverage) html+=`<details open><summary>Coverage and diagnostics</summary><dl class="coverage">${Object.entries(report.coverage).map(([k,v])=>`<div><dt>${escape(k.replaceAll('_',' '))}</dt><dd>${Array.isArray(v) ? v.length : escape(v)}</dd></div>`).join('')}</dl></details>`;
    if (name==='channel') html+=`<p>Known recorded source: ${report.known_source_count || 0}/${report.population_ids.length} applications. Unknown is a separate group.</p>`;
    let chart='';
    try { chart=name==='sankey' ? sankeyChart(report) : name==='cohorts' ? cohortHeatmap(report.groups,link) : name==='stages' ? stageChart(report.groups) : name==='skills' ? skillMatrix(report.groups,link) : barChart(report.groups,['channel','targeting'].includes(name)); }
    catch (_) {chart='<p>Visualization unavailable. Read the evidence table below.</p>';}
    html+=chart;
    html+=evidenceTable(name,report.groups,'Recorded groups and exact evidence',link,['channel','targeting','cohorts'].includes(name));
    if (name==='cohorts') html+=`<p>Unknown applied date: ${(report.unknown_date_ids || []).length}. Cohorts with interval anomalies have unavailable timed rates.</p>`;
    if (name==='stages') html+=evidenceTable(name,report.rejections || [],'Rejection by highest prior recorded interview · no inferred visits',link);
    if (name==='targeting' || name==='channel') html+=`<h3>Fully observed 30-day comparison subset</h3><p>Same application scope; only valid dates with at least 30 recorded days of follow-up and non-anomalous interview intervals. These are the exact populations tested by the brief.</p>${evidenceTable(name,report.comparisons || [],'30-day interview attainment',link,true)}`;
    if (name==='targeting') html+=`<h3>Latest descriptive assessments · timing separated</h3>${evidenceTable(name,report.descriptive || [],'Descriptive fit; not a pre-outcome recommendation',link,true)}`;
    if (name==='skills') html+=`<h3>Normalized requirements</h3>${skillMatrix(report.requirements || [],link)}${evidenceTable(name,report.requirements || [],'Raw requirement variants and exact assessed applications',link)}`;
    if (name==='sankey') html+=table('Transition occurrence counts versus distinct contributors',['Recorded transition','Occurrences','Distinct applications','Inspect'],report.groups.map(g=>[escape(g.label),String(g.occurrences),String(g.denominator),link(name,g.key,'Contributors')]))+evidenceTable(name,report.current || [],'Current-status counts · not flows',link);
    if (name==='inventory') {
      html+=`<h3>Collection freshness</h3><p>Last completed collection: ${escape(report.last_completed_at)} · elapsed recorded days: ${report.freshness_days == null ? 'unavailable' : report.freshness_days.toFixed(1)}. ${(report.older_than_30_days_ids || []).length} postings older than 30 days; ${(report.unknown_freshness_ids || []).length} with unknown freshness. Runs ${report.runs_available ? 'available' : 'unavailable'}.</p>`;
      try {html+=salaryChart(report.salary_groups || []);} catch (_) {html+='<p>Salary visualization unavailable; inspect units and ranges in evidence.</p>';}
      html+=evidenceTable(name,report.salary_groups || [],'Captured salary units · incomplete groups are non-comparable',link);
      html+=table('Recorded discovery runs and errors',['Run','Status','Started / completed','Recorded errors'],(report.runs || []).map(r=>[String(r.id),escape(r.status),escape(r.started_at)+' / '+escape(r.completed_at),escape(r.errors_state)+'<pre>'+escape(JSON.stringify(r.errors,null,2))+'</pre>']));
    }
    return html;
  }
  const api = {createStore, scopeFromURL, routeFromURL, routeURL, allGroups, escape, safeURL, reportNames, presentation};
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
    const bundle = state.bundle;
    if (bundle && !state.loading) {
      const acceptedURL = new URL(location.href);
      for (const key of scopeKeys) {
        if (bundle.scope[key]) acceptedURL.searchParams.set(key,bundle.scope[key]);
        else acceptedURL.searchParams.delete(key);
      }
      history.replaceState(null,'',acceptedURL);
    }
    const route = routeFromURL(new URL(location.href));
    $('navigation').innerHTML = Object.entries(reportNames).map(([key, name]) => `<a ${key === route.report ? 'aria-current="page"' : ''} href="${escape(routeURL(location.href,key))}">${name}</a>`).join('');
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
    $('content').innerHTML = presentation(bundle, route, link);
    renderEvidence(bundle, route);
    if (route.group && !changedSnapshot) $('evidence-heading')?.focus();
  }
  function findGroup(bundle, route) {
    if (route.report === 'overview' && route.group === 'never-applied') return {label:'Never applied · excluded from outcome denominators', ids:bundle.never_applied_ids};
    if (route.report === 'overview' && route.group === 'unknown-date') return {label:'Unknown applied date · excluded by date range', ids:bundle.unknown_date_excluded_ids};
    return allGroups(bundle.reports[route.report] || {}).find(g => g.key === route.group);
  }
  function renderEvidence(bundle, route) {
    const selected = findGroup(bundle, route), region = $('evidence');
    region.hidden = !selected;
    if (!selected) {region.innerHTML = ''; return;}
    const ids = route.subset === 'numerator' ? selected.numerator_ids || [] : route.subset === 'gap' ? selected.gap_ids || [] :
      route.subset.startsWith('evidence:') ? selected.evidence?.[route.subset.slice(9)] || [] : selected.ids;
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
    else store.restoreAccepted();
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    const url = new URL(location.href);
    for (const key of scopeKeys) { const value = form.elements.namedItem(key).value; if (value) url.searchParams.set(key,value); else url.searchParams.delete(key); }
    history.pushState(null,'',url); store.load(scopeFromURL(url));
  });
  $('refresh').onclick = () => store.load(scopeFromURL(new URL(location.href)));
  addEventListener('hashchange',render); addEventListener('popstate',navigate);
  navigate();
})(typeof globalThis !== 'undefined' ? globalThis : this);
