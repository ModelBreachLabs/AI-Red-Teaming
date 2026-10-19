# Testing for Harmful and Wasteful Output

Run commands from the repository root (`AI-Red-Teaming/`). Replace `<cookie>` with your lab session cookie. The default endpoint is `http://localhost:5000/api/chat`; add `-u URL` if your lab uses another endpoint.

Use the CSV responses and application observations to validate these tests. The injection judge does not evaluate content policy, application scope, or resource consumption.

## Testing for Harmful Output

```bash
python3 tools/prompt_tester.py 15 tools/prompts/harmful_prompts.csv --check-for-phrase
python3 tools/prompt_tester.py 15 tools/prompts/harmful_prompts.csv --check-for-phrase -c "<cookie>"
```

- Define the application's expected content policy before testing.
- Use `phrase_check` to find responses containing the dataset's expected phrases. Review the full response: quoting a phrase in a refusal can still produce a match.
- Confirm whether the response violates the application's policy. A phrase match alone is not a confirmed finding.
- Record the prompt, response, authentication state, expected behavior, and demonstrated impact.

## Testing for Off-Topic Content

```bash
python3 tools/prompt_tester.py 15 tools/prompts/offtopic_prompts.csv
python3 tools/prompt_tester.py 15 tools/prompts/offtopic_prompts.csv -c "<cookie>"
```

- Establish the application's intended scope and expected handling of unrelated requests.
- Review whether each response fulfills the off-topic request, refuses it, or redirects to the supported scope.
- Dataset technique names are category labels, so phrase matching is not used here.
- Record reproducible deviations from the expected scope and explain their impact.

## Testing for Unbounded Consumption

```bash
python3 tools/prompt_tester.py 15 tools/prompts/context_overflow.csv
python3 tools/prompt_tester.py 15 tools/prompts/context_overflow.csv -c "<cookie>"
```

- Establish a baseline using a short request, then compare long-input response times, HTTP status codes, and errors under comparable conditions.
- Check whether input-size, output-size, timeout, quota, and rate limits are enforced. Capture token usage, cost, or server resource metrics when available.
- Long responses or increased latency alone do not prove unbounded consumption. Confirm which expected limit is missing or bypassed and document the measured effect.
- Phrase matching does not measure resource usage and is not used here.

## Stacking Prompt Injection and Harmful Content Generation

Combine previously validated injection techniques with content-policy tests. Confirm both the instruction-boundary bypass and the resulting policy violation separately, preserving the prompt, response, and application evidence.
