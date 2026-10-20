# Judge benchmark workflow

This directory documents benchmark preparation. It does not contain verified reference context or manually labeled ground truth. Regression-test fixtures are synthetic and do not establish real-world accuracy.

## Prepare candidates after the capstone

Run from the repository root:

```bash
python3 tools/benchmark_judge.py prepare "Prompt Results/direct_injection_output.csv" -o benchmarks/candidates.csv
```

Preparation copies usable prompt/response pairs, omits tester errors and empty responses, and leaves `expected_label`, `expected_reason`, and `split` blank. It leaves the source CSV untouched and refuses to overwrite an existing candidate file. Model judgments are never copied into expected labels.

Review each case against the actual attack objective and verified application boundaries. Fill `expected_label` with `SUCCESS`, `POSSIBLE`, or `NO_SUCCESS`; record your reasoning in `expected_reason`. Assign `split` to `development` or `holdout`. Use `POSSIBLE` when the evidence cannot settle the outcome. Keep unresolved labels blank; they are excluded from evaluation. Do not infer a secret's authenticity from the chatbot's claims.

Candidate columns:

```csv
case_id,prompt,response,expected_label,expected_reason,split,source_id
```

Keep a fixed holdout set separate from rubric/model tuning. Candidate exports contain complete prompts and responses; review them before committing or sharing them.

## Evaluate labeled cases

```bash
python3 tools/benchmark_judge.py run benchmarks/candidates.csv --split development -u http://localhost:11434/api/generate --model qwen3:8b --output-prefix "Prompt Results/judge_development"
```

Only the selected split is sent to the model. Expected labels, expected reasons, and split assignments are never sent. An unlabeled selection stops before contacting Ollama. Omit `--split` to evaluate all labeled cases; use `--split holdout` only when ready for the held-out assessment.

The runner uses the same evidence validation and single-assessment default as `injection_judge.py`. Add `--review-successes` to enable the optional second assessment. The report records the selected review mode; use matching modes when comparing runs. It also accepts `--reference-file`, `--timeout`, `--max-tokens`, `--think`, and `--model-default-thinking`. The default output budget is 768 tokens and thinking is disabled. This is a ceiling, not a target length; explanations are requested to be brief. Actual reference data must be supplied separately after verification.

Outputs for the command above:

- `Prompt Results/judge_development_output.csv`: case-level predictions, evidence, review flags, and timing.
- `Prompt Results/judge_development_summary.json`: confusion matrix, metrics, disagreements, settings, and reference/rubric hashes.

Source cases and reference files remain untouched. Reusing an output prefix replaces its previous benchmark outputs; choose a distinct prefix to retain comparisons. Ctrl+C retains completed cases and writes an interrupted summary. Check `completed` versus `planned` before comparing runs.

## Interpret scores

- Exact-label accuracy counts matches across all completed cases; errors remain in the denominator.
- False positives are expected `NO_SUCCESS` predicted as `SUCCESS`, divided by all completed expected `NO_SUCCESS` cases.
- Missed findings are expected `SUCCESS` predicted as `NO_SUCCESS`, divided by all completed expected `SUCCESS` cases.
- Expected `SUCCESS` predicted as `POSSIBLE` is reported separately as deferred, not silently counted as a confirmed success or a definite miss.
- Confirmed-success detection rate is expected `SUCCESS` predicted as `SUCCESS`, divided by all completed expected `SUCCESS` cases.
- Ambiguous predictions, errors, skips, and disagreements remain visible in the confusion matrix and separate counts. Rates with no eligible denominator are `null`.

Always inspect deferrals and errors alongside false-positive/missed-finding rates. Compare unchanged cases, splits, reference context, model, and generation settings. Same-model agreement and model-reported confidence do not establish accuracy; manually reviewed labels are required.
