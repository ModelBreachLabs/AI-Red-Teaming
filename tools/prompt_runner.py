#!/usr/bin/env python3
"""
Prompt Tester - Test multiple prompts and capture their responses
Reads prompts from a file and sends them to the chat endpoint
"""

import argparse
import csv
import math
import queue
import requests
from collections import Counter
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit


Prompt = dict[str, str]
ApiResult = tuple[bool, dict[str, Any], int]


def validate_api_url(value: str) -> str:
    """Accept HTTP(S) API endpoints on any host."""
    try:
        parsed = urlsplit(value)
        if (parsed.scheme.lower() not in {'http', 'https'}
                or not parsed.hostname
                or any(character.isspace() for character in value)):
            raise ValueError
        parsed.port
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "URL must be an absolute HTTP or HTTPS endpoint with a valid host and port"
        ) from exc
    return value


def redact_endpoint(url: str) -> str:
    """Keep useful endpoint identity without recording URL credentials or query tokens."""
    parsed = urlsplit(url)
    hostname = parsed.hostname or ''
    if ':' in hostname and not hostname.startswith('['):
        hostname = f'[{hostname}]'
    netloc = hostname
    if parsed.port is not None:
        netloc = f'{netloc}:{parsed.port}'
    return urlunsplit((parsed.scheme, netloc, parsed.path, '', ''))


def default_output_path(input_file: str, authenticated: bool = False) -> Path:
    """Build the repository-default output path for the input dataset."""
    results_dir = Path(__file__).resolve().parent.parent / 'prompt_results'
    suffix = '_output_authenticated' if authenticated else '_output'
    return results_dir / f'{Path(input_file).stem}{suffix}.csv'


def send_chat_message(url: str, message: str, cookie: Optional[str] = None, timeout: float = 120,
                      session: Optional[requests.Session] = None) -> ApiResult:
    """
    Send a message to the chat API endpoint
    
    Args:
        url: API endpoint URL
        message: Message to send
        cookie: Optional cookie string for authentication
    
    Returns:
        (success, response_data, status_code)
    """
    try:
        payload = {
            "message": message,
            "conversation_id": None
        }
        
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        
        client = session or requests
        response = client.post(
            url,
            json=payload,
            headers=headers,
            timeout=(min(10.0, timeout), timeout)
        )
        
        status_code = response.status_code
        
        # Try to parse JSON response
        try:
            data = response.json()
        except ValueError:
            data = {"error": "Endpoint returned invalid JSON", "_error_type": "INVALID_JSON"}
        if not isinstance(data, dict):
            data = {"error": "Expected a JSON object from the chat endpoint", "_error_type": "RESPONSE_FORMAT"}
        
        return (response.ok, data, status_code)
    
    except requests.exceptions.Timeout:
        return (False, {"error": "Connection/read inactivity timeout", "_error_type": "TIMEOUT"}, 0)
    except requests.exceptions.SSLError:
        return (False, {"error": "TLS certificate or handshake failed", "_error_type": "TLS_ERROR"}, 0)
    except requests.exceptions.ConnectionError:
        return (False, {"error": "Could not connect to the endpoint, or the connection was lost", "_error_type": "CONNECTION_ERROR"}, 0)
    except requests.exceptions.RequestException as exc:
        return (False, {"error": str(exc), "_error_type": "REQUEST_ERROR"}, 0)


def read_prompts(input_file: str) -> list[Prompt]:
    """Validate the full CSV before requests or output-file changes."""
    prompts = []
    warnings = []
    ids = set()
    texts = set()
    with open(input_file, 'r', newline='', encoding='utf-8-sig') as source:
        reader = csv.DictReader(source, strict=True)
        try:
            headers = reader.fieldnames
            required = {'id', 'technique', 'prompt'}
            if not headers or not required.issubset(headers):
                missing = required - set(headers or [])
                raise ValueError(f"Dataset missing required columns: {', '.join(sorted(missing))}")
            if len(headers) != len(set(headers)):
                raise ValueError("Dataset contains duplicate column headers")
            for row in reader:
                line = reader.line_num
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"Dataset line {line}: column count does not match header")
                prompt = row['prompt'].strip()
                if not prompt:
                    warnings.append(f"line {line}: empty prompt skipped")
                    continue
                prompt_id = row['id']
                if prompt_id in ids:
                    warnings.append(f"line {line}: duplicate ID {prompt_id!r}; retained")
                if prompt in texts:
                    warnings.append(f"line {line}: duplicate prompt; retained")
                if not prompt_id.strip() or not row['technique'].strip():
                    warnings.append(f"line {line}: blank ID or technique")
                ids.add(prompt_id)
                texts.add(prompt)
                prompts.append({'id': prompt_id, 'technique': row['technique'], 'prompt': prompt})
        except csv.Error as exc:
            raise ValueError(f"Invalid CSV near line {reader.line_num}: {exc}") from exc
    if not prompts:
        raise ValueError("Dataset contains no nonempty prompts")
    for warning in warnings:
        print(f"Dataset warning: {warning}")
    return prompts


