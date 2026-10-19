# Pentesting RAG 

## Direct RAG Leakage Prompts 
- All testing needs to be both authenticated and unauthenticated 
```
# TMC labs only
curl http://localhost:5000/api/knowledge-base/stats 

# Targeted RAG Testing
python3 prompt_tester.py 10 targeted_rag.csv
python3 prompt_tester.py 10 enhanced_targeted_rag.csv --repeat 2

# Authenticated
python3 prompt_tester.py 10 enhanced_targeted_rag.csv --repeat 2 -c "<cookie>"


```
- After reviewing the output from the first attack, tweak prompts that may have worked to further exploit the applications RAG
- Prompts from other Jailbreaks and previous injections can also be used and tweaked to attack an applications RAG

## RAG "FISHING"
- Most of the time we will not have lab level knowledge of the AI and RAG being used by an application, "Fishing" is methodically pulling information via prompts
```
python3 prompt_tester.py 10 --repeat 2 rag_fishing_prompts.csv
python3 prompt_tester.py 10 --repeat 2 rag_fishing_prompts.csv -c "<cookie>"
```
- If there are any success or potential successes, modify the prompt and continue testing for further exploitation 

## RAG Canaries
- For Lab -- Delete Once Done
  <img width="1328" height="440" alt="image" src="https://github.com/user-attachments/assets/9e2e697d-5258-4224-9fc2-3a8b9bc5d752" />

```
python3 prompt_tester.py 10 canary_rag.csv --check-for-phrase
python3 prompt_tester.py 10 canary_rag.csv --check-for-phrase -c "<cookie>"
```

## RAG Data Poisoning 
- Typically not done directly in a pentest
- Often requires prior compromise or a malicious insider
- Test in lab
  - Update FAQ about the company (labs/ai101/knowledge-bases/faq.md (Don't forget to re-index))
