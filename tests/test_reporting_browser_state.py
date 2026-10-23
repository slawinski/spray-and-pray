from pathlib import Path
import shutil
import subprocess


def run_node(script):
    node = shutil.which('node')
    assert node, 'Node is required: reporting browser checks must not skip'
    result = subprocess.run([node, '-e', script, str(Path('static/reports.js').resolve())], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


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
