"""Direct Gemini pilot, with bounded spend, resumable transport logs, and no code execution.

Only the exported model-facing task file is read. GEMINI_API_KEY stays in process memory.
This script never grades or executes returned Python. Pricing inputs are operator-supplied
estimates; the budget guard is not a provider billing cap.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time
import urllib.error
import urllib.request


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def append(path, record):
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + '\n')


def save_responses(path, attempts):
    records = [record['parsed_response'] for record in attempts if record.get('parsed_response')]
    temporary = path.with_suffix('.tmp')
    temporary.write_text(''.join(json.dumps(record, ensure_ascii=False) + '\n' for record in records), encoding='utf-8')
    temporary.replace(path)


def parse_record(text, task_id):
    value = json.loads(text)
    if not isinstance(value, dict) or value.get('task_id') != task_id:
        raise ValueError('Response is not an object with the requested task ID.')
    if not isinstance(value.get('decision'), str) or value.get('decision') not in {'accept', 'reject', 'no_change'}:
        raise ValueError('Invalid decision.')
    if not isinstance(value.get('source'), str) or not isinstance(value.get('explanation'), str):
        raise ValueError('Missing source or explanation.')
    if not value['explanation'].strip():
        raise ValueError('Empty explanation.')
    return {key: value[key] for key in ('task_id', 'decision', 'source', 'explanation')}


def load_tasks(data):
    try:
        lines = data.decode('utf-8').splitlines()
    except UnicodeError:
        raise ValueError('Task file must use UTF-8.') from None
    if not lines:
        raise ValueError('Task file must contain at least one task.')
    tasks = []
    seen = set()
    for number, line in enumerate(lines, 1):
        try:
            task = json.loads(line)
        except ValueError:
            raise ValueError(f'Task file line {number} must contain a JSON object.') from None
        if not isinstance(task, dict) or any(
                not isinstance(task.get(field), str) or not task[field].strip()
                for field in ('task_id', 'benchmark_version', 'prompt')):
            raise ValueError(f'Task file line {number} needs nonempty task_id, benchmark_version, and prompt strings.')
        if task['task_id'] in seen:
            raise ValueError(f'Task file line {number} repeats a task_id.')
        if tasks and task['benchmark_version'] != tasks[0]['benchmark_version']:
            raise ValueError(f'Task file line {number} has a different benchmark_version.')
        seen.add(task['task_id'])
        tasks.append(task)
    return tasks


USAGE_COUNTS = ('promptTokenCount', 'candidatesTokenCount', 'thoughtsTokenCount')


def validate_usage(usage):
    if usage is None:
        return {}
    if not isinstance(usage, dict) or any(
            type(usage.get(field, 0)) is not int or usage.get(field, 0) < 0
            for field in USAGE_COUNTS):
        raise ValueError('Invalid provider usage metadata.')
    return usage


def usage_count(record, field):
    # Older attempt logs may contain malformed metadata; never retry those requests.
    usage = record.get('usage')
    value = usage.get(field, 0) if isinstance(usage, dict) else 0
    return value if type(value) is int and value >= 0 else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks', type=Path, required=True)
    parser.add_argument('--model', required=True, choices=('gemini-2.5-flash-lite', 'gemini-2.5-flash', 'gemini-3.5-flash-lite'))
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--max-output-tokens', type=int, default=1536)
    parser.add_argument('--max-estimated-usd', type=float, default=1.0)
    parser.add_argument('--input-usd-per-million', type=float, required=True)
    parser.add_argument('--output-usd-per-million', type=float, required=True)
    parser.add_argument('--seed', type=int, default=20261020)
    parser.add_argument('--pause-seconds', type=float, default=0.2)
    parser.add_argument('--thinking-level', choices=('minimal', 'low', 'medium', 'high'))
    args = parser.parse_args()
    if not all(math.isfinite(value) for value in (
            args.max_estimated_usd, args.input_usd_per_million,
            args.output_usd_per_million, args.pause_seconds)):
        parser.error('Budgets, rates, and pauses must be finite numbers.')
    if (args.max_output_tokens < 1 or args.max_estimated_usd <= 0 or args.input_usd_per_million < 0
            or args.output_usd_per_million < 0 or args.pause_seconds < 0 or
            (args.limit is not None and args.limit < 1)):
        parser.error('Budgets/output limits must be positive; rates and pauses must be nonnegative.')
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        parser.error('GEMINI_API_KEY is unavailable. Do not place credentials in source or output files.')
    data = args.tasks.read_bytes()
    try:
        tasks = load_tasks(data)
    except ValueError as error:
        parser.error(str(error))
    random.Random(args.seed).shuffle(tasks)
    if args.limit:
        tasks = tasks[:args.limit]
    args.directory.mkdir(parents=True, exist_ok=True)
    manifest_path = args.directory / 'run.json'
    config = dict(model_id=args.model, provider='Google Gemini Developer API direct',
                  track='direct-completion', tasks_sha256=digest(data), expected_tasks=len(tasks),
                  benchmark_version=tasks[0]['benchmark_version'], seed=args.seed,
                  temperature=0, thinking_budget=None if args.thinking_level else 0,
                  thinking_level=args.thinking_level, max_output_tokens=args.max_output_tokens,
                  tools_allowed=[], repetitions=1, system_prompt=None, response_mime_type='application/json',
                  response_schema='task_id:str, decision:enum, explanation:str, source:str',
                  input_usd_per_million=args.input_usd_per_million,
                  output_usd_per_million=args.output_usd_per_million,
                  max_estimated_usd=args.max_estimated_usd,
                  runner_sha256=digest(Path(__file__).read_bytes()),
                  adapter='urllib standard library; no SDK; no automatic answer-dependent retries')
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding='utf-8'))
        if previous['config'] != config:
            parser.error('Resume configuration mismatch; use a fresh run directory.')
        manifest = previous
    else:
        manifest = dict(started_at=now(), config=config, status='running')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    attempts_path = args.directory / 'attempts.jsonl'
    responses_path = args.directory / 'responses.jsonl'
    attempts = [json.loads(line) for line in attempts_path.read_text(encoding='utf-8').splitlines()] if attempts_path.exists() else []
    save_responses(responses_path, attempts)
    done = {record['task_id'] for record in attempts}
    # Conservative reservation: UTF-8 byte count used as an input-token upper estimate,
    # plus output cap. Reserve even failed requests so unknown provider usage is not ignored.
    reserved = sum(record.get('reserved_usd', 0) for record in attempts)
    schema = {'type': 'OBJECT', 'properties': {
        'task_id': {'type': 'STRING'},
        'decision': {'type': 'STRING', 'enum': ['accept', 'reject', 'no_change']},
        'explanation': {'type': 'STRING'}, 'source': {'type': 'STRING'}},
        'required': ['task_id', 'decision', 'explanation', 'source']}
    stop_reason = 'completed'
    for task in tasks:
        task_id = task['task_id']
        if task_id in done:
            continue
        prompt = task['prompt'] + '\n\nThe task_id for this request is: ' + task_id
        reserve = ((len(prompt.encode('utf-8')) + 1000) * args.input_usd_per_million +
                   args.max_output_tokens * args.output_usd_per_million) / 1_000_000
        if reserved + reserve > args.max_estimated_usd:
            stop_reason = 'estimated-budget-reservation-limit'
            break
        body = {'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
                'generationConfig': {'temperature': 0, 'maxOutputTokens': args.max_output_tokens,
                    'thinkingConfig': ({'thinkingLevel': args.thinking_level} if args.thinking_level
                                       else {'thinkingBudget': 0}), 'responseMimeType': 'application/json',
                    'responseSchema': schema}}
        request = urllib.request.Request(
            f'https://generativelanguage.googleapis.com/v1beta/models/{args.model}:generateContent',
            data=json.dumps(body).encode('utf-8'), headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
        record = dict(task_id=task_id, started_at=now(), prompt_sha256=digest(prompt.encode('utf-8')),
                      reserved_usd=reserve)
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = json.load(response)
            # Only model output, usage and identifiers are logged; never request headers.
            record.update(status='received', model_version=raw.get('modelVersion'),
                          response_id=raw.get('responseId'), usage=validate_usage(raw.get('usageMetadata')),
                          candidates=raw.get('candidates', []), prompt_feedback=raw.get('promptFeedback'))
            candidates = raw.get('candidates') or []
            parts = candidates[0].get('content', {}).get('parts', []) if candidates else []
            text = ''.join(part.get('text', '') for part in parts
                           if not part.get('thought'))
            try:
                parsed = parse_record(text, task_id)
                record['parse_valid'] = True
                record['parsed_response'] = parsed
            except (ValueError, IndexError, TypeError):
                record['parse_valid'] = False
        except urllib.error.HTTPError as error:
            record.update(status='http-error', http_status=error.code, parse_valid=False)
            # Error bodies can echo submitted credentials; deliberately never persist them.
            stop_reason = f'http-{error.code}'
        except (urllib.error.URLError, TimeoutError):
            record.update(status='transport-error', parse_valid=False)
            stop_reason = 'transport-error'
        except (ValueError, UnicodeError, TypeError, AttributeError, IndexError):
            record.update(status='invalid-provider-response', parse_valid=False)
            stop_reason = 'invalid-provider-response'
        record.update(finished_at=now(), elapsed_seconds=round(time.monotonic() - started, 3))
        append(attempts_path, record)
        attempts.append(record)
        save_responses(responses_path, attempts)
        reserved += reserve
        print(json.dumps(dict(completed=len(attempts), expected=len(tasks),
                              status=record['status'], parse_valid=record['parse_valid'])), flush=True)
        if record['status'] != 'received':
            break
        time.sleep(args.pause_seconds)
    prompt_tokens = sum(usage_count(record, 'promptTokenCount') for record in attempts)
    output_tokens = sum(usage_count(record, 'candidatesTokenCount') +
                        usage_count(record, 'thoughtsTokenCount') for record in attempts)
    manifest.update(finished_at=now(), status=stop_reason, attempts=len(attempts),
                    valid_responses=sum(record.get('parse_valid', False) for record in attempts),
                    prompt_tokens=prompt_tokens, output_and_thought_tokens=output_tokens,
                    price_based_estimate_usd=(prompt_tokens * args.input_usd_per_million +
                                              output_tokens * args.output_usd_per_million) / 1_000_000,
                    reserved_estimate_usd=reserved,
                    billed_cost_usd=None,
                    model_versions=sorted({record['model_version'] for record in attempts if record.get('model_version')}),
                    note='Usage-based price estimate, not a provider invoice. No returned code was executed. '
                         'Failed/invalid requests are retained; no selective accuracy retries.')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in manifest.items() if key != 'config'}, indent=2), flush=True)
    return 0 if stop_reason == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