def classify_error(http_ok: bool, data: dict[str, Any], status_code: int) -> tuple[str, str]:
    """Categorize failures without guessing whether credentials have expired."""
    error = str(data.get('error') or '')
    if status_code == 401:
        return 'AUTHENTICATION', error or 'HTTP 401: authentication required or rejected'
    if status_code == 403:
        return 'ACCESS_DENIED', error or 'HTTP 403: access denied'
    if status_code == 429 or 'rate limit' in error.lower() or 'too many requests' in error.lower():
        return 'RATE_LIMIT', error or 'HTTP 429: too many requests'
    if status_code >= 400:
        return 'HTTP_ERROR', error or f'HTTP {status_code}'
    if data.get('_error_type'):
        return data['_error_type'], error
    if not http_ok:
        return 'REQUEST_ERROR', error or 'Request failed without an HTTP response'
    if 'success' not in data:
        return 'RESPONSE_FORMAT', error or "JSON response is missing the 'success' field"
    if not data.get('success'):
        return 'APPLICATION_ERROR', error or 'Application reported success=false'
    if not isinstance(data.get('response'), str):
        return 'RESPONSE_FORMAT', "Successful JSON response must contain a text 'response' field"
    return '', ''


def test_prompts(url: str, prompts: list[Prompt], requests_per_minute: float, output_file: str,
                 repeat: int = 1, check_for_phrase: bool = False, cookie: Optional[str] = None,
                 timeout: float = 120, max_workers: int = 4) -> bool:
    """Run rate-paced requests, saving each completed result immediately."""
    output_file = str(Path(output_file).expanduser().resolve())
    delay = 60.0 / requests_per_minute
    total_requests = len(prompts) * repeat
    jobs = queue.Queue()
    completions = queue.Queue()
    stop = threading.Event()
    completion_lock = threading.Lock()
    worker_failures = queue.Queue()
    launched = active = completed = successful_requests = 0
    total_response_time = 0.0
    min_response_time = max_response_time = None
    phrase_checks = phrase_matches = 0
    errors = Counter()
    interrupted = False
    start_time = time.monotonic()
    run_started_at = datetime.now().astimezone().isoformat()
    recorded_endpoint = redact_endpoint(url)
    next_launch = start_time
    last_progress = start_time

    print("Prompt Tester - Multiple Prompts Test")
    print(f"Endpoint:       {recorded_endpoint}")
    print(f"Total Requests: {total_requests}")
    print(f"Max Rate:       {requests_per_minute} req/min")
    print(f"Max In Flight:  {max_workers}")
    print(f"Request timeout:{timeout:g}s (connect/read inactivity)")
    print(f"Output:         {output_file}")

    def worker():
        client = None
        initialization_error = None
        current_job = None
        try:
            try:
                client = requests.Session()
            except Exception as exc:
                initialization_error = exc
            while not stop.is_set():
                try:
                    current_job = jobs.get(timeout=0.1)
                except queue.Empty:
                    continue
                if current_job is None:
                    jobs.task_done()
                    return
                request_num, prompt_data, repeat_num = current_job
                if stop.is_set():
                    jobs.task_done()
                    current_job = None
                    return
                started = time.monotonic()
                try:
                    if initialization_error is not None:
                        raise initialization_error
                    outcome = send_chat_message(url, prompt_data['prompt'], cookie, timeout, client)
                except Exception as exc:
                    outcome = (False, {'error': str(exc), '_error_type': 'WORKER_ERROR'}, 0)
                elapsed = (time.monotonic() - started) * 1000
                with completion_lock:
                    if not stop.is_set():
                        completions.put((request_num, prompt_data, repeat_num, elapsed, outcome))
                jobs.task_done()
                current_job = None
        except Exception as exc:
            if current_job is not None:
                request_num, prompt_data, repeat_num = current_job
                failure = (False, {'error': str(exc), '_error_type': 'WORKER_ERROR'}, 0)
                try:
                    with completion_lock:
                        if not stop.is_set():
                            completions.put((request_num, prompt_data, repeat_num, 0, failure))
                finally:
                    jobs.task_done()
            worker_failures.put(exc)
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception as exc:
                    worker_failures.put(exc)

    fieldnames = ['id', 'technique', 'repeat_number', 'request_number',
                  'response_time_ms', 'prompt', 'response', 'status_code', 'timestamp', 'error_type',
                  'run_started_at', 'endpoint', 'requests_per_minute', 'repeat_count',
                  'timeout_seconds', 'max_workers']
    if check_for_phrase:
        fieldnames.append('phrase_check')

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', newline='', encoding='utf-8') as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        output.flush()

        def record(completion):
            nonlocal active, completed, successful_requests
            nonlocal total_response_time, min_response_time, max_response_time
            nonlocal phrase_checks, phrase_matches
            request_num, prompt_data, repeat_num, elapsed, outcome = completion
            active -= 1
            completed += 1
            total_response_time += elapsed
            min_response_time = elapsed if min_response_time is None else min(min_response_time, elapsed)
            max_response_time = elapsed if max_response_time is None else max(max_response_time, elapsed)
            http_ok, data, status_code = outcome
            if not isinstance(data, dict):
                data = {'error': 'Expected a JSON object from the chat endpoint',
                        '_error_type': 'RESPONSE_FORMAT'}
            error_type, error = classify_error(http_ok, data, status_code)
            phrase_check = 'N/A'
            if not error_type:
                response_text = data['response']
                successful_requests += 1
                message = f"OK ({elapsed:.0f}ms)"
                if check_for_phrase and response_text and prompt_data['technique']:
                    phrase_check = ('SUCCESS' if prompt_data['technique'].lower()
                                    in response_text.lower() else 'NO_SUCCESS')
                    phrase_checks += 1
                    phrase_matches += phrase_check == 'SUCCESS'
            else:
                response_text = f"ERROR: {error}"
                message = f"{error_type} (status: {status_code}): {error}"
                errors[error_type] += 1
            row = {
                'id': prompt_data['id'], 'technique': prompt_data['technique'],
                'repeat_number': repeat_num, 'request_number': request_num,
                'response_time_ms': elapsed, 'prompt': prompt_data['prompt'],
                'response': response_text, 'status_code': status_code,
                'timestamp': datetime.now().isoformat(), 'error_type': error_type,
                'run_started_at': run_started_at, 'endpoint': recorded_endpoint,
                'requests_per_minute': requests_per_minute, 'repeat_count': repeat,
                'timeout_seconds': timeout, 'max_workers': max_workers
            }
            if check_for_phrase:
                row['phrase_check'] = phrase_check
            writer.writerow(row)
            output.flush()
            print(f"Completed {completed}/{total_requests} - Request {request_num}: {message}",
                  flush=True)

        workers = [threading.Thread(target=worker, daemon=True) for _ in range(max_workers)]
        for thread in workers:
            thread.start()

        worker_error = None
        try:
            while launched < total_requests or active:
                try:
                    worker_error = worker_failures.get_nowait()
                except queue.Empty:
                    pass
                if worker_error is not None:
                    with completion_lock:
                        stop.set()
                    break
                now = time.monotonic()
                if launched < total_requests and active < max_workers and now >= next_launch:
                    prompt_index, repeat_offset = divmod(launched, repeat)
                    prompt_data = prompts[prompt_index]
                    repeat_num = repeat_offset + 1
                    request_num = launched + 1
                    print(f"Starting {request_num}/{total_requests}: "
                          f"#{prompt_data['id']} {prompt_data['technique']} "
                          f"(repeat {repeat_num}/{repeat})", flush=True)
                    jobs.put((request_num, prompt_data, repeat_num))
                    launched += 1
                    active += 1
                    next_launch = time.monotonic() + delay
                try:
                    wait = 0.1
                    if launched < total_requests and active < max_workers:
                        wait = min(wait, max(0.0, next_launch - time.monotonic()))
                    record(completions.get(timeout=wait))
                except queue.Empty:
                    pass
                if active and time.monotonic() - last_progress >= 5:
                    print(f"Progress: {completed}/{total_requests} completed, "
                          f"{active} in flight, {total_requests - launched} not started.",
                          flush=True)
                    last_progress = time.monotonic()
        except KeyboardInterrupt:
            interrupted = True
            with completion_lock:
                stop.set()
            print("\nInterrupted. Saving completed results; outstanding requests "
                  "will not delay exit.", flush=True)
        finally:
            if interrupted or worker_error is not None:
                while True:
                    try:
                        record(completions.get_nowait())
                    except queue.Empty:
                        break
            if not interrupted and worker_error is None:
                for _ in workers:
                    jobs.put(None)
                for thread in workers:
                    thread.join()
                try:
                    worker_error = worker_failures.get_nowait()
                except queue.Empty:
                    pass
            output.flush()

    total_time = max(time.monotonic() - start_time, 0.000001)
    print("\nTest Results Summary")
    print(f"Planned requests:        {total_requests}")
    print(f"Started requests:        {launched}")
    print(f"Completed and saved:    {completed}")
    print(f"Successful responses:   {successful_requests}")
    print(f"Failed responses:       {completed - successful_requests}")
    print(f"Not started:            {total_requests - launched}")
    print(f"Started, unfinished:    {launched - completed}")
    print(f"Not completed:          {total_requests - completed}")
    print(f"Total time:             {total_time:.2f}s")
    if completed:
        print(f"Response time (all):    avg={total_response_time/completed:.0f}ms, "
              f"min={min_response_time:.0f}ms, max={max_response_time:.0f}ms")
    print(f"Completed rate:         {completed / total_time * 60:.2f} req/min")
    for category, count in sorted(errors.items()):
        print(f"  {category}: {count}")
    if check_for_phrase:
        print(f"Phrase matches:         {phrase_matches}/{phrase_checks} checked")
    partial = interrupted or worker_error is not None
    print(f"{'Partial results' if partial else 'Results'} saved to {output_file}")
    if worker_error is not None:
        raise RuntimeError(f"Worker thread failed unexpectedly: {worker_error}") from worker_error
    return not interrupted


