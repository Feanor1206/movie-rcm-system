"""Independent F05 checks; no live DB/HTTP/model/GPU/Drive or runtime state writes."""
import ast
import copy
import importlib.util
import json
import logging
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[3]


def module(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/file)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def build_failure_probe():
    sync=module('f05_sync_independent','backend/fastapi/services/catalog_sync.py')
    payload=json.loads((ROOT/'docs/contracts/animation-catalog-v1/catalog.example.json').read_text(encoding='utf-8'))
    for col in ['series','seasons','episodes','segments','characters','media_assets','text_tracks','scenes']:
        for row in payload[col]:
            row['record']['status']='ready';row['record']['provenance']['verification']='human_verified'
    for row in payload['media_assets']:row['access_policy']='public'
    a=copy.deepcopy(payload);a['series'][0]['title']='accepted-A'
    b=copy.deepcopy(payload);b['series'][0]['title']='rejected-build-B'
    class IndexFixture:
        def __init__(self):self.fail=False;self.titles=[]
        def build_from_catalog(self,items,**kwargs):
            if self.fail:raise OSError('fixture index build failure')
            self.titles=[r['title'] for r in items if r['item_type']=='series']
    class ProbeHTTPError(Exception):
        def __init__(self,status_code,detail):self.status_code=status_code;self.detail=detail
    tree=ast.parse((ROOT/'backend/fastapi/main.py').read_text(encoding='utf-8'))
    nodes=[]
    for name in ['_save_sync_state','_load_sync_state','sync_index']:
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
        node.decorator_list=[];node.returns=None
        for arg in node.args.args:arg.annotation=None
        nodes.append(node)
    manager=sync.CatalogSyncManager();index=IndexFixture()
    with tempfile.TemporaryDirectory(prefix='catalog-f05-durable-review-') as temp:
        ns={'FASTAPI_SYNC_SECRET':'local-fixture-only','_current_sync_generation':0,'_current_sync_hash':'',
            '_active_catalog_payload':None,'_publish_lock':threading.Lock(),
            'HTTPException':ProbeHTTPError,'IndexSyncResponse':lambda **kwargs:SimpleNamespace(**kwargs),
            'catalog_sync_manager':manager,'logger':logging.getLogger('f05-review'),
            'cascading_pipeline':SimpleNamespace(retrieval_node=SimpleNamespace(hybrid_index=index)),
            'SYNC_STATE_PATH':Path(temp)/'state.json','json':json}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'production-sync-functions','exec'),ns)
        request=SimpleNamespace(headers={'X-Service-Token':'local-fixture-only'})
        def call(gen,data):
            try:return vars(ns['sync_index'](request,SimpleNamespace(generation=gen,catalog=data,content_hash=manager.compute_hash(data))))
            except ProbeHTTPError as exc:return {'http_status':exc.status_code}
        first=call(1,a);index.fail=True;failed=call(2,b)
        gen,chash,restored=ns['_load_sync_state']()
        fresh=sync.CatalogSyncManager();fresh.load_from_payload(restored,include_draft=False,include_private=False)
        return {'baseline_status':first.get('status'),'rejected_request':failed,
                'active_generation':ns['_current_sync_generation'],
                'active_catalog_titles':[r['title'] for r in manager.get_flattened_catalog() if r['item_type']=='series'],
                'active_index_titles':index.titles,'persisted_generation':gen,
                'restored_titles':[r['title'] for r in fresh.get_flattened_catalog() if r['item_type']=='series'],
                'expected_persisted_generation':1,'expected_restored_titles':['accepted-A'],
                'scope':'production sync/save/load AST, temp state, real manager, fake index failure; loader simulation, not service restart'}


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    old=module('f04_grant_probe_reused','docs/reviews/repro/CATALOG_01_F04_independent_probe.py')
    result={'grant_regression':old.grant_probe(),'index_build_failure':build_failure_probe()}
    rendered=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    (ROOT/'docs/reviews/evidence/CATALOG_01_F05_independent_probe.json').write_text(rendered,encoding='utf-8');print(rendered)
