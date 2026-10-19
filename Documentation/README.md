# Test Results

The prompt tester saves results here by default using `<dataset_name>_output.csv`.

Example: `tools/prompts/direct_injection.csv` produces `Documentation/direct_injection_output.csv`.

The path is anchored to the repository root. Running the same dataset again replaces its previous default output. Use `-o` to choose a separate filename or directory for another run or authentication state.

```bash
python3 tools/prompt_tester.py 10 tools/prompts/direct_injection.csv
python3 tools/prompt_tester.py 10 tools/prompts/direct_injection.csv -c "<cookie>" -o Documentation/direct_injection_authenticated_output.csv
```

Result CSVs are generated locally when tests run.
