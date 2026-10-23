from pathlib import Path
import shutil
import subprocess


def run_node(script):
    node = shutil.which('node')
    assert node, 'Node is required: reporting browser checks must not skip'
    result = subprocess.run([node, '-e', script, str(Path('static/reports.js').resolve())], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


FRONTEND_HARNESS = r"""
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const A = {start:'',end:'',profile:'',source:''}, B = {...A,profile:'it'};
const bundle = (scope,id) => ({scope,snapshot_id:id,retrieved_at:'synthetic',selected_ids:[],
  never_applied_ids:[],unknown_date_excluded_ids:[],filter_options:{profile:['it'],source:[]},
  reports:{sankey:{groups:[],current:[],nodes:[],links:[]}},brief:{message:'Insufficient data',leads:[],reasons:[]}});
const elements = {}, events = {}, requests = [];
const element = id => elements[id] ||= {innerHTML:'',textContent:'',hidden:false,value:'',
  addEventListener(t,f){this[t]=f},append(){},focus(){}};
const fields = Object.fromEntries(['start','end','profile','source'].map(k=>[k,element(k)]));
element('filters').elements = {namedItem:k=>fields[k]};
const ctx = {URL,URLSearchParams,console,document:{getElementById:element,createTextNode:t=>t},
  location:new URL('http://local/reports'),
  history:{replaceState(_,__,url){ctx.location=new URL(url)},pushState(_,__,url){ctx.location=new URL(url)}},
  addEventListener:(t,f)=>events[t]=f,fetch:url=>new Promise(resolve=>requests.push({url,resolve}))};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
const tick = () => new Promise(resolve=>setImmediate(resolve));
const respond = (request,data,ok=true) => request.resolve({ok,json:async()=>data});
const submitB = () => {fields.profile.value='it';elements.filters.submit({preventDefault(){}})};
"""


def test_frontend_retry_restores_accepted_scope_before_links_and_refresh():
    run_node(FRONTEND_HARNESS + r"""
    (async()=>{
      respond(requests[0],bundle(A,'A')); await tick();
      submitB();
      respond(requests[1],{detail:'Synthetic failure'},false); await tick();
      assert.equal(ctx.location.search,'');
      assert.match(elements.scope.textContent,/profile all/);
      elements.retry.onclick();
      assert.equal(new URL(requests[2].url,'http://local').searchParams.get('profile'),'it');
      respond(requests[2],bundle(B,'B-retry')); await tick();
      assert.equal(ctx.location.search,'?profile=it');
      assert.match(elements.scope.textContent,/profile it/);
      for (const id of ['navigation','content']) {
        const links = [...elements[id].innerHTML.matchAll(/href="([^"]+)"/g)];
        assert.ok(links.length);
        for (const [,href] of links) assert.equal(new URL(href.replaceAll('&amp;','&')).searchParams.get('profile'),'it');
      }
      elements.refresh.onclick();
      assert.equal(new URL(requests[3].url,'http://local').searchParams.get('profile'),'it');
    })().catch(e=>{console.error(e);process.exitCode=1});
    """)


def test_frontend_back_to_accepted_scope_invalidates_pending_fetch():
    run_node(FRONTEND_HARNESS + r"""
    (async()=>{
      respond(requests[0],bundle(A,'A')); await tick();
      submitB();
      ctx.location = new URL('http://local/reports'); events.popstate();
      assert.equal(requests.length,2);
      assert.equal(elements['load-state'].innerHTML,'');
      assert.match(elements.scope.textContent,/profile all/);
      assert.doesNotMatch(elements.scope.textContent,/STALE/);
      respond(requests[1],bundle(B,'B-abandoned')); await tick();
      assert.equal(ctx.location.search,'');
      assert.match(elements.scope.textContent,/profile all/);
      assert.equal(fields.profile.value,'');
      elements.refresh.onclick();
      assert.equal(new URL(requests[2].url,'http://local').searchParams.get('profile'),'');
    })().catch(e=>{console.error(e);process.exitCode=1});
    """)


def test_atomic_accept_race_failure_retry_and_url_scope():
    run_node(r"""
    const assert = require('node:assert/strict');
    const {createStore, scopeFromURL, routeFromURL, routeURL} = require(process.argv[1]);
    const pending = [];
    const store = createStore(url => new Promise(resolve => pending.push({url, resolve})));
    const bundle = (scope, id) => ({scope, snapshot_id:id, reports:{channel:{groups:[]}}, applications:{}});
    const a = {start:'',end:'',profile:'it',source:''};
    const b = {...a,source:'recruiter'};
    (async () => {
      const first = store.load(a); const second = store.load(b);
      pending[1].resolve({ok:true,json:async()=>bundle(b,'new')}); await second;
      pending[0].resolve({ok:true,json:async()=>bundle(a,'old')}); await first;
      assert.equal(store.state.bundle.snapshot_id,'new');
      const failure = store.load(a);
      assert.equal(store.state.stale,true);
      pending[2].resolve({ok:false,json:async()=>({detail:'Failed load'})}); await failure;
      assert.equal(store.state.bundle.snapshot_id,'new');
      assert.deepEqual(store.state.bundle.scope,b);
      assert.match(store.state.error,/Failed load/);
      const retry = store.load(a);
      pending[3].resolve({ok:true,json:async()=>bundle(a,'retry')}); await retry;
      assert.equal(store.state.stale,false);
      const url = new URL('http://local/reports?profile=it&source=recruiter#inventory');
      assert.deepEqual(scopeFromURL(url),b);
      assert.equal(routeFromURL(url).report,'inventory');
      const back = new URL(routeURL(url,'channel','exact key'));
      assert.equal(back.search,url.search);
      assert.equal(routeFromURL(back).group,'exact key');
    })().catch(e=>{console.error(e);process.exitCode=1});
    """)
