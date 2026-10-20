# Pentesting RAG 

Run commands from the repository root (`AI-Red-Teaming/`). The baseline datasets are included under `tools/prompts/`. `enhanced_targeted_rag.csv` is created during an engagement after reviewing initial results; it is not a bundled dataset.

Results default to `Prompt Results/<dataset_name>_output.csv`. Before replacing an existing output, the tester creates a timestamped backup beside it. Use `-o` with a separate filename to preserve different runs or authentication states.

## Direct RAG Leakage Prompts 
- All testing needs to be both authenticated and unauthenticated 
```
# TMC labs only
curl http://localhost:5000/api/knowledge-base/stats 

# Initial targeted RAG testing
python3 tools/prompt_tester.py 10 tools/prompts/targeted_rag.csv
python3 tools/prompt_tester.py 10 tools/prompts/targeted_rag.csv -c "<cookie>" -o "Prompt Results/targeted_rag_authenticated_output.csv"

# Mid-engagement: review initial results, adapt promising prompts to the target,
# and save them as tools/prompts/enhanced_targeted_rag.csv before running:
python3 tools/prompt_tester.py 10 tools/prompts/enhanced_targeted_rag.csv --repeat 2

# Authenticated
python3 tools/prompt_tester.py 10 tools/prompts/enhanced_targeted_rag.csv --repeat 2 -c "<cookie>" -o "Prompt Results/enhanced_targeted_rag_authenticated_output.csv"


```
- After reviewing the output from the first attack, tweak prompts that may have worked to further exploit the applications RAG
- Prompts from other Jailbreaks and previous injections can also be used and tweaked to attack an applications RAG

## RAG "FISHING"
- Most of the time we will not have lab level knowledge of the AI and RAG being used by an application, "Fishing" is methodically pulling information via prompts
```
python3 tools/prompt_tester.py 10 --repeat 2 tools/prompts/rag_fishing_prompts.csv
python3 tools/prompt_tester.py 10 --repeat 2 tools/prompts/rag_fishing_prompts.csv -c "<cookie>" -o "Prompt Results/rag_fishing_prompts_authenticated_output.csv"
```
- If there are any success or potential successes, modify the prompt and continue testing for further exploitation 

## RAG Canaries
- For Lab -- Delete Once Done
  <img width="1328" height="440" alt="image" src="https://github.com/user-attachments/assets/9e2e697d-5258-4224-9fc2-3a8b9bc5d752" />

```
python3 tools/prompt_tester.py 10 tools/prompts/canary_rag.csv --check-for-phrase
python3 tools/prompt_tester.py 10 tools/prompts/canary_rag.csv --check-for-phrase -c "<cookie>" -o "Prompt Results/canary_rag_authenticated_output.csv"
```

## RAG Data Poisoning 
- Typically not done directly in a pentest
- Often requires prior compromise or a malicious insider
- Test in lab
  - Update FAQ about the company (labs/ai101/knowledge-bases/faq.md (Don't forget to re-index))
