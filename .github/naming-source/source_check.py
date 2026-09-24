#!/usr/bin/env python3
"""Direct-source naming check, removing JSON-code serialization as a confound.

Candidates and semantic code cases are unchanged. No generated source is
executed or repaired. Optional enclosing Python fences alone are stripped.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import random
import re
import time

confirmation = Path(__file__).resolve().parent.parent / 'naming-confirmation' / 'confirm.py'
if not confirmation.exists():
    confirmation = Path(__file__).with_name('confirm.py')
spec = importlib.util.spec_from_file_location('confirmation', confirmation)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
b = c.b
PROTOCOL = {
    **c.PROTOCOL,
    'design': 'Direct-source amendment to isolate code naming from JSON serialization.',
    'amendment': 'Observed atomic code outputs include wrong JSON field names, singleton list envelopes and double-escaped source newlines. All candidate wording and semantic tasks stay unchanged. Return source directly; only enclosing Python fences are removed. No source repair. Filenames are not assessed in this supplement; path decisions remain in the atomic decision bank.',
    'units': '128 fresh source completions: eight tasks, four conditions, two models and two seeds.',
    'selection': 'For final selection, combine the 640 single-item decision observations from atomic run 35972991366 with these 128 direct-source observations. Replace, do not combine with, the format-confounded atomic JSON-code observations. Among non-control wordings choose fewest core failures, then fewer whitespace-delimited words, then ID. Validation is excluded. This amendment is frozen before its own source inference, but follows inspection of some atomic results; it is an exploratory amendment, not an independent confirmatory trial.',
    'scoring': 'Same prewritten code naming checks as the atomic study, except no filename score. Source fences may be stripped; JSON wrappers, prose and source syntax are not repaired. Structural behavior-shape checks remain secondary. No generated code execution.',
    'decision_source_run': 35972991366,
    'candidate_changes': False,
}


def source_text(text: str) -> str:
    text = text.strip()
    match = re.fullmatch(r'```(?:python|py)?\s*\n(.*?)\n```', text, re.S)
    return match.group(1).strip() if match else text


def grade(task: dict, text: str) -> dict:
    # The known task filename is a harness input, not a model naming success.
    result = c.score_naming(task, {'path': task['good']['path'], 'code': source_text(text)})
    result['naming_checks'].pop('path', None)
    result['passed'] = all(result['naming_checks'].values())
    return result


def self_test() -> None:
    c.self_test()
    checks = 0
    for task in b.GEN:
        for text in [task['good']['code'], '```python\n' + task['good']['code'] + '```']:
            assert grade(task, text)['passed'], task['id']
            checks += 1
        assert not grade(task, 'def :')['passed']
        checks += 1
    task = next(x for x in b.GEN if x['id'] == 'g01')
    assert not grade(task, task['good']['code'].replace('seconds_to_milliseconds', 'phase4_seconds_to_milliseconds'))['passed']
    checks += 1
    print(json.dumps({'direct_source_checks': checks, 'passed': True}), flush=True)


def worker(model: str, condition: str) -> None:
    out = Path('source-results') / (model + '-' + condition)
    out.mkdir(parents=True, exist_ok=True)
    b.write_json(out / 'protocol.json', PROTOCOL)
    b.write_json(out / 'manifest.json', {
        'protocol_sha256': b.sha_file(out / 'protocol.json'),
        'script_sha256': b.sha_file(Path(__file__)),
        'confirmation_sha256': b.sha_file(confirmation),
        'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'model': model, 'condition': condition,
    })
    self_test()
    process = log = None
    records = []
    try:
        process, log = b.bootstrap(model, out)
        system = 'You are a coding assistant working in a repository. Follow the repository guidance below and the requested response format.\n\n' + b.CONDITIONS[condition]
        for seed in b.SEEDS:
            tasks = list(b.GEN)
            random.Random(seed + 1).shuffle(tasks)
            for task in tasks:
                prompt = task['task'] + '\nFor this request, the filename is handled separately: return ONLY the complete Python source. Do not return a filename, JSON or explanatory prose.'
                request, response, seconds = c.call(system, prompt, seed, 400)
                text = response['choices'][0]['message']['content']
                score = grade(task, text)
                row = {'model': model, 'condition': condition, 'seed': seed, 'case': task['id'],
                       'split': task['split'], 'kind': task['kind'], 'task_type': 'source', **score}
                records.append(row)
                b.write_json(out / f'{task["id"]}-{seed}.json', {'request': request, 'response': response, 'seconds': seconds, 'score': row})
                b.write_json(out / 'scores.json', records)
                print(json.dumps(row), flush=True)
        b.write_json(out / 'status.json', {'complete': True, 'observations': len(records), 'completions': 16})
    except Exception as error:
        b.write_json(out / 'status.json', {'complete': False, 'error': str(error), 'observations': len(records)})
        raise
    finally:
        b.write_json(out / 'scores.json', records)
        if process:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()
        if log:
            log.close()


def aggregate(root: Path) -> None:
    records = []
    for path in sorted(root.rglob('scores.json')):
        records += json.loads(path.read_text())
    statuses = [json.loads(path.read_text()) for path in root.rglob('status.json')]
    complete = len(statuses) == 8 and all(s['complete'] for s in statuses) and len(records) == 128
    summary = {'complete': complete, 'observations': len(records), 'conditions': {}}
    for condition in b.CONDITIONS:
        summary['conditions'][condition] = {}
        for split in ['core', 'validation']:
            rows = [r for r in records if r['condition'] == condition and r['split'] == split]
            summary['conditions'][condition][split] = {'passed': sum(r['passed'] for r in rows), 'total': len(rows)}
    b.write_json(root / 'summary.json', summary)
    b.write_json(root / 'all-scores.json', records)
    print(json.dumps(summary, indent=2))
    if not complete:
        raise SystemExit('Incomplete source comparison')


def combine(atomic: Path, source: Path, out: Path) -> None:
    assert json.loads((atomic / 'summary.json').read_text())['complete']
    assert json.loads((source / 'summary.json').read_text())['complete']
    decisions = [r for r in json.loads((atomic / 'all-scores.json').read_text()) if r['task_type'] == 'decision']
    code = json.loads((source / 'all-scores.json').read_text())
    assert len(decisions) == 640 and len(code) == 128
    rows = decisions + code
    summary = {'complete': True, 'observations': len(rows), 'conditions': {}}
    for condition in b.CONDITIONS:
        result = {'words': b.words(b.CONDITIONS[condition])}
        for split in ['core', 'validation']:
            items = [r for r in rows if r['condition'] == condition and r['split'] == split]
            result[split] = {'passed': sum(r['passed'] for r in items), 'total': len(items)}
        for kind in ['decision', 'source']:
            items = [r for r in rows if r['condition'] == condition and r['task_type'] == kind]
            result[kind] = {'passed': sum(r['passed'] for r in items), 'total': len(items)}
        result['failures'] = [r for r in rows if r['condition'] == condition and not r['passed']]
        summary['conditions'][condition] = result
    order = sorted((k for k in b.CONDITIONS if k != 'T4'), key=lambda k: (
        summary['conditions'][k]['core']['total'] - summary['conditions'][k]['core']['passed'], b.words(b.CONDITIONS[k]), k))
    summary['selected_on_core'] = order[0]
    summary['selection_order'] = order
    b.write_json(out / 'summary.json', summary)
    b.write_json(out / 'all-scores.json', rows)
    (out / 'selected-guidance.md').write_text(b.CONDITIONS[order[0]] + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--worker', nargs=2)
    parser.add_argument('--aggregate', type=Path)
    parser.add_argument('--combine', nargs=3, type=Path, metavar=('ATOMIC', 'SOURCE', 'OUTPUT'))
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.worker:
        worker(*args.worker)
    elif args.aggregate:
        aggregate(args.aggregate)
    elif args.combine:
        combine(*args.combine)
    else:
        parser.error('Choose an operation')
