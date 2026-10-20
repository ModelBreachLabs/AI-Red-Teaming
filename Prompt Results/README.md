# Test Results

The prompt tester saves results here by default using `<dataset_name>_output.csv`.

Example: `tools/prompts/direct_injection.csv` produces `Prompt Results/direct_injection_output.csv`.

The path is anchored to the repository root. Before replacing an existing output, the tester preserves it beside the output as `<output_stem>_backup_<timestamp>.csv`. A failed backup stops the run before requests are sent. Use `-o` to choose a separate filename or directory for another run or authentication state.

```bash
python3 tools/prompt_tester.py 10 tools/prompts/direct_injection.csv
python3 tools/prompt_tester.py 10 tools/prompts/direct_injection.csv -c "<cookie>" -o "Prompt Results/direct_injection_authenticated_output.csv"
```

Result CSVs are generated locally when tests run.

The injection judge overwrites the selected CSV with judged results. It creates no backup or separate judged file; atomic checkpoints retain progress in that same CSV.
