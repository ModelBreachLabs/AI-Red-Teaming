# Data Leakage 

Modern LLM applications often use Retrieval-Augmented Generation (RAG). Instead of relying only on training data, the system retrieves documents from a vector database and injects them into the model's context before generating a response.

This creates multiple potential leakage points:

- Over-broad similarity search retrieves unrelated confidential documents
- Shared vector databases across departments or tenants
- Large context windows combining multiple document chunks
- Debug logging stores full prompts and retrieved content
- Weak or missing metadata filtering

## Attacks on Vector Databases

