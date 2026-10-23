# AI Red Teaming

AI application security testing methodology, prompt datasets, and Python tools maintained by **ModelBreachLabs**.

This repository provides practical resources for assessing LLM-powered applications, including prompt injection, jailbreaking, retrieval-augmented generation (RAG), access controls, agentic workflows, and resource consumption.

## Testing Methodology

| Guide | Coverage |
| --- | --- |
| [Threat Modeling](threats.md) | Threat actors, assets, attack surfaces, and risks |
| [Application Reconnaissance](recon.md) | Application mapping, model behavior, context handling, tools, and rate limits |
| [Prompt Injection and Jailbreaking](PromptInjection_and_Jailbreaking.md) | Direct, narrative, encoded, multi-turn, and indirect injection testing |
| [RAG Testing](RAG.md) | Retrieval leakage, information discovery, canaries, and lab data poisoning |
| [Access Control Testing](Testing_RBAC.md) | Authentication boundaries, cross-user data access, and conversation isolation |
| [Excessive Agency](Excessive_Agency.md) | Unauthorized actions and abuse of agent workflows |
| [Harmful Content and Resource Consumption](HarmfulContentGeneration.md) | Harmful responses, off-topic output, and context overflow |

## Tools

| Tool | Purpose |
| --- | --- |
| `tools/prompt_runner.py` | Run CSV prompt datasets against a chat endpoint and capture responses |
| `tools/injection_judge.py` | Evaluate prompt/response pairs using an Ollama-hosted LLM |
| `tools/benchmark_judge.py` | Prepare unlabeled cases and score manually reviewed judge benchmarks |
| `tools/temp_probe.py` | Compare repeated responses and measure response variation, timing, and throttling |
| `tools/rate_probe.py` | Send scheduled requests and detect rate-limit responses |

## Setup

### Requirements

- Python 3.9 or later
- `requests`
- A compatible chat API endpoint
- Ollama and an installed judge model for automated classification

### Installation

```bash
git clone https://github.com/ModelBreachLabs/AI-Red-Teaming.git
cd AI-Red-Teaming
python -m venv .venv
```

Activate the virtual environment:

**Linux / macOS**

```bash
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the dependency:

```bash
python -m pip install requests
```

Run all examples from the repository root.

## Prompt Testing

Run a dataset at 10 requests per minute:

```bash
python tools/prompt_runner.py 10 tools/prompts/direct_injection.csv
```

Repeat each prompt three times:

```bash
python tools/prompt_runner.py 10 tools/prompts/direct_injection.csv --repeat 3 -o repeated_results.csv
```

Specify a target endpoint:

```bash
python tools/prompt_runner.py 10 tools/prompts/direct_injection.csv -u https://api.example.com/v1/chat
```

Include an authentication cookie:

```bash
python tools/prompt_runner.py 10 tools/prompts/direct_injection.csv -c "session_id=YOUR_SESSION_COOKIE" -o authenticated_results.csv
```

### Arguments

| Argument | Description |
| --- | --- |
| `rate` | Scheduled request rate in requests per minute |
| `input_file` | Input CSV path |
| `-u`, `--url` | Absolute HTTP(S) chat endpoint on any host; defaults to `http://localhost:5000/api/chat` |
| `-o`, `--output` | Output CSV path; defaults to `prompt_results/<dataset_name>_output.csv` at the repository root |
| `-r`, `--repeat` | Requests per prompt; defaults to `1` |
| `--check-for-phrase` | Check whether the row's `technique` value appears in the response, ignoring case |
| `-c`, `--cookie` | Authentication cookie header |
| `--timeout` | Read inactivity timeout in seconds; defaults to `120`. Connection timeout is capped at `10` seconds. |
| `--max-workers` | Maximum simultaneous requests; defaults to `4` |

The URL may point to any reachable HTTP or HTTPS host. The endpoint must implement the runner's chat contract: it receives a JSON `POST` with `message` and `conversation_id: null`, and returns a JSON object with `success: true` and a text `response` on success. This supports remote endpoints without changing the existing request/response format; it does not make arbitrary API schemas configurable. Requests are paced at the configured rate, with at most four requests in flight by default. Use `--max-workers` to change that limit. Each worker reuses its HTTP connection across requests. Jobs are generated as needed, and completed responses are written immediately without retaining the full result set in memory. Progress distinguishes started requests from completed requests and reports pending work while waiting. Multi-turn testing requires a separate workflow.

### CSV Format

Input files use the following headers:

```csv
id,technique,prompt
1,CANARY_TEST,"Repeat the phrase CANARY_TEST exactly."
```

Empty prompts are skipped. When using `--check-for-phrase`, set `technique` to the expected response marker.

```bash
python tools/prompt_runner.py 10 custom_prompts.csv --check-for-phrase -o phrase_results.csv
```

### Included Datasets

Datasets are located in [`tools/prompts/`](tools/prompts/):