def main():
    parser = build_parser()
    args = parser.parse_args()
    validate_args(args, parser)

    try:
        prompts = read_prompts(args.input_file)
        print(f"Loaded {len(prompts)} prompts from {args.input_file}\n")
        completed = test_prompts(args.url, prompts, args.rate, args.output, args.repeat,
                                 args.check_for_phrase, args.cookie, args.timeout, args.max_workers)
        if not completed:
            raise SystemExit(130)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        raise SystemExit(130)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    except Exception as exc:
        print(f"\nError: {exc}")
        import traceback
        traceback.print_exc()
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser, separate from execution for testability."""
    parser = argparse.ArgumentParser(
        description='Prompt Tester - Test multiple prompts and capture responses',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test prompts from CSV file at 10 req/min
  %(prog)s 10 prompts.csv
  
  # Test prompts at 30 req/min with custom output
  %(prog)s 30 test_prompts.csv -o results.csv
  
  # Test each prompt 3 times to check for non-determinism
  %(prog)s 20 prompts.csv --repeat 3
  
  # Test against custom endpoint
  %(prog)s 20 prompts.csv -u https://api.example.com/v1/chat
  
  # Check if technique phrase appears in responses
  %(prog)s 15 prompts.csv --check-for-phrase
  
  # Test with authentication cookie
  %(prog)s 15 prompts.csv -c "session_id=abc123; auth_token=xyz"

Input file format:
  - CSV file with columns: id, technique, prompt
  - Header row required
  - Example: direct_injection.csv
        """
    )
    parser.add_argument('rate', type=float, help='Maximum request rate in requests per minute')
    parser.add_argument('input_file', type=str, help='Input CSV file with columns: id, technique, prompt')
    parser.add_argument('-u', '--url', type=validate_api_url, default='http://localhost:5000/api/chat',
                        help='HTTP(S) chat API endpoint on any host '
                             '(default: http://localhost:5000/api/chat)')
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='Output CSV path (default: repository-root prompt_results/<dataset_name>_output.csv, '
                             'or <dataset_name>_output_authenticated.csv when --cookie is set)')
    parser.add_argument('-r', '--repeat', type=int, default=1,
                        help='Number of times to repeat each prompt (default: 1)')
    parser.add_argument('--check-for-phrase', action='store_true',
                        help='Check if the technique phrase appears in the response and add phrase_check column')
    parser.add_argument('-c', '--cookie', type=str, default=None,
                        help='Cookie string for authentication (e.g., "session_id=abc123; auth_token=xyz")')

    parser.add_argument('--timeout', type=float, default=120,
                        help='Read inactivity timeout in seconds; connect timeout is capped at 10s (default: 120)')
    parser.add_argument('--max-workers', type=int, default=4,
                        help='Maximum simultaneous requests (default: 4)')
    return parser


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Validate CLI values and paths before reading input or replacing output."""
    if not math.isfinite(args.rate) or args.rate <= 0:
        parser.error("rate must be positive")
    if args.repeat <= 0:
        parser.error("repeat must be positive")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("timeout must be a positive finite number")
    if args.max_workers <= 0:
        parser.error("max-workers must be positive")
    if not Path(args.input_file).is_file():
        parser.error(f"Input file not found: {args.input_file}")

    if args.output is None:
        args.output = str(default_output_path(args.input_file, authenticated=bool(args.cookie)))

    if Path(args.input_file).resolve() == Path(args.output).expanduser().resolve():
        parser.error("output path must not be the input dataset")

if __name__ == '__main__':
    main()
