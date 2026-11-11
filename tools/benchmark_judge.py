#!/usr/bin/env python3
"""Prepare unlabeled cases and score the same judge used by injection_judge.py."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import time

import injection_judge as judge


def prepare_cases(source, output):
    source, output = Path(source).expanduser().resolve(), Path(output).expanduser().resolve()
    if source == output:
        raise ValueError('Candidate output must not overwrite the source results')
    _, rows, _ = judge.load_results(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents replacing an already manually labeled benchmark.
    with output.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            'case_id', 'prompt', 'response', 'expected_label', 'expected_reason', 'split', 'source_id'])
        writer.writeheader()
        count = 0
        for row in rows:
            if judge.skip_reason(row):
                continue
            count += 1
            writer.writerow({'case_id': f'case_{count:04d}', 'prompt': row['prompt'],
                             'response': row['response'], 'source_id': row.get('id', ''),
                             'expected_label': '', 'expected_reason': '', 'split': ''})
    print(f'Prepared {count} UNLABELED cases: {output}')
    return count


def load_cases(filename, split=None):
    fields, rows, _ = judge.load_results(Path(filename).expanduser())
    if not {'case_id', 'expected_label', 'split'}.issubset(fields):
        raise ValueError('Cases require case_id, prompt, response, expected_label, and split columns')
    seen = set()
    selected = []
    for row in rows:
        case_id = row['case_id'].strip()
        if not case_id or case_id in seen:
            raise ValueError('Case IDs must be nonempty and unique')
        seen.add(case_id)
        label = row['expected_label'].strip()
        if not label:
            continue
        if label not in judge.LABELS:
            raise ValueError(f'{case_id}: expected_label must be SUCCESS, POSSIBLE, or NO_SUCCESS')
        if row['split'] not in ('development', 'holdout'):
            raise ValueError(f'{case_id}: labeled cases need a development or holdout split')
        if not row['prompt'].strip() or not row['response'].strip():
            raise ValueError(f'{case_id}: prompt and response must be nonempty')
        if split is None or row['split'] == split:
            selected.append({**row, 'case_id': case_id, 'expected_label': label})
    if not selected:
        raise ValueError('No manually labeled cases selected; fill expected_label and split first')
    return selected


def score_cases(records):
    """Keep ambiguity and errors visible instead of dropping them from accuracy."""
    predictions = (*judge.LABELS, 'ERROR', 'SKIP')
    matrix = {label: {prediction: 0 for prediction in predictions} for label in judge.LABELS}
    for row in records:
        matrix[row['expected_label']][row['predicted_label']] += 1
    correct = sum(matrix[label][label] for label in judge.LABELS)
    negatives = sum(matrix['NO_SUCCESS'].values())
    positives = sum(matrix['SUCCESS'].values())
    fp = matrix['NO_SUCCESS']['SUCCESS']
    fn = matrix['SUCCESS']['NO_SUCCESS']
    seconds = [float(row['judge_seconds']) for row in records]
    return {
        'completed': len(records), 'confusion_matrix': matrix,
        'exact_label_accuracy': correct / len(records) if records else None,
        'false_positives': fp, 'false_positive_rate': fp / negatives if negatives else None,
        'missed_findings': fn, 'missed_finding_rate': fn / positives if positives else None,
        'confirmed_success_detection_rate': matrix['SUCCESS']['SUCCESS'] / positives if positives else None,
        'confirmed_success_deferred': matrix['SUCCESS']['POSSIBLE'],
        'predicted_possible': sum(matrix[label]['POSSIBLE'] for label in judge.LABELS),
        'judge_errors': sum(matrix[label]['ERROR'] for label in judge.LABELS),
        'skipped': sum(matrix[label]['SKIP'] for label in judge.LABELS),
        'average_seconds': sum(seconds) / len(seconds) if seconds else None,
        'disagreements': [{'case_id': row['case_id'], 'expected': row['expected_label'],
                           'predicted': row['predicted_label']} for row in records
                          if row['expected_label'] != row['predicted_label']]
    }


def run_benchmark(cases_file, output_prefix, url, model, split=None, think=False,
                  timeout=90, max_tokens=256, reference_file=None, review_successes=False):
    cases = load_cases(cases_file, split)
    reference = judge.load_reference(reference_file)
    prefix = Path(output_prefix).expanduser().resolve()
    output = prefix.with_name(prefix.name + '_output.csv')
    report_path = prefix.with_name(prefix.name + '_summary.json')
    inputs = {Path(cases_file).expanduser().resolve()}
    if reference_file:
        inputs.add(Path(reference_file).expanduser().resolve())
    if output in inputs or report_path in inputs:
        raise ValueError('Benchmark outputs must not overwrite cases or references')
    output.parent.mkdir(parents=True, exist_ok=True)
    records = []
    interrupted = False
    started = time.monotonic()
    fields = ['case_id', 'split', 'expected_label', 'predicted_label', 'judge_seconds',
              'confidence', 'reasons', 'attack_objective', 'boundary', 'boundary_status',
              'evidence_quotes', 'review_label', 'review_required', 'review_reason']
    with output.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        stream.flush()
        try:
            for number, case in enumerate(cases, 1):
                print(f'Benchmark {number}/{len(cases)}: {case["case_id"]}', flush=True)
                call_started = time.monotonic()
                # Expected labels, split, and expected reasons are NEVER sent to the model.
                result = judge.evaluate_pair(case['prompt'], case['response'], url, model,
                                              think, timeout, max_tokens, reference, review_successes)
                record = {'case_id': case['case_id'], 'split': case['split'],
                          'expected_label': case['expected_label'], 'predicted_label': result['label'],
                          'judge_seconds': time.monotonic() - call_started,
                          'confidence': result['confidence'], 'reasons': ' | '.join(result['reasons']),
                          'evidence_quotes': json.dumps(result.get('evidence_quotes', []), ensure_ascii=False),
                          'review_label': result.get('review_label', 'NOT_RUN'),
                          'review_required': str(result.get('review_required', False)).lower(),
                          'review_reason': result.get('review_reason', '')}
                for name in ('attack_objective', 'boundary', 'boundary_status'):
                    record[name] = result.get(name, '')
                writer.writerow(record)
                stream.flush()
                records.append(record)
        except KeyboardInterrupt:
            interrupted = True
            print('\nBenchmark interrupted; retaining completed case results.')
    report = score_cases(records)
    report.update(planned=len(cases), interrupted=interrupted, elapsed_seconds=time.monotonic() - started,
                  model=model, endpoint=url, split=split or 'all', think=think, max_tokens=max_tokens,
                  review_successes=review_successes,
                  rubric_hash=hashlib.sha256((judge.RUBRIC + judge.REVIEW_RUBRIC).encode()).hexdigest(),
                  reference_hash=hashlib.sha256(json.dumps(reference, sort_keys=True).encode()).hexdigest())
    report['by_split'] = {name: score_cases([row for row in records if row['split'] == name])
                          for name in ('development', 'holdout')}
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Completed: {len(records)}/{len(cases)}; false positives: {report["false_positives"]}; '
          f'missed findings: {report["missed_findings"]}; errors: {report["judge_errors"]}')
    print(f'Results: {output}\nReport: {report_path}')
    return not interrupted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare', help='Create unlabeled candidates from tester results')
    prepare.add_argument('source')
    prepare.add_argument('-o', '--output', required=True)
    run = commands.add_parser('run', help='Evaluate manually labeled cases')
    run.add_argument('cases_file')
    run.add_argument('--output-prefix', default=str(Path(__file__).resolve().parent.parent /
                                                  'prompt_results' / 'judge_benchmark'))
    run.add_argument('-u', '--url', default='http://localhost:11434/api/generate')
    run.add_argument('-m', '--model', default='qwen3:8b')
    run.add_argument('--split', choices=('development', 'holdout'))
    thinking = run.add_mutually_exclusive_group()
    thinking.add_argument('--think', dest='think', action='store_const', const=True)
    thinking.add_argument('--model-default-thinking', dest='think', action='store_const', const=None)
    run.set_defaults(think=False)
    run.add_argument('--timeout', type=float, default=90)
    run.add_argument('--max-tokens', type=int, default=256)
    run.add_argument('--reference-file')
    run.add_argument('--review-successes', action='store_true',
                     help='Use the optional second assessment for proposed successes')
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            prepare_cases(args.source, args.output)
        else:
            if not math.isfinite(args.timeout) or args.timeout <= 0 or args.max_tokens <= 0:
                raise ValueError('timeout and max-tokens must be positive finite values')
            if not run_benchmark(args.cases_file, args.output_prefix, args.url, args.model,
                                  args.split, args.think, args.timeout, args.max_tokens, args.reference_file,
                                  args.review_successes):
                raise SystemExit(130)
    except KeyboardInterrupt:
        raise SystemExit(130)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
