# Testing for Harmful and Wasteful Output

Run commands from the repository root (`AI-Red-Teaming/`).

## Testing for Harmful Output 
```
python3 tools/prompt_tester.py --help
python3 tools/prompt_tester.py 15 tools/prompts/harmful_prompts.csv --check-for-phrase
python3 tools/prompt_tester.py 15 tools/prompts/harmful_prompts.csv --check-for-phrase -c "<cookie>"

# Automated Classification
python3 tools/injection_judge.py --help
python3 tools/injection_judge.py "<previous_results>.csv" -u "http://<ollama_URL>:11434/api/generate"

# Format Excel: Conditional Highlighting -> SUCCESS = Green & FAILURE = RED
# Review Results
```

## Testing fort Off Topic Content 
```
python3 tools/prompt_tester.py 15 tools/prompts/offtopic_prompts.csv --check-for-phrase
python3 tools/prompt_tester.py 15 tools/prompts/offtopic_prompts.csv --check-for-phrase -c "<cookie>" 

# Automated Classification
python3 tools/injection_judge.py --help
python3 tools/injection_judge.py "<previous_results>.csv" -u "http://<ollama_URL>:11434/api/generate"

# Format Excel: Conditional Highlighting -> SUCCESS = Green & FAILURE = RED
# Review Results
```

# Testing for Unbounded Consumption 
```
python3 tools/prompt_tester.py 15 tools/prompts/context_overflow.csv --check-for-phrase
python3 tools/prompt_tester.py 15 tools/prompts/context_overflow.csv --check-for-phrase -c "<cookie>"

# Automated Classification
python3 tools/injection_judge.py --help
python3 tools/injection_judge.py "<previous_results>.csv" -u "http://<ollama_URL>:11434/api/generate"

# Format Excel: Conditional Highlighting -> SUCCESS = Green & FAILURE = RED
# Review Results
```

# Stacking Prompt Injection and Harmful Content Generation
- This is done by combining previously enumerated successful prompts to accomplish harmful content generation