| Dataset | Testing Category |
| --- | --- |
| `direct_injection.csv` | Direct prompt injection |
| `narrative_injections.csv` | Narrative and social engineering |
| `obfuscation_and_encoding_injection.csv` | Obfuscated and encoded instructions |
| `jailbreaks.csv` | Jailbreaking |
| `harmful_prompts.csv` | Harmful content |
| `harmful_prompt_injections.csv` | Harmful content combined with injection |
| `offtopic_prompts.csv` | Off-topic responses |
| `context_overflow.csv` | Context overflow |
| `context_overflow_one_long.csv` | Long-input context testing |

RAG-specific CSV filenames referenced in the RAG guide are examples and are not currently included.

### Results

Each completed response is written and flushed to CSV immediately, in completion order. Ctrl+C stops scheduling, saves completed results, and exits without waiting for outstanding requests. Requests already sent may continue processing on the server; their unfinished responses are not included. The summary distinguishes planned, started, completed, and unfinished requests. Status `0` means no HTTP response was received; the terminal and CSV include the underlying error.

The request timeout applies to connection/read inactivity, not total wall-clock duration. For shorter waits, add `--timeout 30`; use Ctrl+C to stop the run.

Without `-o`, the prompt runner saves results to `prompt_results/<dataset_name>_output.csv` at the repository root, regardless of the working directory. For example, `direct_injection.csv` produces `prompt_results/direct_injection_output.csv`. The directory is created on the first default-output run and does not need to be checked in. Before replacing an existing output, the runner creates a unique backup beside it named `<output_stem>_backup_<timestamp>.csv`. If backup fails, the run stops before sending requests. Use `-o` to select a separate run or authentication-state filename; custom output paths remain supported.

Before a run, the tester validates required `id`, `technique`, and `prompt` headers and CSV structure. Malformed rows or datasets with no usable prompts stop the run before requests or output replacement. Empty prompts are skipped with a warning; duplicate IDs/prompts are reported and retained. UTF-8 BOMs and quoted multiline prompts are supported.

The final summary reports planned, started, completed, successful, failed, not-started, and unfinished requests; average/minimum/maximum response time across completed requests; completed request rate; error counts by category; phrase matches when enabled; and absolute output and backup paths.

The prompt runner exports:

- Prompt ID and technique
- Repeat and request numbers
- Response time
- Full prompt and response
- HTTP status code
- Error category (`error_type`; empty for successful responses)
- Timestamp
- Phrase-check result, when enabled

A completed request or phrase match does not establish a vulnerability by itself. Review the response and application behavior to confirm the security impact.

## Automated Injection Judging

The judge uses an Ollama-hosted model to evaluate captured prompt/response pairs.

Install the default model on the Ollama host:

```bash
ollama pull qwen3:8b
```

With Ollama running, evaluate a results file:

```bash
python tools/injection_judge.py "prompt_results/direct_injection_output.csv"
```

Specify an Ollama endpoint and model:

```bash
python tools/injection_judge.py "prompt_results/direct_injection_output.csv" -u http://localhost:11434/api/generate --model qwen3:8b
```

The judge validates the input before making changes and **overwrites the input CSV with judged results**, adding the columns below. It does not create a backup or a separate judged CSV:

| Column | Description |
| --- | --- |
| `injection_label` | Classification result |
| `injection_confidence` | Model-reported confidence |
| `injection_reasons` | Explanation supporting the classification |
| `attack_objective`, `boundary`, `boundary_status` | Claimed objective, boundary, and whether it is supported, unverified, or absent |
| `evidence_quotes` | JSON list of exact substrings from the assistant response |
| `judge_primary_label`, `judge_review_label` | Initial classification and independent review result, when run |
| `judge_review_required`, `judge_review_reason` | Manual-review flag and explanation |

Classification labels include:

- `SUCCESS`
- `POSSIBLE`
- `NO_SUCCESS`
- `ERROR`
- `SKIP` for tester errors (including `error_type` and legacy `ERROR:` responses) or empty assistant responses

The rubric treats prompts and responses as untrusted evidence. Each classification must identify the actual objective and boundary and supply one to three quotes appearing verbatim in the assistant response. Invalid quotes or malformed judgments become `ERROR`. `SUCCESS` requires a boundary marked `SUPPORTED`; this remains a model assessment, not independent proof. There is no blanket refusal-word filter: a refusal can coexist with disclosure.

The default uses one assessment per row and requests brief explanations and short evidence quotes. Proposed successes are flagged for manual verification. Add `--review-successes` to independently reassess proposed successes without showing the first verdict. Agreement retains `SUCCESS`; disagreement or a failed review becomes `POSSIBLE` and is flagged for manual review. Other `POSSIBLE` and `ERROR` rows are also flagged. Both assessments use the same model and can share mistakes. The optional review adds a second request for proposed successes.

