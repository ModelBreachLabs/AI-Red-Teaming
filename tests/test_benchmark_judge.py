"""Synthetic plumbing/scoring tests; these are not manually labeled lab cases."""

import contextlib
import csv
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
# Reuse the test transport stub when requests is unavailable.
import test_injection_judge
import benchmark_judge as benchmark


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cases = self.root / 'cases.csv'

    def write_cases(self, rows):
        with self.cases.open('w', newline='') as output:
            writer = csv.DictWriter(output, fieldnames=['case_id', 'prompt', 'response',
                                                        'expected_label', 'expected_reason', 'split'])
            writer.writeheader()
            writer.writerows(rows)

    def cases_fixture(self):
        return [{'case_id': 'one', 'prompt': 'test prompt', 'response': 'test response',
                 'expected_label': 'NO_SUCCESS', 'expected_reason': 'DO_NOT_SEND_TO_MODEL',
                 'split': 'development'},
                {'case_id': 'two', 'prompt': 'holdout prompt', 'response': 'holdout response',
                 'expected_label': 'SUCCESS', 'expected_reason': 'DO_NOT_SEND_TO_MODEL',
                 'split': 'holdout'}]

    def test_prepare_does_not_invent_labels_or_modify_results(self):
        source = self.root / 'tester.csv'
        source.write_text('id,prompt,response,injection_label\n1,p,r,SUCCESS\n')
        original = source.read_bytes()
        candidates = self.root / 'candidates.csv'
        with contextlib.redirect_stdout(io.StringIO()):
            benchmark.prepare_cases(source, candidates)
        with candidates.open() as file:
            row = next(csv.DictReader(file))
        self.assertEqual(row['expected_label'], '')
        self.assertEqual(row['expected_reason'], '')
        self.assertEqual(row['split'], '')
        self.assertEqual(source.read_bytes(), original)
        with self.assertRaises(FileExistsError):
            benchmark.prepare_cases(source, candidates)

    def test_unlabeled_or_invalid_cases_fail_before_network_calls(self):
        rows = self.cases_fixture()
        for row in rows:
            row['expected_label'] = ''
        self.write_cases(rows)
        with patch.object(benchmark.judge, 'evaluate_pair') as model, self.assertRaises(ValueError):
            benchmark.run_benchmark(self.cases, self.root / 'report', 'url', 'model')
        model.assert_not_called()
        rows[0]['expected_label'] = 'INVALID'
        self.write_cases(rows)
        with self.assertRaises(ValueError):
            benchmark.load_cases(self.cases)

    def test_scoring_keeps_errors_and_deferrals_visible(self):
        pairs = [('NO_SUCCESS', 'SUCCESS'), ('SUCCESS', 'NO_SUCCESS'),
                 ('SUCCESS', 'POSSIBLE'), ('POSSIBLE', 'ERROR'), ('NO_SUCCESS', 'NO_SUCCESS')]
        records = [{'case_id': str(i), 'expected_label': expected, 'predicted_label': predicted,
                    'judge_seconds': 2} for i, (expected, predicted) in enumerate(pairs)]
        report = benchmark.score_cases(records)
        self.assertEqual(report['false_positives'], 1)
        self.assertEqual(report['missed_findings'], 1)
        self.assertEqual(report['confirmed_success_deferred'], 1)
        self.assertEqual(report['judge_errors'], 1)
        self.assertEqual(report['exact_label_accuracy'], .2)
        self.assertEqual(report['confirmed_success_detection_rate'], 0)
        self.assertEqual(len(report['disagreements']), 4)
        self.assertIsNone(benchmark.score_cases([])['exact_label_accuracy'])

    def test_holdout_is_excluded_and_expected_answers_are_not_sent(self):
        self.write_cases(self.cases_fixture())
        original = self.cases.read_bytes()
        prefix = self.root / 'Prompt Results' / 'benchmark'
        answer = {'label': 'NO_SUCCESS', 'confidence': 80, 'reasons': ['test fixture']}
        with patch.object(benchmark.judge, 'evaluate_pair', return_value=answer) as model, contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(benchmark.run_benchmark(self.cases, prefix, 'url', 'model', split='development'))
        model.assert_called_once()
        self.assertEqual(model.call_args.args[:2], ('test prompt', 'test response'))
        self.assertNotIn('DO_NOT_SEND_TO_MODEL', repr(model.call_args))
        self.assertNotIn('holdout prompt', repr(model.call_args))
        self.assertEqual(self.cases.read_bytes(), original)
        report = json.loads(prefix.with_name('benchmark_summary.json').read_text())
        self.assertEqual(report['completed'], 1)
        self.assertEqual(report['exact_label_accuracy'], 1)
        self.assertEqual(report['by_split']['holdout']['completed'], 0)
        self.assertFalse(report['review_successes'])
        self.assertIs(model.call_args.args[-1], False)

    def test_optional_review_is_forwarded_and_recorded(self):
        self.write_cases(self.cases_fixture())
        prefix = self.root / 'reviewed'
        answer = {'label': 'NO_SUCCESS', 'confidence': 80, 'reasons': ['test fixture']}
        with patch.object(benchmark.judge, 'evaluate_pair', return_value=answer) as model, contextlib.redirect_stdout(io.StringIO()):
            benchmark.run_benchmark(self.cases, prefix, 'url', 'model',
                                    split='development', review_successes=True)
        self.assertIs(model.call_args.args[-1], True)
        report = json.loads(prefix.with_name('reviewed_summary.json').read_text())
        self.assertTrue(report['review_successes'])

    def test_interrupted_run_reports_only_completed_cases(self):
        self.write_cases(self.cases_fixture())
        prefix = self.root / 'benchmark'
        answer = {'label': 'NO_SUCCESS', 'confidence': 80, 'reasons': ['test fixture']}
        with patch.object(benchmark.judge, 'evaluate_pair', side_effect=[answer, KeyboardInterrupt]), contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(benchmark.run_benchmark(self.cases, prefix, 'url', 'model'))
        report = json.loads(prefix.with_name('benchmark_summary.json').read_text())
        self.assertTrue(report['interrupted'])
        self.assertEqual(report['planned'], 2)
        self.assertEqual(report['completed'], 1)


if __name__ == '__main__':
    unittest.main()
