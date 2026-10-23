import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tools import prompt_runner


class PromptRunnerTests(unittest.TestCase):
    def test_validate_api_url_accepts_http_and_https_hosts(self):
        self.assertEqual(
            prompt_runner.validate_api_url('http://localhost:5000/api/chat'),
            'http://localhost:5000/api/chat')
        self.assertEqual(
            prompt_runner.validate_api_url('https://api.example.com/v1/chat?key=value'),
            'https://api.example.com/v1/chat?key=value')

    def test_validate_api_url_rejects_invalid_endpoint_urls(self):
        for value in ('localhost:5000/api/chat', 'ftp://api.example.com/chat',
                      'https:///chat', 'https://api.example.com:bad/chat'):
            with self.subTest(value=value), self.assertRaises(
                    prompt_runner.argparse.ArgumentTypeError):
                prompt_runner.validate_api_url(value)

    def test_send_chat_message_uses_provided_session(self):
        response = SimpleNamespace(
            status_code=200,
            ok=True,
            json=lambda: {'success': True, 'response': 'CANARY'},
        )
        session = Mock()
        session.post.return_value = response

        result = prompt_runner.send_chat_message(
            'https://api.example.com/v1/chat', 'test', session=session)

        self.assertEqual(result, (True, {'success': True, 'response': 'CANARY'}, 200))
        session.post.assert_called_once()
        self.assertEqual(session.post.call_args.args[0], 'https://api.example.com/v1/chat')

    def test_classify_error_preserves_response_categories(self):
        self.assertEqual(
            prompt_runner.classify_error(False, {'error': 'slow'}, 429),
            ('RATE_LIMIT', 'slow'))
        self.assertEqual(
            prompt_runner.classify_error(True, {'success': True, 'response': 'ok'}, 200),
            ('', ''))

    def test_read_prompts_validates_and_skips_empty_prompts(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / 'prompts.csv'
            dataset.write_text(
                'id,technique,prompt\n1,CANARY,hello\n2,EMPTY, \n',
                encoding='utf-8',
            )

            prompts = prompt_runner.read_prompts(str(dataset))

        self.assertEqual(prompts, [{'id': '1', 'technique': 'CANARY', 'prompt': 'hello'}])

    def test_test_prompts_keeps_csv_schema_and_phrase_check(self):
        prompts = [
            {'id': '1', 'technique': 'CANARY', 'prompt': 'prompt one'},
            {'id': '2', 'technique': 'MARKER', 'prompt': 'prompt two'},
        ]
        output_fields = [
            'id', 'technique', 'repeat_number', 'request_number', 'response_time_ms',
            'prompt', 'response', 'status_code', 'timestamp', 'error_type', 'phrase_check',
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'prompt_results' / 'results.csv'
            response = {'success': True, 'response': 'A CANARY response'}
            with patch.object(prompt_runner, 'send_chat_message',
                              return_value=(True, response, 200)):
                completed = prompt_runner.test_prompts(
                    'http://localhost/api/chat',
                    prompts,
                    requests_per_minute=60000,
                    output_file=str(output),
                    repeat=2,
                    check_for_phrase=True,
                    max_workers=2,
                )
            with output.open(newline='', encoding='utf-8') as result_file:
                reader = csv.DictReader(result_file)
                rows = list(reader)

        self.assertTrue(completed)
        self.assertEqual(reader.fieldnames, output_fields)
        self.assertEqual(len(rows), 4)
        self.assertEqual({row['phrase_check'] for row in rows}, {'SUCCESS', 'NO_SUCCESS'})
        self.assertEqual({row['repeat_number'] for row in rows}, {'1', '2'})


if __name__ == '__main__':
    unittest.main()