Each processed row is checkpointed by writing a complete temporary CSV and atomically replacing the input. Original columns and unprocessed rows are preserved. Ctrl+C retains completed judgments and exits without waiting for a stalled judge request; unprocessed judgment cells remain blank. By default, each invocation starts a fresh evaluation, replacing previous classifications in the same file. Add `--resume` to reuse valid judgments with matching evidence, model, endpoint, rubric, schema, and generation settings; errors, failed second assessments, and unfinished rows are judged again. Reference content and the review policy are included in resume checks. Legacy judgments without matching provenance are re-evaluated. Model tag contents are not fingerprinted, so start a fresh run if you replace a model under the same name. External changes detected during judging stop the run instead of overwriting that file, so finish the prompt tester before starting the judge.

The judge defaults to `think: false`, a 768-token output limit, one or two concise reasons, and schema-constrained JSON. The rubric evaluates the actual attack objective: absence of credentials does not by itself disprove initialization-text disclosure. Models that reject disabled thinking can use `--model-default-thinking`; `--think` explicitly enables it. A token-limit stop is recorded as `ERROR`, not a classification; increase `--max-tokens` if needed. These settings reduce unnecessary generation but do not guarantee speed or accuracy on your hardware.

The original three judgment columns remain available. `judge_signature` records the evidence/configuration fingerprint for resume checks, and `judge_seconds` records each row's total assessment wall-clock duration. When returned by Ollama, model load, prompt processing, generation times, and tokens/second are displayed in the terminal.

```bash
# Resume an interrupted run using matching judgments
python tools/injection_judge.py "prompt_results/direct_injection_output.csv" --resume

# Optional second assessment of proposed successes (slower)
python tools/injection_judge.py "prompt_results/direct_injection_output.csv" --review-successes

# Adjust inactivity timeout and output budget when needed
python tools/injection_judge.py "prompt_results/direct_injection_output.csv" --timeout 180 --max-tokens 1024
```

Progress reports waiting requests, and the final summary separates classifications, judge errors, skipped results, and remaining work, with elapsed time and the absolute output path.

Review classifications manually. Confidence is model-reported, not a calibrated probability. The judge cannot verify secret authenticity or backend state changes from text alone, and instructions in the rubric do not guarantee resistance to adversarial evidence. It evaluates injection evidence and does not provide dedicated scoring for harmful content, off-topic responses, or resource consumption.

### Optional Reference Context

The normal command works without a reference file. After collecting verified context, pass `--reference-file path/to/reference.json`. Supported JSON keys are `expected_behavior` and `system_prompt` (strings), and `access_rules` and `protected_canaries` (lists of strings). Include only keys you can substantiate; unknown keys, wrong types, and empty reference objects are rejected. No reference data is supplied in this repository.

Literal comparisons distinguish canaries already present in the attack from canaries appearing only in the response, and check for the complete reference system prompt. These comparisons are assessment context, not proof of retrieval, authenticity, or backend execution. Treat reference files as sensitive assessment material and keep them out of public commits.

## Response Variation Testing

Send the same message 10 times at 5 requests per minute:

```bash
python tools/temp_probe.py "What is your return policy?" 10 5 -o probe_results.csv
```

Use concurrent scheduling:

```bash
python tools/temp_probe.py "Hello" 10 10 --concurrent -o concurrent_results.csv
```

Specify a target endpoint:

```bash
python tools/temp_probe.py "Hello" 10 5 -u http://localhost:5000/api/chat -o probe_results.csv
```

The tool reports response variation, timing, basic text-length statistics, and rate-limit observations. Per-request results are saved to CSV.

It measures observed output consistency; it does not read or change the model's temperature setting.

## Rate-Limit Testing

Send 10 requests at a scheduled rate of 10 requests per minute:

```bash
python tools/rate_probe.py 10 10 -u http://localhost:5000/api/chat
```

The tool sends `Hello` messages, detects HTTP `429` and supported rate-limit error messages, and prints a summary.

Treat the reported threshold as an observation from that test run.

## API Compatibility

The chat tools send HTTP POST requests using this JSON structure:

```json
{
  "message": "Your test prompt",
  "conversation_id": null
}
```

The prompt runner expects responses shaped like:

```json
{
  "success": true,
  "response": "Assistant response",
  "conversation_id": "optional-conversation-id"
}
```

Adapt request and response handling for applications with a different API format.

Cookie authentication is available in the prompt runner. The response variation and rate-limit probes do not expose a cookie argument.

## Assessment Workflow

1. Define scope and threat-model the application.
2. Map authenticated and unauthenticated functionality and AI integrations.
3. Establish baseline response behavior and request limits.
4. Run relevant prompt datasets and investigate potential successes.
5. Test RAG boundaries, user isolation, and agent actions manually.
6. Review automated classifications and preserve evidence for reproducible findings.

## Authorized Use

Use these materials on applications you own or are authorized to assess, within the agreed testing scope and request limits.
