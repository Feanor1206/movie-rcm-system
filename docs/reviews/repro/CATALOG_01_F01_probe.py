"""F01 offline checks: production validator and catalog flattening only.

No Spring server, database, GPU, encoder, network or Drive access.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]


def load_module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    contract = load_module('contract_f01', 'docs/contracts/animation-catalog-v1/validate_catalog.py')
    sync = load_module('sync_f01', 'backend/fastapi/services/catalog_sync.py')
    example = json.loads((ROOT / 'docs/contracts/animation-catalog-v1/catalog.example.json').read_text(encoding='utf-8'))
    cases = {}
    for name, change in [
        ('invalid_release_date', lambda d: d['episodes'][0].update({'release_date': '2026-99-99'})),
        ('invalid_source_uri', lambda d: d['sources'][0].update({'url': 'not a uri'})),
        ('zero_rating_scale', lambda d: d['episodes'][0].update({'ratings': [{
            'value': 0, 'scale_max': 0, 'vote_count': None,
            'source_id': d['sources'][0]['id'], 'retrieved_at': None}]})),
    ]:
        payload = copy.deepcopy(example)
        change(payload)
        cases[name] = payload
    m2 = Path.home() / '.m2/repository'
    jars = [m2 / f'com/fasterxml/jackson/core/{n}/2.17.2/{n}-2.17.2.jar'
            for n in ['jackson-core', 'jackson-annotations', 'jackson-databind']]
    jars += [m2 / 'org/springframework/spring-context/6.1.12/spring-context-6.1.12.jar']
    production = ROOT / 'backend/springboot/src/main/java/com/dippie/moviercm'
    with tempfile.TemporaryDirectory(prefix='catalog-f01-review-') as directory:
        cp = os.pathsep.join(map(str, jars))
        subprocess.run(['javac', '-encoding', 'UTF-8', '-cp', cp, '-d', directory,
                        str(production / 'dto/catalog/CatalogValidationError.java'),
                        str(production / 'service/catalog/CatalogValidator.java'),
                        str(Path(__file__).with_name('CATALOG_01_ValidatorProbe.java'))],
                       check=True, capture_output=True, text=True)
        paths = []
        for name, payload in cases.items():
            file = Path(directory) / (name + '.json')
            file.write_text(json.dumps(payload), encoding='utf-8')
            paths.append(str(file))
        output = subprocess.run(['java', '-cp', directory + os.pathsep + cp,
                                 'CATALOG_01_ValidatorProbe', *paths],
                                check=True, capture_output=True, text=True, encoding='utf-8')
        actual = {row['case'].removesuffix('.json'): row['errors']
                  for row in map(json.loads, output.stdout.splitlines())}
    results = {'validation': [{'case': name,
                              'contract_errors': contract.validate(payload),
                              'production_errors': actual[name]}
                             for name, payload in cases.items()]}
    manager = sync.CatalogSyncManager()
    counts = manager.load_from_payload(example)
    results['runtime_default_publication'] = {
        'input_contract_errors': contract.validate(example),
        'input_series_status': example['series'][0]['record']['status'],
        'input_asset_policy': example['media_assets'][0]['access_policy'],
        'indexed_counts': counts,
        'indexed_ids': [item['id'] for item in manager.get_flattened_catalog()],
        'scene_asset_id': manager.get_item_by_id(example['scenes'][0]['id']).get('media_asset_id'),
        'scope': 'direct production load_from_payload call using runtime defaults; no HTTP/model',
    }
    rendered = json.dumps(results, ensure_ascii=False, indent=2) + '\n'
    destination = ROOT / 'docs/reviews/evidence/CATALOG_01_F01_probe.json'
    destination.write_text(rendered, encoding='utf-8')
    print(rendered)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
