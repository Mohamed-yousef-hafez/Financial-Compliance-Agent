# Financial Compliance Agent

Production-style Agentic RAG project for financial document compliance analysis.

## Scope

The system analyzes financial contracts and internal policies. It retrieves relevant evidence, reranks results, applies tenant isolation and security checks, generates grounded compliance answers, and returns structured results with sources and a concise decision trace.

## Core capabilities

PDF ingestion
Text cleaning and chunking
Document metadata
Tenant-scoped retrieval
Semantic-style local retrieval
Hybrid retrieval abstraction
Lightweight reranking
Grounded generation
Source citations
Agent orchestration
Bounded agent execution
Prompt-injection detection
Tool allow-listing
Structured JSON responses
Compliance risk classification
Evaluation utilities
FastAPI API
Automated tests
Docker support

## Architecture

A request enters FastAPI and is passed to the compliance agent. The agent validates the request, checks for prompt injection, selects approved tools, retrieves tenant-scoped evidence, reranks the evidence, evaluates whether enough evidence exists, classifies the compliance risk, generates a grounded response, and returns structured output.

The decision trace contains high-level execution events only. It is not hidden chain-of-thought.

## Requirements

Python 3.12 is recommended.

## Run locally

Install dependencies:

pip install -r requirements.txt

Start the API:

python run.py

Open:

http://127.0.0.1:8000/docs

## Ingest documents

POST /ingest

Example body:

{"tenant_id":"tenant_demo"}

Sample documents are included in data/policies and data/contracts.

## Ask a compliance question

POST /chat

Example body:

{"question":"Does the contract allow payment after 30 days?","tenant_id":"tenant_demo","user_id":"user_demo"}

The response includes answer, grounded status, risk level, decision trace, and sources.

## Security

Tenant isolation is enforced by the retrieval layer and is never delegated to the LLM.

Prompt injection is checked before retrieval.

Tools are allow-listed.

The demo uses a tenant identifier instead of a production identity provider. A production deployment should use JWT or OAuth2 authentication, server-side authorization, secret management, rate limits, audit logging, and policy enforcement.

## Agent controls

Agent execution is bounded.

Tool access is restricted.

The system stops when evidence is insufficient.

Production deployments should add tool timeouts, retries, idempotency, duplicate-action detection, circuit breakers, and human approval for high-risk actions.

## Retrieval

The default implementation is intentionally lightweight and does not require a GPU or paid model API.

The retrieval layer is isolated behind an interface so a production system can replace the local TF-IDF implementation with BGE embeddings, a vector database such as ChromaDB, hybrid search, and a cross-encoder reranker.

## Generation

The included generator is deterministic so the project can be demonstrated without an API key.

A production version should connect the generation interface to an approved LLM provider and enforce grounding, structured output validation, timeout handling, retries, fallback models, and cost controls.

## Evaluation

The project includes Recall@K and retrieval score utilities.

A production evaluation set should measure retrieval recall, precision, answer correctness, faithfulness, groundedness, refusal quality, latency, token usage, cost, tool success, and task completion.

## Docker

Run:

docker compose up --build

## Configuration

TOP_K controls retrieval depth.

MAX_AGENT_STEPS controls the maximum agent execution budget.

MIN_RETRIEVAL_SCORE controls the evidence threshold.

## Production upgrade path

Replace local TF-IDF retrieval with BGE embeddings and ChromaDB or another vector database.

Add hybrid lexical and semantic retrieval.

Add a cross-encoder reranker.

Connect a real LLM through the generation interface.

Add authentication and authorization.

Add database and vector-index synchronization.

Add asynchronous ingestion.

Add caching and streaming.

Add structured logging and distributed tracing.

Add continuous AI evaluation to CI/CD.

Add model routing and LLM fallback.

Add monitoring for latency, cost, groundedness, retrieval quality, tool failures, and task success.

## Interview focus

RAG retrieval quality is improved through chunking, metadata, embeddings, top-k selection, hybrid retrieval, reranking, and evaluation.

Agents need bounded execution, tool restrictions, validation, timeouts, duplicate detection, and safe stopping.

Authorization must be enforced in backend services and data access layers.

RAG is preferred when knowledge changes frequently or must remain externally grounded. Fine-tuning is primarily used for behavior, style, or task adaptation.

FastAPI provides the production API boundary. Streamlit is more appropriate for a rapid interactive demo.

Docker provides a reproducible runtime.

CI/CD should include unit tests, API tests, retrieval evaluations, security checks, container builds, and deployment gates.

Observability should track latency, retrieval quality, model usage, cost, tool outcomes, errors, and task success while minimizing sensitive data exposure.
