"""F03 offline source probes: actual Java worker hash and Python sync function.

No DB/server, HTTP, model/encoder, GPU or Drive. Does not import FastAPI main.
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


def worker_hash(payload):
    base=ROOT/'backend/springboot';src=base/'src/main/java/com/dippie/moviercm'
    cp=os.pathsep.join([str(base/'target/classes')]+[str(p) for p in sorted((Path.home()/'.m2/repository').rglob('*.jar'))])
    sources=[]
    for folder in ['dto/catalog','entity/catalog','repository/catalog','service/catalog']:
        sources+=list((src/folder).glob('*.java'))
    sources += [src/'config/StorageKeyConfig.java',src/'exception/CatalogConflictException.java',
                Path(__file__).with_name('CATALOG_01_F03_HashProbe.java')]
    with tempfile.TemporaryDirectory(prefix='catalog-f03-hash-') as temp:
        args=['-proc:none','-encoding','UTF-8','-cp',cp,'-d',temp]+list(map(str,sources))
        argfile=Path(temp)/'javac.args'
        argfile.write_text('\n'.join('"'+s.replace('\\','/')+'"' for s in args),encoding='utf-8')
        compiled=subprocess.run(['javac','@'+str(argfile)],capture_output=True,text=True)
        if compiled.returncode:raise RuntimeError(compiled.stderr)
        path=Path(temp)/'payload.json';path.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
        result=subprocess.run(['java','-cp',temp+os.pathsep+cp,'CATALOG_01_F03_HashProbe',str(path)],
                              capture_output=True,text=True,encoding='utf-8',check=True)
        return json.loads(result.stdout)['worker_hash']


def main():
    spec=importlib.util.spec_from_file_location('catalog_f03_sync',ROOT/'backend/fastapi/services/catalog_sync.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    payload=json.loads((ROOT/'docs/contracts/animation-catalog-v1/catalog.example.json').read_text(encoding='utf-8'))
    for col in ['series','seasons','episodes','segments','characters','media_assets','text_tracks','scenes']:
        for row in payload[col]:
            row['record']['status']='ready';row['record']['provenance']['verification']='human_verified'
    for row in payload['media_assets']:row['access_policy']='public'
    payload['series'][0]['title']='accepted-A'
    altered=copy.deepcopy(payload);altered['series'][0]['title']='rejected-B'
    java_hash=worker_hash(altered)
    manager=module.CatalogSyncManager()
    node=next(n for n in ast.parse((ROOT/'backend/fastapi/main.py').read_text(encoding='utf-8')).body
              if isinstance(n,ast.FunctionDef) and n.name=='sync_index')
    node.decorator_list=[];node.returns=None
    for argument in node.args.args:argument.annotation=None
    class ProbeHTTPError(Exception):
        def __init__(self,status_code,detail):self.status_code=status_code;self.detail=detail
    index=SimpleNamespace(build_from_catalog=lambda *a,**k:None)
    ns={'FASTAPI_SYNC_SECRET':'local-probe-only','_current_sync_generation':0,'_current_sync_hash':'',
        '_active_catalog_payload':None,'_publish_lock':threading.Lock(),
        'HTTPException':ProbeHTTPError,'IndexSyncResponse':lambda **k:SimpleNamespace(**k),
        'catalog_sync_manager':manager,'logger':logging.getLogger('f03-probe'),
        'cascading_pipeline':SimpleNamespace(retrieval_node=SimpleNamespace(hybrid_index=index))}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'production-sync-index','exec'),ns)
    request=SimpleNamespace(headers={'X-Service-Token':'local-probe-only'})
    def call(gen,catalog,declared_hash):
        try:return vars(ns['sync_index'](request,SimpleNamespace(generation=gen,catalog=catalog,content_hash=declared_hash)))
        except ProbeHTTPError as exc:return {'http_status':exc.status_code,'detail':exc.detail}
    accepted=call(1,payload,manager.compute_hash(payload))
    rejected=call(2,altered,java_hash)
    after_reject=[x['title'] for x in manager.get_flattened_catalog() if x['item_type']=='series']
    conflict=call(1,altered,manager.compute_hash(altered))
    after_conflict=[x['title'] for x in manager.get_flattened_catalog() if x['item_type']=='series']
    result={'hash_contract':{'java_worker_hash':java_hash,'python_receiver_hash':manager.compute_hash(altered),
                             'match':java_hash==manager.compute_hash(altered)},
            'baseline_status':accepted.get('status'),'worker_request':rejected,
            'after_rejected_request':{'generation':ns['_current_sync_generation'],'series_titles':after_reject,
                                      'expected':['accepted-A']},
            'same_generation_conflict':conflict,
            'after_conflict_series_titles':after_conflict,
            'scope':'current production Java hash and unmodified Python sync AST; fake encoder/index/request; no HTTP/model/DB'}
    rendered=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    (ROOT/'docs/reviews/evidence/CATALOG_01_F03_probe.json').write_text(rendered,encoding='utf-8');print(rendered)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
