import pytest

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


@pytest.mark.parametrize('aligned_outcomes', [False, True])
def test_sankey_routes_shared_outcomes_without_crossing_flows(aligned_outcomes):
    run_node(r"""
    const assert = require('node:assert/strict'), ui = require(process.argv[1]);
    const nodeData = ALIGNED_OUTCOMES
      ? [[0,'applied',184],[1,'interview 1',14],[2,'interview 2',8],[3,'interview 3',1],
         [4,'No recorded outcome',131],[4,'withdrawn',3],[4,'rejected',45]]
      : [[0,'applied',184],[1,'waiting',131],[1,'interview 1',14],[1,'withdrawn',1],
         [2,'interview 2',8],[3,'interview 3',1],[3,'withdrawn',2],[4,'rejected',45]];
    const nodes = nodeData
      .map(([position,label,count])=>({key:position+':'+label,position,label,count}));
    const linkData = ALIGNED_OUTCOMES
      ? [[0,1,14],[0,4,131],[0,5,1],[0,6,38],[1,2,8],
         [1,6,2],[2,3,1],[2,5,2],[2,6,4],[3,6,1]]
      : [[0,1,131],[0,2,14],[0,3,1],[0,7,38],[2,4,8],
         [2,7,2],[4,5,1],[4,6,2],[4,7,4],[5,7,1]];
    const links = linkData
      .map(([a,b,count])=>({source:nodes[a].key,target:nodes[b].key,count}));
    const report = {title:'Paths',state:'ready',groups:[],current:[],nodes,links};
    const html = ui.presentation({reports:{sankey:report}},{report:'sankey'},()=> '');
    const paths = [...html.matchAll(/<path d="([^"]+)" stroke-width="([^"]+)"/g)];
    assert.equal(paths.length,links.length);
    // Sample the rendered cubic curves, including each bypass segment of long links.
    const curves = paths.map(([,d,width])=>{
      const points = []; let start;
      for (const [,command,args] of d.matchAll(/([MCL])\s*([^MCL]+)/g)) {
        const v = args.trim().split(/[\s,]+/).map(Number);
        if (command === 'M') {start=v; points.push(v); continue;}
        const end = v.slice(-2);
        for (let i=1;i<=100;i++) {
          const t=i/100, u=1-t;
          points.push(command === 'L' ? start.map((s,j)=>s*u+end[j]*t)
            : start.map((s,j)=>s*u*u*u+3*v[j]*u*u*t+3*v[j+2]*u*t*t+end[j]*t*t*t));
        }
        start=end;
      }
      assert.ok(points.every(p=>p.every(Number.isFinite)));
      return {points,width:Number(width)};
    });
    function yAt(points,x) {
      const i=points.findIndex(p=>p[0]>=x);
      if (i===0) return points[0][1];
      const [a,b]=[points[i-1],points[i]], t=(x-a[0])/(b[0]-a[0]);
      return a[1]+(b[1]-a[1])*t;
    }
    for(let i=0;i<curves.length;i++) for(let j=i+1;j<curves.length;j++) {
      const a=curves[i], b=curves[j];
      const left=Math.max(a.points[0][0],b.points[0][0]);
      const right=Math.min(a.points.at(-1)[0],b.points.at(-1)[0]);
      if(right<=left) continue;
      const distances=Array.from({length:101},(_,n)=>{
        const x=left+(right-left)*n/100;
        return yAt(a.points,x)-yAt(b.points,x);
      });
      assert.ok(distances.every(d=>d>=-1e-6) || distances.every(d=>d<=1e-6),
        `Flows ${i} and ${j} cross`);
      assert.ok(distances.every(d=>Math.abs(d)+.02>=(a.width+b.width)/2),
        `Flows ${i} and ${j} overlap`);
    }
    assert.equal((html.match(/<rect /g)||[]).length,nodes.length,'Bypasses are not visible nodes');
    const captions = [...html.matchAll(/<text [^>]*>(.*?)<\/text>/g)];
    assert.deepEqual(captions.map(m=>m[1].replace(/<\/tspan>/g,' ').replace(/<[^>]+>/g,'').replace(/\s+/g,' ').trim()),
      nodes.map(n=>`${n.label} (${n.count})`));
    if(ALIGNED_OUTCOMES) {
      const rects = [...html.matchAll(/<rect x="([^"]+)"/g)].map(m=>Number(m[1]));
      assert.ok(rects.slice(-3).every(x=>x===Math.max(...rects)),'Final outcomes align right');
      assert.ok(captions.slice(-3).every(m=>m[0].includes('text-anchor="end"')),'Outcome captions extend inward');
    }
    """.replace('ALIGNED_OUTCOMES', 'true' if aligned_outcomes else 'false'))
