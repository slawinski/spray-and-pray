from test_reporting_browser_state import run_node


def test_semantic_tables_charts_states_and_safe_text():
    run_node(r"""
    const assert = require('node:assert/strict');
    const ui = require(process.argv[1]);
    const group = {key:'g',label:'<script>stored</script>',ids:[1],denominator:1,numerator:0,numerator_ids:[],rate:0};
    const names = ['channel','cohorts','stages','targeting','skills','aging','inventory','sankey'];
    const reports = Object.fromEntries(names.map(n=>[n,{title:n,state:'ready',groups:[group],population_ids:[1],caveat:'Recorded evidence'}]));
    reports.sankey.nodes=[]; reports.sankey.links=[];
    const bundle = {reports,selected_ids:[1],never_applied_ids:[],unknown_date_excluded_ids:[],brief:{message:'Insufficient data',leads:[],reasons:[]}};
    const link=(r,g,t)=>`<a href="#${r}/${encodeURIComponent(g)}">${ui.escape(t)}</a>`;
    for (const report of names) {
      const html = ui.presentation(bundle,{report},link);
      assert.match(html,/<caption>/); assert.match(html,/<th/);
      assert.ok(!html.includes('<script>stored</script>'));
      assert.match(html,/&lt;script&gt;/);
    }
    assert.match(ui.presentation(bundle,{report:'channel'},link),/0\/1/);
    assert.match(ui.presentation(bundle,{report:'overview'},link),/Where to focus next/);
    reports.channel.state='unavailable'; reports.channel.reason='Missing table';
    assert.match(ui.presentation(bundle,{report:'channel'},link),/Missing table/);
    assert.equal(ui.safeURL('javascript:alert(1)'),null);
    assert.equal(ui.safeURL('https://example.com/'),'https://example.com/');
    assert.match(ui.presentation(bundle,{report:'inventory'},link),/independent/i);
    """)
