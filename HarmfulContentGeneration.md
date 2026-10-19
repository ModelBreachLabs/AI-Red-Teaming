# Testing for Harmful and Wasteful Output

## Testing for Harmful Output 
```
python3 prompt_tester.py
python3 prompt_tester.py 15 harmful_prompts.csv --check-for-phrase
python3 prompt_tester.py 15 harmful_prompts.csv --check-for-phrase -c "<cookie>"

# Automated Classification
python3 injection_judge.py --help
python3 injection_judge.py <previous_results>.csv -u http://<ollama_URL>:11434/api/generate

# Format Excel: Conditional Highlighting -> SUCCESS = Green & FAILURE = RED
# Review Results
```

## Testing fort Off Topic Content 
```
python3 prompt_tester.py 15 offtopic_prompts.csv --check-for-phrase
python3 prompt_tester.py 15 offtopic_prompts.csv --check-for-phrase -c "<cookie>" 

# Automated Classification
python3 injection_judge.py --help
python3 injection_judge.py <previous_results>.csv -u http://<ollama_URL>:11434/api/generate

# Format Excel: Conditional Highlighting -> SUCCESS = Green & FAILURE = RED
# Review Results
```

# Testing for Unbounded Consumption 
```
python3 prompt_tester.py 15 context_overflow.csv --check-for-phrase
python3 prompt_tester.py 15 context_overflow.csv --check-for-phrase-c "<cookie>"

# Automated Classification
python3 injection_judge.py --help
python3 injection_judge.py <previous_results>.csv -u http://<ollama_URL>:11434/api/generate

# Format Excel: Conditional Highlighting -> SUCCESS = Green & FAILURE = RED
# Review Results
```

# Stacking Prompt Injection and Harmful Content Generation
- This is done by combining previously enumerated successful prompts to accomplish harmful content generation
