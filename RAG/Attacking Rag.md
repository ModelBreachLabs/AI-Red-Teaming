# RAG Attack Surface 

Unlike traditional applications, external data is not just stored — **it directly influences model reasoning at inference time.**

The main RAG-specific attack surfaces are:

- **Document ingestion:** Untrusted, outdated, or malicious documents can enter the system if validation is weak.
- **Embedding generation:** Text is converted into numerical vectors, making intent and safety harder to inspect manually.
- **Similarity-based retrieval:** Documents are selected by semantic relevance, not correctness, trust, or safety.
- **Context injection:** Retrieved documents are injected directly into the model’s context window before generation.

**Retrieval abuse** is a RAG-specific attack technique in which unintended or malicious documents influence model output via retrieval.

- **Passive poisoning:** Malicious content is ingested once and left in the knowledge base. The attacker waits for normal queries to retrieve it.
- **Active manipulation:** Content is deliberately crafted to rank highly for common or sensitive queries.

In RAG systems, retrieved documents are injected into the model’s context window before generation resulting in context manipulation. 

## Training Data Poisoning

Training data poisoning happens when an attacker manipulates the data used to train or fine-tune an LLM. Poisoning usually begins with access to a trusted data source. Attackers may insert new documents, modify existing ones, or gradually shift content over time. Effective poisoning is subtle. Attackers only need access to a data source.

## Embeddings and Vector Databases 

Modern LLM systems often use embeddings to retrieve relevant documents. An embedding is a numerical representation of text that captures meaning rather than exact words. Documents with similar meaning are positioned closer together in semantic space. A vector database stores these embeddings and retrieves documents based on similarity.

### Corpus Poisoning Techniques
Corpus poisoning targets the document collection inside the vector database.

Attackers may:
- Repeat common search phrases (keyword stuffing)
- Imitate the tone and structure of trusted documents (semantic mimicry)
- Upload multiple slightly modified copies of the same idea (duplication)

**Vector databases return the top-k closest results.** If multiple poisoned documents occupy a similar region of embedding space, they increase the local density around that topic. 

### Embedding Poisoning Vs Training Data Poisoning

Training data poisoning changes what the model learns. Embedding and corpus poisoning change what the model sees at **inference time.**

Comparing Poisoning Layers:
- **Training Data Poisoning:** Alters the model's internal weights during training or fine-tuning; the distortion becomes part of the model's learned parameters.
- **Embedding-Level Poisoning:** Manipulates how documents are represented in vector space. The base model remains unchanged, but similarity relationships are influenced.
- **Corpus Flooding: **Increases the density of attacker-controlled documents in a specific semantic region, raising the probability of retrieval.

## Ingestion Pipeline Attacks

An ingestion pipeline may include **document collection, parsing, chunking, embedding, indexing, and storage.** Once processed, the content becomes part of the system's searchable knowledge base. These steps are often automated and **trusted by default.** These processes are mostly automated. 

 Attackers do not need access to the model itself. They only need access to a data source that feeds into the pipeline.

Attacks may look like:
- Upload a malicious document into a shared directory
- Modify an existing file that is automatically re-indexed
- Inject poisoned content into a third-party feed
- Exploit weak validation rules in file parsers

Since ingestion is automated, the poisoned document is processed like any other. It is chunked, embedded, indexed, and made retrievable. The attack becomes scalable. One document can affect many future queries.

## Effects on Model Behavior 

**Obvious Poisoning Effects**
- Backdoor triggers that activate specific behaviour
- Persona shifts or tone changes
- Clearly incorrect or extreme responses

**Subtle Poisoning Effects**
- Slightly favour one product over another
- Adjust regulatory thresholds by small margins
- Reframe a security recommendation
- Omit critical warnings
Each individual response may appear reasonable. Over time, these small distortions can influence decisions at scale. Subtle poisoning blends into normal operation.

# Detections and Mitigations
- Validation at Ingestion
  - Source verification
  - Access control restrictions
  - Structured content review
  - Logging and change tracking
- Monitoring Behavioral Drift
  - Tracking shifts in tone or persona
  - Detecting consistent recommendation bias
  - Comparing outputs before and after data updates
- Review and Governance of data integrity 
