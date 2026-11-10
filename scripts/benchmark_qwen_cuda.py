import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend' / 'fastapi'))


def provider_url(value):
    try:
        parsed = urlsplit(value)
        parsed.port
    except ValueError:
        raise argparse.ArgumentTypeError('base-url contains an invalid host or port') from None
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise argparse.ArgumentTypeError('base-url must be an HTTP(S) provider URL without credentials, query or fragment')
    return value.rstrip('/')


def positive_count(value):
    try:
        count = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('iterations must be an integer between 1 and 100') from None
    if not 1 <= count <= 100:
        raise argparse.ArgumentTypeError('iterations must be between 1 and 100')
    return count


async def run_benchmark(args, transport=None):
    import httpx
    from services.llm_client import LLMClient, LLMProtocolError, LLMUnavailableError
    from services.model_registry import ModelRegistry, InferenceCapacityError
    rows = []
    async with httpx.AsyncClient(transport=transport, follow_redirects=False, timeout=httpx.Timeout(30.0, connect=5.0)) as http:
        llm = LLMClient(ModelRegistry(args.mode), client=http)
        llm.base_url = args.base_url
        llm.model = args.model
        for iteration in range(args.iterations):
            for query in args.query:
                started = time.perf_counter()
                row = {'iteration': iteration + 1, 'query': query, 'task': args.task, 'firstTextMs': None}
                messages = [{'role': 'user', 'content': query}]
                try:
                    if args.task == 'intent':
                        row['intent'] = await llm.parse_intent(messages)
                    else:
                        chunks = []
                        async for chunk in llm.stream(messages):
                            if row['firstTextMs'] is None:
                                row['firstTextMs'] = (time.perf_counter() - started) * 1000
                            chunks.append(chunk)
                        row['outputCharacters'] = len(''.join(chunks))
                    row['success'] = True
                except (LLMProtocolError, LLMUnavailableError, InferenceCapacityError):
                    row['success'] = False
                    row['error'] = 'Provider request failed or returned invalid output'
                row['totalMs'] = (time.perf_counter() - started) * 1000
                rows.append(row)
    return {'schemaVersion': 'dippie.external-llm-benchmark.v1', 'timestamp': datetime.now(timezone.utc).isoformat(),
            'mode': args.mode, 'model': args.model, 'task': args.task, 'vram': None,
            'vramSource': 'Not measured; model runs in an external provider process', 'results': rows}


def main():
    parser = argparse.ArgumentParser(description='Benchmark an explicitly configured external llama-server or DeepSeek endpoint. No model is loaded or downloaded by this script.')
    parser.add_argument('--base-url', type=provider_url, required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--mode', choices=('full', 'cloud'), default='full')
    parser.add_argument('--task', choices=('stream', 'intent'), default='stream')
    parser.add_argument('--query', action='append', required=True)
    parser.add_argument('--iterations', type=positive_count, default=1)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.execute:
        parser.error('Pass --execute to authorize live requests to this provider')
    if not args.model.strip() or len(args.model) > 512:
        parser.error('model must contain between 1 and 512 characters')
    if any(not query.strip() or len(query) > 4000 for query in args.query) or len(args.query) > 100:
        parser.error('Provide 1 to 100 nonempty queries, each at most 4000 characters')
    if args.mode == 'cloud' and args.base_url.split(':', 1)[0] != 'https':
        parser.error('Cloud provider URLs must use HTTPS')
    report = asyncio.run(run_benchmark(args))
    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + '\n', encoding='utf-8')
    return 0 if all(row['success'] for row in report['results']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
