"""Compile current catalog source into temp; exercise pure methods with proxy repos.

Uses cached dependency jars and existing unchanged legacy model bytecode only.
Does not start Spring/JPA, connect to DB/HTTP, or invoke importPackage/model code.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]


def main():
    base = ROOT / 'backend/springboot'
    src = base / 'src/main/java/com/dippie/moviercm'
    jars = sorted((Path.home() / '.m2/repository').rglob('*.jar'))
    dependencies = os.pathsep.join([str(base / 'target/classes')] + [str(p) for p in jars])
    sources = []
    for folder in ['dto/catalog', 'entity/catalog', 'repository/catalog', 'service/catalog']:
        sources += list((src / folder).glob('*.java'))
    sources += [src / 'config/StorageKeyConfig.java', src / 'exception/CatalogConflictException.java',
                Path(__file__).with_name('CATALOG_01_F01_LogicProbe.java')]
    with tempfile.TemporaryDirectory(prefix='catalog-f01-logic-') as directory:
        args = ['-proc:none', '-encoding', 'UTF-8', '-cp', dependencies, '-d', directory] + list(map(str, sources))
        argfile = Path(directory) / 'javac.args'
        argfile.write_text('\n'.join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding='utf-8')
        compiled = subprocess.run(['javac', '@' + str(argfile)], capture_output=True, text=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stderr)
        output = subprocess.run(['java', '-cp', directory + os.pathsep + dependencies,
                                 'CATALOG_01_F01_LogicProbe'], capture_output=True, text=True, encoding='utf-8', check=True)
    data = json.loads(output.stdout.strip())
    spec = importlib.util.spec_from_file_location('contract_logic', ROOT / 'docs/contracts/animation-catalog-v1/validate_catalog.py')
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    data['export_contract_errors'] = validator.validate(data['empty_db_export'])
    data['scope'] = 'current-source pure methods; proxy repositories, not DB transaction or HTTP evidence'
    rendered = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    (ROOT / 'docs/reviews/evidence/CATALOG_01_F01_logic_probe.json').write_text(rendered, encoding='utf-8')
    print(rendered)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
