#!/usr/bin/env python3
"""
Prompt Tester - Test multiple prompts and capture their responses
Reads prompts from a file and sends them to the chat endpoint
"""

import argparse
import csv
import json
import math
import queue
import requests
import time
import threading
from datetime import datetime
from pathlib import Path


def send_chat_message(url: str, message: str, cookie: str = None, timeout: float = 120) -> tuple[bool, dict, int]:
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
        
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=(min(10.0, timeout), timeout)
        )
        
        status_code = response.status_code
        
        # Try to parse JSON response
        try:
            data = response.json()
        except json.JSONDecodeError:
            data = {"error": "Invalid JSON response", "raw": response.text[:200]}
        
        return (response.ok, data, status_code)
    
    except requests.exceptions.Timeout:
        return (False, {"error": "Request timeout"}, 0)
    except requests.exceptions.ConnectionError:
        return (False, {"error": "Connection error"}, 0)
    except Exception as e:
        return (False, {"error": str(e)}, 0)


def read_prompts(input_file: str) -> list[dict]:
    """
    Read prompts from CSV file with id, technique, and prompt columns
    
    Args:
        input_file: Path to CSV file containing prompts
        
    Returns:
        List of dictionaries with 'id', 'technique', and 'prompt' keys
    """
    prompts = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('prompt', '').strip():  # Skip rows with empty prompts
                prompts.append({
                    'id': row.get('id', ''),
                    'technique': row.get('technique', ''),
                    'prompt': row['prompt'].strip()
                })
    return prompts


def test_prompts(url: str, prompts: list[dict], requests_per_minute: float, output_file: str, repeat: int = 1, check_for_phrase: bool = False, cookie: str = None, timeout: float = 120, max_workers: int = 4):
    """Run rate-paced requests, saving each completed result immediately."""
    delay = 60.0 / requests_per_minute
    jobs = [(prompt, number) for prompt in prompts for number in range(1, repeat + 1)]
    completions = queue.Queue()
    stop = threading.Event()
    results = []
    launched = 0
    active = 0
    successful_requests = 0
    interrupted = False
    start_time = time.monotonic()
    next_launch = start_time
    last_progress = start_time

    print(f"Prompt Tester - Multiple Prompts Test")
    print(f"Endpoint:       {url}")
    print(f"Total Requests: {len(jobs)}")
    print(f"Max Rate:       {requests_per_minute} req/min")
    print(f"Max In Flight:  {max_workers}")
    print(f"Request timeout:{timeout:g}s (connect/read inactivity)")
    print(f"Output:         {output_file}")

    def worker(request_num, prompt_data, repeat_num):
        started = time.monotonic()
        try:
            outcome = send_chat_message(url, prompt_data['prompt'], cookie, timeout)
        except Exception as exc:
            outcome = (False, {'error': str(exc)}, 0)
        if not stop.is_set():
            completions.put((request_num, prompt_data, repeat_num,
                             (time.monotonic() - started) * 1000, outcome))

    fieldnames = ['id', 'technique', 'repeat_number', 'request_number',
                  'response_time_ms', 'prompt', 'response', 'status_code', 'timestamp']
    if check_for_phrase:
        fieldnames.append('phrase_check')

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', newline='', encoding='utf-8') as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        output.flush()

        def record(completion):
            nonlocal active, successful_requests
            request_num, prompt_data, repeat_num, elapsed, outcome = completion
            active -= 1
            http_ok, data, status_code = outcome
            if not isinstance(data, dict):
                data = {'error': 'Expected a JSON object from the chat endpoint'}
            success = http_ok and bool(data.get('success'))
            phrase_check = 'N/A'
            if success:
                response_text = str(data.get('response', ''))
                successful_requests += 1
                message = f"OK ({elapsed:.0f}ms)"
                if check_for_phrase and response_text and prompt_data['technique']:
                    phrase_check = ('SUCCESS' if prompt_data['technique'].lower()
                                    in response_text.lower() else 'NO_SUCCESS')
            else:
                error = str(data.get('error') or 'Unknown error')
                response_text = f"ERROR: {error}"
                message = f"Error (status: {status_code}): {error}"
            row = {
                'id': prompt_data['id'], 'technique': prompt_data['technique'],
                'repeat_number': repeat_num, 'request_number': request_num,
                'response_time_ms': elapsed, 'prompt': prompt_data['prompt'],
                'response': response_text, 'status_code': status_code,
                'timestamp': datetime.now().isoformat()
            }
            if check_for_phrase:
                row['phrase_check'] = phrase_check
            writer.writerow(row)
            output.flush()
            results.append(row)
            print(f"Completed {len(results)}/{len(jobs)} - Request {request_num}: {message}",
                  flush=True)

        try:
            while launched < len(jobs) or active:
                now = time.monotonic()
                if launched < len(jobs) and active < max_workers and now >= next_launch:
                    prompt_data, repeat_num = jobs[launched]
                    request_num = launched + 1
                    thread = threading.Thread(
                        target=worker, args=(request_num, prompt_data, repeat_num),
                        daemon=True)
                    print(f"Starting {request_num}/{len(jobs)}: "
                          f"#{prompt_data['id']} {prompt_data['technique']} "
                          f"(repeat {repeat_num}/{repeat})", flush=True)
                    thread.start()
                    launched += 1
                    active += 1
                    next_launch = time.monotonic() + delay
                try:
                    wait = 0.1
                    if launched < len(jobs) and active < max_workers:
                        wait = min(wait, max(0.0, next_launch - time.monotonic()))
                    record(completions.get(timeout=wait))
                except queue.Empty:
                    pass
                if active and time.monotonic() - last_progress >= 5:
                    print(f"Progress: {len(results)}/{len(jobs)} completed, "
                          f"{active} in flight, {len(jobs) - launched} not started.",
                          flush=True)
                    last_progress = time.monotonic()
        except KeyboardInterrupt:
            interrupted = True
            stop.set()
            print("\nInterrupted. Saving completed results; outstanding requests "
                  "will not delay exit.", flush=True)
            # Collect results that finished before interruption but were not yet recorded.
            while True:
                try:
                    record(completions.get_nowait())
                except queue.Empty:
                    break
        finally:
            stop.set()
            output.flush()

    total_time = max(time.monotonic() - start_time, 0.000001)
    print("\nTest Results Summary")
    print(f"Planned requests:        {len(jobs)}")
    print(f"Started requests:        {launched}")
    print(f"Completed and saved:    {len(results)}")
    print(f"Successful responses:   {successful_requests}")
    print(f"Failed responses:       {len(results) - successful_requests}")
    print(f"Not completed:          {len(jobs) - len(results)}")
    print(f"Total time:             {total_time:.2f}s")
    if check_for_phrase:
        checked = [row for row in results if row['phrase_check'] != 'N/A']
        matches = sum(row['phrase_check'] == 'SUCCESS' for row in checked)
        print(f"Phrase matches:         {matches}/{len(checked)} checked")
    print(f"{'Partial results' if interrupted else 'Results'} saved to {output_file}")
    return not interrupted


