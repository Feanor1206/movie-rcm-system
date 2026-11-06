"""Offline F02 production source probes; no model, DB, Spring server, network or media."""
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


def java_probe():
    base=ROOT/'backend/springboot'
    src=base/'src/main/java/com/dippie/moviercm'
    cp=os.pathsep.join([str(base/'target/classes')]+[str(p) for p in sorted((Path.home()/'.m2/repository').rglob('*.jar'))])
    sources=[]
    for folder in ['dto/catalog','entity/catalog','repository/catalog','service/catalog']:
        sources+=list((src/folder).glob('*.java'))
    sources += [src/'config/StorageKeyConfig.java',src/'exception/CatalogConflictException.java',
                Path(__file__).with_name('CATALOG_01_F02_Probe.java')]
    with tempfile.TemporaryDirectory(prefix='catalog-f02-java-') as temp:
        args=['-proc:none','-encoding','UTF-8','-cp',cp,'-d',temp]+list(map(str,sources))
        argfile=Path(temp)/'javac.args'
        argfile.write_text('\n'.join('"'+s.replace('\\','/')+'"' for s in args),encoding='utf-8')
        result=subprocess.run(['javac','@'+str(argfile)],capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stderr)
        result=subprocess.run(['java','-cp',temp+os.pathsep+cp,'CATALOG_01_F02_Probe',temp],
                              capture_output=True,text=True,encoding='utf-8',check=True)
        return json.loads(result.stdout.strip())


def sync_race():
    spec=importlib.util.spec_from_file_location('f02_sync',ROOT/'backend/fastapi/services/catalog_sync.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    manager=module.CatalogSyncManager()
    template=json.loads((ROOT/'docs/contracts/animation-catalog-v1/catalog.example.json').read_text(encoding='utf-8'))
    for col in ['series','seasons','episodes','segments','characters','media_assets','text_tracks','scenes']:
        for row in template[col]:
            row['record']['status']='ready'
            row['record']['provenance']['verification']='human_verified'
    for row in template['media_assets']:row['access_policy']='public'
    payloads={}
    for name in ['older','newer']:
        def rename(x):
            if isinstance(x,dict):return {k:rename(v) for k,v in x.items()}
            if isinstance(x,list):return [rename(v) for v in x]
            if isinstance(x,str) and x.endswith('_demo'):return x+'_'+name
            return x
        payloads[name]=rename(copy.deepcopy(template))
        payloads[name]['series'][0]['title']=name
    entered=threading.Event();release=threading.Event()
    original=manager.load_from_payload
    def delayed(payload,**kwargs):
        if payload['series'][0]['title']=='older':
            entered.set()
            if not release.wait(10):raise TimeoutError('probe coordination')
        return original(payload,**kwargs)
    manager.load_from_payload=delayed
    index=SimpleNamespace(build_from_catalog=lambda *a,**k:None)
    node=next(n for n in ast.parse((ROOT/'backend/fastapi/main.py').read_text(encoding='utf-8')).body
              if isinstance(n,ast.FunctionDef) and n.name=='sync_index')
    node.decorator_list=[];node.returns=None
    for argument in node.args.args:argument.annotation=None
    class ProbeHTTPError(Exception):
        def __init__(self,**kwargs):super().__init__(str(kwargs))
    namespace={'FASTAPI_SYNC_SECRET':'fixture-only-local-token','_current_sync_generation':0,
               'HTTPException':ProbeHTTPError,'IndexSyncResponse':lambda **k:SimpleNamespace(**k),
               'catalog_sync_manager':manager,'logger':logging.getLogger('f02-probe'),
               'cascading_pipeline':SimpleNamespace(retrieval_node=SimpleNamespace(hybrid_index=index))}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'production-sync_index','exec'),namespace)
    request=SimpleNamespace(headers={'X-Service-Token':'fixture-only-local-token'})
    errors=[]
    def older():
        try:namespace['sync_index'](request,SimpleNamespace(generation=1,catalog=payloads['older']))
        except Exception as exc:errors.append(str(exc))
    thread=threading.Thread(target=older);thread.start()
    if not entered.wait(10):raise TimeoutError('older sync did not enter')
    namespace['sync_index'](request,SimpleNamespace(generation=2,catalog=payloads['newer']))
    release.set();thread.join(10)
    if thread.is_alive() or errors:raise RuntimeError(errors or 'probe thread incomplete')
    return {'generation_after_both':namespace['_current_sync_generation'],
            'final_series_titles':[x['title'] for x in manager.get_flattened_catalog() if x['item_type']=='series'],
            'expected_series_title':'newer',
            'scope':'unmodified production sync function AST; real CatalogSyncManager; fake encoder/index and local auth request; no HTTP/model'}


def rebuild_probe():
    spec=importlib.util.spec_from_file_location('f02_hybrid',ROOT/'backend/fastapi/services/hybrid_retrieval.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    index=module.HybridMovieIndex()
    index.encoder=SimpleNamespace(encode_documents=lambda texts:[[1.0] for _ in texts])
    index.build_from_catalog([{'id':'removed_A','title':'removed text'}],save_to_disk=False)
    index.build_from_catalog([{'id':'current_B','title':'current text'}],save_to_disk=False)
    after_replace=sorted(index.documents)
    index.build_from_catalog([],save_to_disk=False)
    return {'documents_after_replace':after_replace,'documents_after_empty':sorted(index.documents),
            'expected_after_replace':['current_B'],'expected_after_empty':[],
            'scope':'production HybridMovieIndex with fake encoder, no disk/model/network'}


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    result={'java':java_probe(),'sync_race':sync_race(),'index_rebuild':rebuild_probe()}
    rendered=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    (ROOT/'docs/reviews/evidence/CATALOG_01_F02_probe.json').write_text(rendered,encoding='utf-8')
    print(rendered)
