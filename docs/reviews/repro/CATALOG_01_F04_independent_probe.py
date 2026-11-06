"""Offline F04 regression probes. Never runs the handoff runtime-state writer.

No main.py import, live server/DB, model/GPU, network or runtime file mutation.
"""
import ast
import copy
import importlib.util
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[3]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def grant_probe():
    base=ROOT/'backend/springboot';src=base/'src/main/java/com/dippie/moviercm'
    cp=os.pathsep.join([str(base/'target/classes')]+[str(p) for p in sorted((Path.home()/'.m2/repository').rglob('*.jar'))])
    with tempfile.TemporaryDirectory(prefix='catalog-f04-grant-review-') as temp:
        sources=[src/'security/JwtUtils.java',src/'security/JwtAuthenticationFilter.java',Path(__file__).with_name('CATALOG_01_F04_GrantProbe.java')]
        args=['-proc:none','-encoding','UTF-8','-cp',cp,'-d',temp]+list(map(str,sources))
        argfile=Path(temp)/'javac.args';argfile.write_text('\n'.join('"'+s.replace('\\','/')+'"' for s in args),encoding='utf-8')
        result=subprocess.run(['javac','@'+str(argfile)],capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stderr)
        result=subprocess.run(['java','-cp',temp+os.pathsep+cp,'CATALOG_01_F04_GrantProbe'],capture_output=True,text=True,encoding='utf-8',check=True)
        return json.loads(next(line for line in reversed(result.stdout.splitlines()) if line.startswith('{')))


def sync_failure_probe(sync,payload):
    manager=sync.CatalogSyncManager()
    class IndexFixture:
        def __init__(self):self.titles=[]
        def build_from_catalog(self,items,**kwargs):self.titles=[r['title'] for r in items if r['item_type']=='series']
    index=IndexFixture()
    node=next(n for n in ast.parse((ROOT/'backend/fastapi/main.py').read_text(encoding='utf-8')).body
              if isinstance(n,ast.FunctionDef) and n.name=='sync_index')
    node.decorator_list=[];node.returns=None
    for arg in node.args.args:arg.annotation=None
    class ProbeHTTPError(Exception):
        def __init__(self,status_code,detail):self.status_code=status_code;self.detail=detail
    ns={'FASTAPI_SYNC_SECRET':'local-fixture-only','_current_sync_generation':0,'_current_sync_hash':'',
        '_active_catalog_payload':None,'_publish_lock':threading.Lock(),'HTTPException':ProbeHTTPError,
        'IndexSyncResponse':lambda **kwargs:SimpleNamespace(**kwargs),'catalog_sync_manager':manager,
        'logger':logging.getLogger('f04-review'),'cascading_pipeline':SimpleNamespace(retrieval_node=SimpleNamespace(hybrid_index=index))}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'production-sync-index','exec'),ns)
    request=SimpleNamespace(headers={'X-Service-Token':'local-fixture-only'})
    def call(gen,payload):
        try:return vars(ns['sync_index'](request,SimpleNamespace(generation=gen,catalog=payload,content_hash=sync.CatalogSyncManager.compute_hash(payload))))
        except ProbeHTTPError as exc:return {'http_status':exc.status_code}
    accepted=copy.deepcopy(payload);accepted['series'][0]['title']='accepted-A'
    rejected=copy.deepcopy(payload);rejected['series'][0]['title']='failed-durable-B'
    first=call(1,accepted)
    def fail_save(*args):raise OSError('fixture durable storage failure')
    ns['_save_sync_state']=fail_save
    failure=call(2,rejected)
    return {'first_status':first.get('status'),'failed_sync':failure,
            'active_generation':ns['_current_sync_generation'],
            'catalog_titles':[r['title'] for r in manager.get_flattened_catalog() if r['item_type']=='series'],
            'index_titles':index.titles,'expected_both':['accepted-A'],
            'scope':'production sync AST and real manager; fake index/save failure, no HTTP/disk/model'}


def main():
    sync=module('sync_f04_independent','backend/fastapi/services/catalog_sync.py')
    previous=module('hash_f04_independent','docs/reviews/repro/CATALOG_01_F03_probe.py')
    payload=json.loads((ROOT/'docs/contracts/animation-catalog-v1/catalog.example.json').read_text(encoding='utf-8'))
    for col in ['series','seasons','episodes','segments','characters','media_assets','text_tracks','scenes']:
        for row in payload[col]:
            row['record']['status']='ready';row['record']['provenance']['verification']='human_verified'
    for row in payload['media_assets']:row['access_policy']='public'
    payload['series'][0]['record']['provenance']['confidence']=1e-8
    contract=module('contract_f04_independent','docs/contracts/animation-catalog-v1/validate_catalog.py')
    java_hash=previous.worker_hash(payload);python_hash=sync.CatalogSyncManager.compute_hash(payload)
    result={'playback_grant':grant_probe(),
            'numeric_hash':{'confidence':1e-8,'contract_errors':contract.validate(payload),
                            'java_hash':java_hash,'python_hash':python_hash,'match':java_hash==python_hash},
            'durable_failure':sync_failure_probe(sync,payload)}
    rendered=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    (ROOT/'docs/reviews/evidence/CATALOG_01_F04_independent_probe.json').write_text(rendered,encoding='utf-8');print(rendered)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
