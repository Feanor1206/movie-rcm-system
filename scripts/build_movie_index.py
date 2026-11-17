import json
import runpy
import sys
from pathlib import Path


def main():
    replacement = Path(__file__).resolve().parents[1] / 'ai' / 'build_text_embeddings.py'
    print(json.dumps({'status': 'migrated', 'replacement': 'python ai/build_text_embeddings.py --catalog CATALOG.json --artifact ARTIFACT_DIR --device cpu', 'message': 'Arguments now follow the offline content-hash embedding cache builder.'}), file=sys.stderr)
    runpy.run_path(str(replacement), run_name='__main__')


if __name__ == '__main__':
    main()
