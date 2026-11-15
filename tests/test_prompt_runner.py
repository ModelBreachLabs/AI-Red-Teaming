import csv
import json
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from tools import prompt_runner


class PromptRunnerTests(unittest.TestCase):
    def test_default_output_name_depends_on_cookie_presence(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "injection_simplified_50.csv"
            input_path.write_text("id,technique,prompt\n1,TEST,hello\n", encoding="utf-8")
            parser = prompt_runner.build_parser()

            for extra_args, expected in (
                ([], "injection_simplified_50_output.csv"),
                (["-c", "session=secret"], "injection_simplified_50_output_authenticated.csv"),
            ):
                args = parser.parse_args(["30", str(input_path), *extra_args])
                prompt_runner.validate_args(args, parser)
                self.assertEqual(Path(args.output).name, expected)

    def test_explicit_output_path_is_preserved_with_cookie(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "prompts.csv"
            output_path = Path(directory) / "my-results.csv"
            input_path.write_text("id,technique,prompt\n1,TEST,hello\n", encoding="utf-8")
            parser = prompt_runner.build_parser()
            args = parser.parse_args([
                "30", str(input_path), "-c", "session=secret", "-o", str(output_path)
            ])

            prompt_runner.validate_args(args, parser)

            self.assertEqual(args.output, str(output_path))

    def test_read_prompts_supports_bom_and_multiline_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "prompts.csv"
            input_path.write_text(
                "\ufeffid,technique,prompt\n1,CANARY,\"first line\nsecond line\"\n",
                encoding="utf-8",
            )

            self.assertEqual(
                prompt_runner.read_prompts(str(input_path))[0]["prompt"].replace("\r\n", "\n"),
                "first line\nsecond line",
            )

    def test_read_prompts_rejects_malformed_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "prompts.csv"
            input_path.write_text("id,technique,prompt\n1,TEST\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "column count"):
                prompt_runner.read_prompts(str(input_path))

    def test_classify_error_validates_success_response_shape(self):
        self.assertEqual(
            prompt_runner.classify_error(True, {"success": True, "response": "ok"}, 200),
            ("", ""),
        )
        self.assertEqual(
            prompt_runner.classify_error(True, {"success": True}, 200),
            ("RESPONSE_FORMAT", "Successful JSON response must contain a text 'response' field"),
        )
        self.assertEqual(
            prompt_runner.classify_error(False, {"error": "denied"}, 403),
            ("ACCESS_DENIED", "denied"),
        )

    @mock.patch.object(prompt_runner.requests, "post")
    def test_send_chat_message_maps_request_errors_and_propagates_unexpected_errors(self, post):
        post.side_effect = prompt_runner.requests.exceptions.Timeout
        self.assertEqual(
            prompt_runner.send_chat_message("https://example.test/chat", "hello")[1]["_error_type"],
            "TIMEOUT",
        )

        post.side_effect = RuntimeError("unexpected bug")
        with self.assertRaisesRegex(RuntimeError, "unexpected bug"):
            prompt_runner.send_chat_message("https://example.test/chat", "hello")

    def test_worker_failure_is_saved_and_does_not_stall_run(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "results.csv"
            prompts = [{"id": "1", "technique": "TEST", "prompt": "hello"}]
            with mock.patch.object(prompt_runner, "send_chat_message",
                                   side_effect=RuntimeError("worker failed")):
                completed = prompt_runner.test_prompts(
                    "http://localhost/chat", prompts, 60000, str(output_path), max_workers=1
                )

            self.assertTrue(completed)
            with output_path.open(newline="", encoding="utf-8") as results:
                row = next(csv.DictReader(results))
            self.assertEqual(row["error_type"], "WORKER_ERROR")
            self.assertIn("worker failed", row["response"])

    def test_worker_loop_crash_fails_run_instead_of_waiting_forever(self):
        class FailingQueue(queue.Queue):
            def get(self, *args, **kwargs):
                raise RuntimeError("worker loop failed")

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "results.csv"
            prompts = [{"id": "1", "technique": "TEST", "prompt": "hello"}]
            queues = [FailingQueue(), queue.Queue(), queue.Queue()]
            with mock.patch.object(prompt_runner.queue, "Queue", side_effect=queues):
                with self.assertRaisesRegex(RuntimeError, "worker loop failed"):
                    prompt_runner.test_prompts(
                        "http://localhost/chat", prompts, 60000, str(output_path), max_workers=1
                    )

            self.assertTrue(output_path.is_file())

    def test_existing_results_are_overwritten_without_creating_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "results.csv"
            output_path.write_text("previous results\n", encoding="utf-8")
            prompts = [{"id": "1", "technique": "TEST", "prompt": "hello"}]
            success = (True, {"success": True, "response": "hello"}, 200)

            with mock.patch.object(prompt_runner, "send_chat_message", return_value=success):
                self.assertTrue(prompt_runner.test_prompts(
                    "https://user:secret@example.test/chat?token=private",
                    prompts,
                    60000,
                    str(output_path),
                    timeout=30,
                    max_workers=1,
                ))

            self.assertEqual(sorted(path.name for path in Path(directory).iterdir()),
                             ["results.csv"])
            with output_path.open(newline="", encoding="utf-8") as results:
                row = next(csv.DictReader(results))
            self.assertEqual(row["endpoint"], "https://example.test/chat")
            self.assertNotIn("secret", row["endpoint"])
            self.assertNotIn("private", row["endpoint"])
            self.assertEqual(row["requests_per_minute"], "60000")
            self.assertEqual(row["repeat_count"], "1")
            self.assertEqual(row["timeout_seconds"], "30")
            self.assertEqual(row["max_workers"], "1")
            self.assertTrue(row["run_started_at"])

    def test_keyboard_interrupt_returns_partial_run_status(self):
        class InterruptOnceQueue(queue.Queue):
            def __init__(self):
                super().__init__()
                self.interrupted = False

            def get(self, *args, **kwargs):
                if not self.interrupted:
                    self.interrupted = True
                    raise KeyboardInterrupt
                return super().get(*args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "results.csv"
            prompts = [{"id": "1", "technique": "TEST", "prompt": "hello"}]
            queues = [queue.Queue(), InterruptOnceQueue(), queue.Queue()]
            with mock.patch.object(prompt_runner.queue, "Queue", side_effect=queues):
                completed = prompt_runner.test_prompts(
                    "http://localhost/chat", prompts, 60000, str(output_path), max_workers=1
                )

            self.assertFalse(completed)
            self.assertTrue(output_path.is_file())

    def test_completion_queued_during_interrupt_is_saved(self):
        class InterruptAfterQueueGet(queue.Queue):
            def __init__(self):
                super().__init__()
                self.interrupted = False

            def get(self, *args, **kwargs):
                item = super().get(*args, **kwargs)
                if not self.interrupted:
                    self.interrupted = True
                    self.put(item)
                    raise KeyboardInterrupt
                return item

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "results.csv"
            prompts = [{"id": "1", "technique": "TEST", "prompt": "hello"}]
            success = (True, {"success": True, "response": "hello"}, 200)
            queues = [queue.Queue(), InterruptAfterQueueGet(), queue.Queue()]
            with mock.patch.object(prompt_runner.queue, "Queue", side_effect=queues):
                with mock.patch.object(prompt_runner, "send_chat_message", return_value=success):
                    completed = prompt_runner.test_prompts(
                        "http://localhost/chat", prompts, 60000, str(output_path), max_workers=1
                    )

            self.assertFalse(completed)
            with output_path.open(newline="", encoding="utf-8") as results:
                row = next(csv.DictReader(results))
            self.assertEqual(row["response"], "hello")

    def test_cli_successful_request_exits_cleanly(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                size = int(self.headers["Content-Length"])
                request = json.loads(self.rfile.read(size))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "response": request["message"],
                }).encode("utf-8"))

            def log_message(self, _format, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                input_path = Path(directory) / "prompts.csv"
                output_path = Path(directory) / "results.csv"
                input_path.write_text("id,technique,prompt\n1,TEST,hello\n", encoding="utf-8")
                result = subprocess.run(
                    [
                        sys.executable,
                        str(Path(prompt_runner.__file__).resolve()),
                        "60000",
                        str(input_path),
                        "--url",
                        f"http://127.0.0.1:{server.server_port}/chat",
                        "--output",
                        str(output_path),
                        "--max-workers",
                        "1",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn("NameError", result.stderr)
                with output_path.open(newline="", encoding="utf-8") as results:
                    row = next(csv.DictReader(results))
                self.assertEqual(row["response"], "hello")
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
