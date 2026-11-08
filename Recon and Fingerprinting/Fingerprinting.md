Tools: 
- nmap
- shodan (search examples)
  - port:5000 "MLflow" for exposed MLflow instances
  - port:8888 title:"Home Page - Select or create a notebook" for unauthenticated Jupyter notebooks
  - http.title:"Ray Dashboard" for exposed Ray cluster dashboards
  - port:8001 "triton"
- ffuf
- grpcurl

# The AI Tech Stack 

## Port and Protocol Reference

| **Component** | **Default Port(s)** | **Protocol(s)** | **Recon Endpoints** |
|---|---|---|---|
| **NVIDIA Triton**<br>*(Loads models into memory and serves predictions at scale)* | 8000, 8001, 8002 | HTTP, gRPC, Prometheus | `/v2/health/ready`, `/v2/models` |
| **TensorFlow Serving**<br>*(Google's model serving framework for TensorFlow models)* | 8500, 8501 | gRPC, HTTP | `/v1/models/<name>` |
| **TorchServe**<br>*(PyTorch's official model serving framework)* | 8080, 8081, 8082 | HTTP | `/ping`, `/models` |
| **Ollama**<br>*(Local runtime for running LLMs on your own hardware)* | 11434 | HTTP | `/api/tags`, `/api/show` |
| **vLLM**<br>*(High-throughput LLM serving engine with OpenAI-compatible API)* | 8000 | HTTP | `/v1/models` |
| **MLflow**<br>*(Tracks experiments, stores models, and manages the ML lifecycle)* | 5000 | HTTP | `/api/2.0/mlflow/experiments/search` |
| **Kubeflow**<br>*(Kubernetes-native platform for orchestrating ML pipelines)* | 80, 443 | HTTP | `/pipeline/apis/v1beta1/pipelines` |
| **Ray**<br>*(Distributed compute framework for scaling AI workloads)* | 8265, 8000 | HTTP | `/api/jobs/`, Ray Dashboard |
| **Qdrant**<br>*(Vector database for semantic search and RAG pipelines)* | 6333, 6334 | HTTP, gRPC | `/collections` |
| **Weaviate**<br>*(Vector database with built-in GraphQL and module system)* | 8080 | HTTP, GraphQL | `/v1/schema`, `/v1/meta` |
| **Milvus**<br>*(Distributed vector database for large-scale embedding storage)* | 19530 | gRPC | Port 19530 connection |
| **Jupyter Notebook**<br>*(Interactive coding environment used by data scientists)* | 8888 | HTTP | `/api/kernels`, `/api/contents` |
| **MinIO**<br>*(S3-compatible object storage often used for model artifacts)* | 9000, 9001 | HTTP (S3-compatible) | Bucket listing |
| **Prometheus Metrics**<br>*(Not a standalone AI service; exposed by Triton on 8002, TorchServe on 8082, and other ML servers as a built-in monitoring endpoint)* | 8002, 8082 | HTTP | `/metrics` |

**Orchestration and Experiment Tracking**
These platforms manage the entire ML lifecycle, from experiment design through to model deployment. They are the highest-value targets during reconnaissance because they contain everything.

## Fingerprinting AI 
Fingerprinting AI services requires a different approach; you need to look at:

- HTTP headers
- (API) JSON response structures
- Error messages (deliberate malformed payloads) - Often most reliable
- Endpoint naming conventions (ffuf, use AI focused wordlist)
- gRPC Fingerprinting (grpcurl)
- TLS Fingerprinting (JA3/JA4)

## Enumerating AI 
