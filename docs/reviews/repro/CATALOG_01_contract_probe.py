"""Offline contract probes; no DB, service, model, network, mount or media access.

Requires installed Python jsonschema and locally cached Java Jackson/Spring jars.
Build outputs and JSON mutations live only in a fresh system temp directory.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    contract = module('contract', 'docs/contracts/animation-catalog-v1/validate_catalog.py')
    sync = module('sync_probe', 'backend/fastapi/services/catalog_sync.py')
    data = json.loads((ROOT / 'docs/contracts/animation-catalog-v1/catalog.example.json').read_text(encoding='utf-8'))
    cases = {'official_example': data}
    for name, change in [
        ('missing_episode_title', lambda d: d['episodes'][0].pop('title')),
        ('unknown_nested_field', lambda d: d['series'][0].update({'not_in_contract': True})),
        ('invalid_package_revision', lambda d: d['package'].update({'revision': 'bad'})),
        ('wrong_enabled_type', lambda d: d['media_assets'][0].update({'enabled': 'false'})),
        ('unknown_provider', lambda d: d['media_assets'][0]['storage'].update({'provider': 'ftp'})),
    ]:
        mutated = copy.deepcopy(data)
        change(mutated)
        cases[name] = mutated
    m2 = Path.home() / '.m2/repository'
    jars = [
        m2 / f'com/fasterxml/jackson/core/{name}/2.17.2/{name}-2.17.2.jar'
        for name in ['jackson-core', 'jackson-annotations', 'jackson-databind']
    ] + [m2 / 'org/springframework/spring-context/6.1.12/spring-context-6.1.12.jar']
    for jar in jars:
        if not jar.is_file():
            raise FileNotFoundError(jar)
    production = ROOT / 'backend/springboot/src/main/java/com/dippie/moviercm'
    with tempfile.TemporaryDirectory(prefix='catalog01-contract-review-') as temp:
        directory = Path(temp)
        classpath = os.pathsep.join(map(str, jars))
        subprocess.run(['javac', '-encoding', 'UTF-8', '-cp', classpath, '-d', temp,
                        str(production / 'dto/catalog/CatalogValidationError.java'),
                        str(production / 'service/catalog/CatalogValidator.java'),
                        str(Path(__file__).with_name('CATALOG_01_ValidatorProbe.java'))], check=True, capture_output=True, text=True)
        inputs = []
        for name, payload in cases.items():
            path = directory / (name + '.json')
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            inputs.append(str(path))
        output = subprocess.run(['java', '-cp', temp + os.pathsep + classpath,
                                 'CATALOG_01_ValidatorProbe', *inputs], check=True, capture_output=True, text=True, encoding='utf-8')
        actual = {row['case'].removesuffix('.json'): row['errors']
                  for row in map(json.loads, output.stdout.splitlines())}
    results = {'validator': []}
    for name, payload in cases.items():
        expected = contract.validate(payload)
        results['validator'].append({'case': name, 'contract_error_count': len(expected),
                                     'production_error_count': len(actual[name]),
                                     'production_errors': actual[name]})
    results['flattening'] = []
    for name in ['character_alias_object', 'unknown_segment_times']:
        payload = copy.deepcopy(data)
        if name == 'character_alias_object':
            payload['characters'][0]['aliases'] = [{'text': 'ProbeAlias', 'language': 'vi', 'kind': 'alternate'}]
        else:
            payload['segments'][0]['episode_start_ms'] = None
            payload['segments'][0]['episode_end_ms'] = None
        expected = contract.validate(payload)
        try:
            counts = sync.CatalogSyncManager().load_from_payload(payload)
            outcome = {'counts': counts}
        except Exception as exc:
            outcome = {'exception': type(exc).__name__, 'message': str(exc)}
        results['flattening'].append({'case': name, 'contract_error_count': len(expected), **outcome})
    results['source_sha256'] = {
        str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [production / 'service/catalog/CatalogValidator.java', ROOT / 'backend/fastapi/services/catalog_sync.py']
    }
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
