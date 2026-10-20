import contextlib
import csv
import importlib.util
import io
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import requests
except ImportError:
    requests = types.ModuleType('requests')
    requests.post = lambda *args, **kwargs: None
    requests.exceptions = types.SimpleNamespace(
        Timeout=type('Timeout', (Exception,), {}),
        SSLError=type('SSLError', (Exception,), {}),
        ConnectionError=type('ConnectionError', (Exception,), {}))
    sys.modules['requests'] = requests

SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'prompt_tester.py'
spec = importlib.util.spec_from_file_location('prompt_tester', SCRIPT)
tester = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tester)


class PromptTesterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dataset = self.root / 'dataset.csv'
        self.output = self.root / 'results.csv'

    def test_validation_retains_duplicates_and_reads_bom_multiline(self):
        self.dataset.write_text('\ufeffid,technique,prompt\n1,marker,"hello\nworld"\n1,marker,"hello\nworld"\n2,marker,\n', encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()) as log:
            prompts = tester.read_prompts(str(self.dataset))
        self.assertEqual(len(prompts), 2)
        self.assertEqual(prompts[0]['prompt'], 'hello\nworld')
        self.assertIn('duplicate ID', log.getvalue())
        self.assertIn('duplicate prompt', log.getvalue())
        self.assertIn('empty prompt skipped', log.getvalue())

    def test_invalid_datasets(self):
        for content in ('prompt\nhello\n', 'id,technique,prompt\n1,x,a,extra\n',
                        'id,technique,prompt\n1,x\n', 'id,technique,prompt\n1,x,"unterminated',
                        'id,technique,prompt\n', 'id,technique,prompt,prompt\n1,x,a,b\n'):
            with self.subTest(content=content):
                self.dataset.write_text(content)
                with self.assertRaises(ValueError):
                    tester.read_prompts(str(self.dataset))

    def test_invalid_dataset_does_not_send_or_replace_output(self):
        self.dataset.write_text('prompt\nhello\n')
        self.output.write_text('original evidence')
        with patch.object(sys, 'argv', ['tester', '10', str(self.dataset), '-o', str(self.output)]), patch.object(tester, 'send_chat_message') as send, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                tester.main()
        self.assertEqual(stopped.exception.code, 1)
        send.assert_not_called()
        self.assertEqual(self.output.read_text(), 'original evidence')
        self.assertEqual(list(self.root.glob('*backup*')), [])

    def test_input_cannot_be_output(self):
        self.dataset.write_text('id,technique,prompt\n1,x,hello\n')
        with patch.object(sys, 'argv', ['tester', '10', str(self.dataset), '-o', str(self.dataset)]), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                tester.main()
        self.assertEqual(stopped.exception.code, 2)
        self.assertIn('1,x,hello', self.dataset.read_text())

    def test_default_output_uses_root_prompt_results_directory(self):
        self.dataset.write_text('id,technique,prompt\n1,x,hello\n')
        root = self.root / 'checkout'
        expected = root / 'Prompt Results' / 'dataset_output.csv'
        with patch.object(tester, '__file__', str(root / 'tools' / 'prompt_tester.py')), patch.object(sys, 'argv', ['tester', '600000', str(self.dataset)]), patch.object(tester, 'send_chat_message', return_value=(True, {'success': True, 'response': 'hello'}, 200)), contextlib.redirect_stdout(io.StringIO()):
            tester.main()
        self.assertTrue(expected.is_file())
        self.assertFalse((root / 'Documentation').exists())
        with expected.open() as source:
            self.assertEqual(list(csv.DictReader(source))[0]['response'], 'hello')

    def test_backups_are_unique_and_preserve_bytes(self):
        self.output.write_bytes(b'original\r\nevidence\r\n')
        first = tester.backup_output(self.output)
        second = tester.backup_output(self.output)
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), self.output.read_bytes())
        self.assertEqual(second.read_bytes(), self.output.read_bytes())

    def test_failed_backup_prevents_requests_and_truncation(self):
        self.output.write_text('original evidence')
        prompts = [{'id': '1', 'technique': 'x', 'prompt': 'hello'}]
        with patch.object(tester.shutil, 'copyfileobj', side_effect=OSError('disk full')), patch.object(tester, 'send_chat_message') as send, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(OSError):
                tester.test_prompts('unused', prompts, 600000, str(self.output))
        send.assert_not_called()
        self.assertEqual(self.output.read_text(), 'original evidence')

    def test_error_classification(self):
        cases = [(False, {}, 401, 'AUTHENTICATION'), (False, {}, 403, 'ACCESS_DENIED'),
                 (False, {}, 429, 'RATE_LIMIT'), (False, {}, 500, 'HTTP_ERROR'),
                 (True, {'error': 'rate limit exceeded'}, 200, 'RATE_LIMIT'),
                 (True, {}, 200, 'RESPONSE_FORMAT'),
                 (True, {'success': False}, 200, 'APPLICATION_ERROR'),
                 (True, {'success': True, 'response': None}, 200, 'RESPONSE_FORMAT'),
                 (True, {'success': True, 'response': ''}, 200, '')]
        for http_ok, data, status, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(tester.classify_error(http_ok, data, status)[0], expected)

    def test_transport_and_json_errors(self):
        for exc, expected in [(requests.exceptions.Timeout(), 'TIMEOUT'),
                              (requests.exceptions.SSLError(), 'TLS_ERROR'),
                              (requests.exceptions.ConnectionError(), 'CONNECTION_ERROR')]:
            with patch.object(requests, 'post', side_effect=exc):
                ok, data, status = tester.send_chat_message('unused', 'hello')
            self.assertEqual(tester.classify_error(ok, data, status)[0], expected)
        response = types.SimpleNamespace(ok=True, status_code=200)
        for body, expected in [(None, 'INVALID_JSON'), ([], 'RESPONSE_FORMAT')]:
            def decode():
                if body is None:
                    raise ValueError('invalid JSON')
                return body
            response.json = decode
            with patch.object(requests, 'post', return_value=response):
                outcome = tester.send_chat_message('unused', 'hello')
            self.assertEqual(tester.classify_error(*outcome)[0], expected)

    def test_csv_summary_backup_repeats_and_cookie(self):
        self.output.write_text('previous run')
        prompts = [{'id': '1', 'technique': 'marker', 'prompt': 'hello'}]
        outcomes = [(True, {'success': True, 'response': 'marker'}, 200),
                    (False, {'error': 'slow', '_error_type': 'TIMEOUT'}, 0)]
        with patch.object(tester, 'send_chat_message', side_effect=outcomes) as send, contextlib.redirect_stdout(io.StringIO()) as log:
            complete = tester.test_prompts('unused', prompts, 600000, str(self.output), repeat=2, check_for_phrase=True, cookie='test-cookie', max_workers=1)
        self.assertTrue(complete)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(send.call_args.args[2], 'test-cookie')
        with self.output.open() as source:
            rows = list(csv.DictReader(source))
        self.assertEqual([r['repeat_number'] for r in rows], ['1', '2'])
        self.assertEqual([r['phrase_check'] for r in rows], ['SUCCESS', 'N/A'])
        self.assertEqual(rows[1]['error_type'], 'TIMEOUT')
        self.assertEqual(next(self.root.glob('*backup*')).read_text(), 'previous run')
        self.assertIn('TIMEOUT: 1', log.getvalue())
        self.assertIn('Response time (all):', log.getvalue())
        self.assertIn(str(self.output.resolve()), log.getvalue())

    @unittest.skipUnless(hasattr(signal, 'SIGINT') and sys.platform != 'win32', 'POSIX signal test')
    def test_interrupt_saves_results_and_exits_with_stalled_worker(self):
        self.dataset.write_text('id,technique,prompt\n1,x,fast\n2,x,block\n')
        child = '''import runpy, sys, time, types
requests = types.ModuleType('requests')
def post(url, json, **kwargs):
    if json['message'] == 'block':
        time.sleep(60)
    return types.SimpleNamespace(ok=True, status_code=200, json=lambda: {'success': True, 'response': 'saved response'})
requests.post = post
sys.modules['requests'] = requests
script = sys.argv.pop(1)
runpy.run_path(script, run_name='__main__')
'''
        process = subprocess.Popen([sys.executable, '-c', child, str(SCRIPT), '600000', str(self.dataset), '-o', str(self.output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if self.output.exists() and 'saved response' in self.output.read_text():
                    break
                if process.poll() is not None:
                    self.fail(str(process.communicate()))
                time.sleep(0.02)
            else:
                self.fail('Completed result was not flushed')
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 130, stderr)
            self.assertIn('Partial results', stdout)
            with self.output.open() as source:
                self.assertEqual(len(list(csv.DictReader(source))), 1)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


if __name__ == '__main__':
    unittest.main()

