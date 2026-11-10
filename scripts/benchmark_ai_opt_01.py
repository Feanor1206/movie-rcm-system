import json
import sys

from benchmark_qwen_cuda import main


if __name__ == '__main__':
    print(json.dumps({'status': 'migrated', 'replacement': 'python scripts/benchmark_qwen_cuda.py --help', 'retrievalQualityGate': 'python ai/evaluation/retrieval_gate.py --help', 'message': 'The removed in-process NF4 pipeline benchmark is replaced by external provider latency and independent retrieval evaluation.'}), file=sys.stderr)
    raise SystemExit(main())
