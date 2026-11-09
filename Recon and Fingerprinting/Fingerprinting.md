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

### MLflow Enumeration Path 
```
1. List all experiments
POST /api/2.0/mlflow/experiments/search

2. List Registered Models
GET /api/2.0/mlflow/registered-models/list

3. Get Model Version
GET /api/2.0/mlflow/model-versions/search

4. Search Training Runs
POST /api/2.0/mlflow/runs/search

5. Downloadable Artifacts 
GET /api/2.0/mlflow/artifacts/list
```

Automated Enumeration ToolL: https://github.com/xforcered/MLOKit

### Inference Server Metadata 

**Triton** and **TensorFlow** Serving both expose metadata endpoints that tell you exactly how to talk to the model.

```
# Triton
GET /v2/models/<name>/config

# TensorFlow
GET /v1/models/<name>/metadata
```

### Enumerating Vector Databases

Vector databases reveal what data the AI system is working with and which embedding model processes it.

```
# Weaviate 
GET /v1/meta
GET /v1/schema
/v1/graphql

# Qdrant
GET /collections
GET /collections/<name>

# Chroma
GET /api/v1/collections
```

### Prometheus Metrics as Intelligence

Model servers often expose ```/metrics``` on a dedicated port (Triton on 8002, TorchServe on 8082). These Prometheus-format endpoints return:

- Model names and version numbers currently loaded
- Inference request counts and latency percentiles
- Batch sizes being processed
- GPU memory utilisation per model

### Debug Interfaces & Information Leakage 

FastAPI-based ML services auto-generate ```/docs``` (Swagger UI) and ```/openapi.json```. Both expose the full request/response schema, authentication requirements, and example payloads for every endpoint.

MLflow's ```/graphql``` endpoint: ```mlflow.source.name, mlflowGetRun, mlflowSearchRuns```

### Enumerating Jupyter Notebooks 

```GET /api/kernels``` on an unauthenticated Jupyter instance returns the names, kernel IDs, and last activity timestamps of running kernels. Enough to infer what code is executing. But the real value is in the notebook cells. Data scientists routinely store cleartext credentials for MLflow (MLFLOW_TRACKING_USERNAME, MLFLOW_TRACKING_PASSWORD), cloud storage access keys, and Hugging Face tokens directly in their code. This is often the bridge between compromising one service and gaining access to everything else in the stack. --- HIGHLY INVESTIGATE