def main():
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
  %(prog)s 20 prompts.csv -u http://example.com/api/chat
  
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
    parser.add_argument('-u', '--url', type=str, default='http://localhost:5000/api/chat',
                        help='Chat API endpoint URL (default: http://localhost:5000/api/chat)')
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='Output CSV path (default: repository-root Documentation/<dataset_name>_output.csv)')
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

    args = parser.parse_args()
    
    # Validate arguments
    if not math.isfinite(args.rate) or args.rate <= 0:
        parser.error("rate must be positive")
    if args.repeat <= 0:
        parser.error("repeat must be positive")
    
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("timeout must be a positive finite number")
    if args.max_workers <= 0:
        parser.error("max-workers must be positive")

    # Check if input file exists
    if not Path(args.input_file).exists():
        parser.error(f"Input file not found: {args.input_file}")
    
    # Anchor default results to the repository, independent of the working directory.
    if args.output is None:
        documentation_dir = Path(__file__).resolve().parent.parent / 'Documentation'
        args.output = str(documentation_dir / f'{Path(args.input_file).stem}_output.csv')
    
    try:
        # Read prompts from file
        prompts = read_prompts(args.input_file)
        if not prompts:
            print("Error: No prompts found in input file")
            return
        
        print(f"Loaded {len(prompts)} prompts from {args.input_file}\n")
        
        # Create the destination before sending any requests.
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)

        # Run the test
        completed = test_prompts(args.url, prompts, args.rate, args.output, args.repeat,
                                 args.check_for_phrase, args.cookie, args.timeout, args.max_workers)
        if not completed:
            raise SystemExit(130)
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
