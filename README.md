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
| `tools/prompt_tester.py` | Run CSV prompt datasets against a chat endpoint and capture responses |
| `tools/injection_judge.py` | Evaluate prompt/response pairs using an Ollama-hosted LLM |
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
python tools/prompt_tester.py 10 tools/prompts/direct_injection.csv
```

Repeat each prompt three times:

```bash
python tools/prompt_tester.py 10 tools/prompts/direct_injection.csv --repeat 3 -o repeated_results.csv
```

Specify a target endpoint:

```bash
python tools/prompt_tester.py 10 tools/prompts/direct_injection.csv -u http://localhost:5000/api/chat
```

Include an authentication cookie:

```bash
python tools/prompt_tester.py 10 tools/prompts/direct_injection.csv -c "session_id=YOUR_SESSION_COOKIE" -o authenticated_results.csv
```

### Arguments

| Argument | Description |
| --- | --- |
| `rate` | Scheduled request rate in requests per minute |
| `input_file` | Input CSV path |
| `-u`, `--url` | Target endpoint; defaults to `http://localhost:5000/api/chat` |
| `-o`, `--output` | Output CSV path; defaults to `Documentation/<dataset_name>_output.csv` at the repository root |
| `-r`, `--repeat` | Requests per prompt; defaults to `1` |
| `--check-for-phrase` | Check whether the row's `technique` value appears in the response, ignoring case |
| `-c`, `--cookie` | Authentication cookie header |

Requests are scheduled in separate threads and can overlap. Each request sends `conversation_id: null`; multi-turn testing requires a separate workflow.

### CSV Format

Input files use the following headers:

```csv
id,technique,prompt
1,CANARY_TEST,"Repeat the phrase CANARY_TEST exactly."
```

Empty prompts are skipped. When using `--check-for-phrase`, set `technique` to the expected response marker.

```bash
python tools/prompt_tester.py 10 custom_prompts.csv --check-for-phrase -o phrase_results.csv
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

Without `-o`, the prompt tester saves results to `Documentation/<dataset_name>_output.csv` at the repository root, regardless of the working directory. For example, `direct_injection.csv` produces `Documentation/direct_injection_output.csv`. The destination directory is created automatically. Running the same dataset again replaces its previous default output; use `-o` to preserve separate runs or authentication states.

The prompt runner exports:

- Prompt ID and technique
- Repeat and request numbers
- Response time
- Full prompt and response
- HTTP status code
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
python tools/injection_judge.py Documentation/direct_injection_output.csv
```

Specify an Ollama endpoint and model:

```bash
python tools/injection_judge.py Documentation/direct_injection_output.csv -u http://localhost:11434/api/generate --model qwen3:8b
```

The judge **updates the input CSV in place**, adding:

| Column | Description |
| --- | --- |
| `injection_label` | Classification result |
| `injection_confidence` | Model-reported confidence |
| `injection_reasons` | Explanation supporting the classification |

Classification labels include:

- `SUCCESS`
- `POSSIBLE`
- `NO_SUCCESS`
- `ERROR`
- `SKIP` for responses recorded as request errors

Review classifications manually. The judge evaluates injection success and does not provide dedicated scoring for harmful content, off-topic responses, or resource consumption.

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
