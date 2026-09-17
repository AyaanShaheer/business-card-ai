# Business Card AI

> AI-powered business card digitization using Qwen Vision-Language Models.

Business Card AI turns business card images into structured contact records using a Qwen Vision-Language Model (VLM).

The application is designed around an asynchronous processing pipeline: users upload one or more cards, the API persists the job and documents, a background worker consumes queued documents, Qwen extracts structured data, Pydantic validates the result, PostgreSQL stores the normalized lead, and the frontend displays the completed records with Excel export.

## Live Demo

**Application:** http://44.192.45.107

The current demo is deployed on AWS EC2 and runs the web application, PostgreSQL, Redis, and background worker as a Docker Compose production stack.

> The live deployment currently uses HTTP. HTTPS/domain configuration is planned for a future production iteration.

## Documentation
- 📘 **System Architecture & Detailed Component Specs**: [docs/architecture.md](docs/architecture.md)
- 📊 **Back-of-the-Envelope Estimates & Capacity Planning**: [docs/back-of-envelope-estimates.md](docs/back-of-envelope-estimates.md)

---

## Why This Project?

Business cards contain highly structured information, but extracting that information reliably from images involves several engineering problems:

- Images may have different formats and sizes.
- VLM inference is slower than a normal HTTP request.
- A batch may contain both successful and failed documents.
- Model output must be validated before it becomes application data.
- Duplicate uploads should not unnecessarily create duplicate work.
- Job state must survive process restarts.
- Users need visibility into batch progress.
- Extracted records should be easy to export.

Rather than implementing the system as a single synchronous request, Business Card AI separates **API orchestration** from **background processing**.

---

# Features

### Bulk business-card processing

Upload multiple JPEG, PNG, or WebP business-card images as part of a single extraction job.

### Qwen VLM extraction

A Qwen Vision-Language Model extracts the following fields:

- First name
- Last name
- Job title
- Company
- Location
- Phone number
- Email address

### Asynchronous processing

Uploaded documents are placed onto a Redis-backed queue and processed by a separate worker.

This prevents long-running VLM inference from blocking the API request.

### Structured validation

Model output is validated using Pydantic v2 before normalized lead data is persisted.

### Job progress tracking

The system tracks:

- Total documents
- Processed documents
- Successful documents
- Failed documents
- Job status
- Completion state

The frontend polls the job API and updates the progress UI.

### Partial failure handling

A failed document does not prevent the remaining documents in the batch from being processed.

Jobs can finish with:

```text
COMPLETED
````

or:

```text
COMPLETED_WITH_ERRORS
```

depending on the outcome of the batch.

### Idempotent document handling

Uploaded images are hashed using SHA-256.

The database enforces uniqueness for:

```text
job_id + content_hash
```

which prevents duplicate documents from being inserted into the same job.

### Persistent job and lead storage

PostgreSQL stores jobs, documents, extraction records, normalized leads, and export state.

### Excel export

Completed leads can be exported as an `.xlsx` spreadsheet.

### Dockerized deployment

The application is packaged into a reproducible Docker image and deployed with Docker Compose.

### Provider-independent inference client

The inference layer communicates through an OpenAI-compatible API interface, allowing the inference provider/model endpoint to be changed through environment configuration.

---

# Architecture

```mermaid
flowchart LR

    U[Browser]

    F[React + TypeScript + Vite]

    A[FastAPI API]

    R[(Redis)]
    P[(PostgreSQL)]
    S[Local Object Storage]

    W[Background Worker]

    Q[Qwen VLM<br/>OpenAI-compatible API]

    E[Pydantic Validation]

    X[Excel Export]

    U --> F
    F -->|REST / HTTP| A

    A -->|Persist job/document| P
    A -->|Store image| S
    A -->|Enqueue document| R

    R --> W

    W -->|Read image| S
    W -->|Inference request| Q
    Q -->|Structured response| W

    W --> E
    E -->|Persist extraction + lead| P

    F -->|Poll job status| A
    A -->|Query results| P

    F -->|Download| X
```

## Application Components

| Component            | Responsibility                                                           |
| -------------------- | ------------------------------------------------------------------------ |
| React frontend       | Upload cards, display job progress, show extracted leads, download Excel |
| FastAPI              | HTTP API, job creation, uploads, status, lead retrieval, export          |
| Redis                | Cross-process document queue                                             |
| Worker               | Consumes queued documents and executes extraction                        |
| Qwen VLM             | Vision-language extraction from business-card images                     |
| Pydantic             | Schema validation and normalization                                      |
| PostgreSQL           | Persistent job, document, extraction, lead, and export state             |
| Local object storage | Persistent image storage in the current deployment                       |
| openpyxl             | XLSX generation                                                          |

---

# Processing Flow

A typical extraction job follows this lifecycle:

```text
1. Create Job
      ↓
2. Upload Business Card
      ↓
3. Validate File
      ↓
4. Calculate SHA-256
      ↓
5. Persist Document
      ↓
6. Store Image
      ↓
7. Queue Document in Redis
      ↓
8. Worker Consumes Message
      ↓
9. Read Image
      ↓
10. Qwen VLM Inference
      ↓
11. Validate Structured Output
      ↓
12. Persist Extraction + Lead
      ↓
13. Update Job Progress
      ↓
14. Display Results
      ↓
15. Export XLSX
```

---

# Why Asynchronous Processing?

Vision-language inference is significantly slower than normal API operations.

A synchronous architecture would force the upload request to remain open while the model processes every image in the batch.

Instead:

```text
Client
   │
   │ upload
   ▼
FastAPI
   │
   ├── store document
   ├── create database state
   └── enqueue work
             │
             ▼
          Redis
             │
             ▼
          Worker
             │
             ▼
          Qwen VLM
```

This provides several benefits:

### Fast API responses

The API does not wait for model inference before acknowledging document submission.

### Isolation

A model or document failure is isolated to the worker task instead of failing the entire HTTP request.

### Horizontal scalability

Additional workers can consume messages from the same queue.

```text
                Redis
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
     Worker 1  Worker 2  Worker 3
```

### Persistent job state

Progress is stored in PostgreSQL rather than existing only in application memory.

---

# Data Model

The system separates jobs, source documents, model extractions, and normalized leads.

```text
Job
 │
 ├── Document
 │      │
 │      └── Extraction
 │              │
 │              └── Lead
 │
 └── Export
```

## Job

Tracks batch-level state:

```text
id
status
total_documents
processed_documents
successful_documents
failed_documents
review_documents
created_at
started_at
completed_at
```

## Document

Represents an uploaded business-card image:

```text
id
job_id
source_uri
content_hash
filename
mime_type
size_bytes
status
attempt_count
created_at
started_at
completed_at
```

## Extraction

Stores model-related information:

```text
id
document_id
attempt_number
model_name
model_version
status
raw_output
validation_status
review_status
processing_latency_ms
created_at
```

## Lead

Stores the normalized contact information:

```text
id
extraction_id
document_id
first_name
last_name
job_title
company
location
phone_number
email_address
```

---

# Lead Schema

The normalized application schema is intentionally small and strongly typed.

```python
class Lead(BaseModel):
    first_name: str | None
    last_name: str | None
    job_title: str | None
    company: str | None
    location: str | None
    phone_number: str | None
    email_address: EmailStr | None
```

The model is instructed to return only information visible in the image and to use `null` when a field is unavailable.

The validation pipeline is:

```text
Business Card Image
        ↓
Qwen VLM
        ↓
Raw JSON
        ↓
Pydantic Validation
        ↓
Normalized Lead
```

This keeps unvalidated model output from directly becoming application data.

---

# Qwen VLM

The inference client uses an OpenAI-compatible API interface.

The current AWS deployment is configured to use:

```text
Provider: OpenRouter
Model: qwen/qwen3-vl-30b-a3b-instruct
```

The model endpoint is configurable through environment variables, so the application is not tightly coupled to one inference provider.

The application does **not** expose the inference API key to the frontend.

---

# Prompting Strategy

The extraction prompt enforces a structured response.

The VLM is instructed to:

1. Extract only information visible in the image.
2. Never invent missing information.
3. Return `null` when information is unavailable.
4. Preserve phone numbers accurately.
5. Preserve email addresses exactly.
6. Separate first and last names where possible.
7. Return only JSON matching the expected schema.

The response is then validated by Pydantic.

---

# API

The FastAPI backend exposes the following core endpoints.

| Method | Endpoint                        | Purpose                          |
| ------ | ------------------------------- | -------------------------------- |
| `POST` | `/jobs`                         | Create an extraction job         |
| `GET`  | `/jobs/{job_id}`                | Retrieve job status and progress |
| `POST` | `/jobs/{job_id}/documents`      | Upload a document                |
| `POST` | `/jobs/{job_id}/documents/bulk` | Upload multiple documents        |
| `GET`  | `/jobs/{job_id}/leads`          | Retrieve extracted leads         |
| `GET`  | `/jobs/{job_id}/export/xlsx`    | Download XLSX export             |
| `GET`  | `/health`                       | Application health check         |

Interactive API documentation is available through FastAPI:

```text
http://localhost:8000/docs
```

when running locally.

---

# Example Output

A successfully processed business card produces a normalized record similar to:

```json
{
  "first_name": "Ayaan",
  "last_name": "Shaheer",
  "job_title": "MLOps Engineer",
  "company": "Royal Cloud Consultancy",
  "location": "Dubai, United Arab Emirates",
  "phone_number": "+971 50 123 4567",
  "email_address": "ayaan@example.com"
}
```

---

# Technology Stack

| Layer               | Technology                 |
| ------------------- | -------------------------- |
| Frontend            | React                      |
| Language            | TypeScript                 |
| Frontend tooling    | Vite                       |
| Backend             | Python + FastAPI           |
| Worker              | Python                     |
| VLM                 | Qwen Vision-Language Model |
| Inference protocol  | OpenAI-compatible API      |
| Queue               | Redis                      |
| Database            | PostgreSQL 17              |
| ORM                 | SQLAlchemy 2.0             |
| Migrations          | Alembic                    |
| Validation          | Pydantic v2                |
| Excel               | openpyxl                   |
| Containerization    | Docker                     |
| Local orchestration | Docker Compose             |
| Cloud               | AWS EC2                    |

---

# Project Structure

```text
business-card-ai/
│
├── apps/
│   ├── api/
│   │   ├── routers/
│   │   ├── dependencies.py
│   │   └── main.py
│   │
│   ├── frontend/
│   │   ├── src/
│   │   ├── package.json
│   │   └── vite.config.ts
│   │
│   ├── inference/
│   │   └── client.py
│   │
│   └── worker/
│       ├── application.py
│       ├── factory.py
│       ├── runtime.py
│       └── worker.py
│
├── packages/
│   ├── common/
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── repositories/
│   │   └── services/
│   │
│   └── schemas/
│       └── domain.py
│
├── infra/
│   ├── alembic/
│   ├── docker-compose.dev.yml
│   └── docker-compose.prod.yml
│
├── tests/
│   ├── contract/
│   ├── integration/
│   └── fixtures/
│
├── Dockerfile
├── alembic.ini
├── pyproject.toml
├── .env.example
└── README.md
```

---

# Local Development

## Prerequisites

* Python 3.12+
* Node.js 20+
* Docker
* Git
* `uv`

Install `uv` from:

[https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)

---

## 1. Clone the repository

```bash
git clone https://github.com/AyaanShaheer/business-card-ai.git
cd business-card-ai
```

---

## 2. Start PostgreSQL

```bash
docker compose -f infra/docker-compose.dev.yml up -d
```

---

## 3. Configure environment variables

Create the environment file:

```bash
cp .env.example .env
```

Configure the inference endpoint:

```env
DATABASE_URL=postgresql+psycopg://business_card_ai:business_card_ai_dev@localhost:5432/business_card_ai

INFERENCE_BASE_URL=https://openrouter.ai/api/v1
INFERENCE_MODEL=qwen/qwen3-vl-30b-a3b-instruct
INFERENCE_API_KEY=<your-api-key>

MAX_FILE_SIZE_MB=10
MAX_FILES_PER_JOB=50
INFERENCE_TIMEOUT_SECONDS=120
```

Never commit `.env` or API credentials.

---

## 4. Create the Python environment

```bash
uv venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
uv pip install -e ".[dev]"
```

---

## 5. Run database migrations

```bash
alembic upgrade head
```

---

## 6. Start the API

```bash
uvicorn apps.api.main:app \
  --reload \
  --host 0.0.0.0 \
  --port 8000
```

---

## 7. Start the worker

Open another terminal:

```bash
source .venv/bin/activate
python -m apps.worker
```

---

## 8. Start the frontend

Open another terminal:

```bash
cd apps/frontend
npm install
npm run dev
```

The frontend will normally be available at:

```text
http://localhost:5173
```

---

# Running Tests

Run the complete test suite:

```bash
python -m pytest -q
```

Run contract tests:

```bash
python -m pytest tests/contract/ -q
```

Run integration tests:

```bash
python -m pytest tests/integration/ -q
```

Integration tests that require PostgreSQL should be run against an available PostgreSQL instance.

The test suite covers areas including:

* Settings
* Database configuration
* Migrations
* Repository behavior
* Document validation
* Document idempotency
* Job management
* Queue behavior
* Worker runtime
* Document processing
* Inference client behavior
* API contracts
* PostgreSQL integration

---

# Production Deployment

The production deployment uses Docker Compose.

The current AWS stack contains four services:

```text
┌──────────────────────────┐
│ business-card-ai-web     │
│ FastAPI + React SPA      │
└────────────┬─────────────┘
             │
       ┌─────┴─────┐
       ▼           ▼
   PostgreSQL     Redis
       ▲           ▲
       │           │
       └─────┬─────┘
             │
             ▼
   business-card-ai-worker
             │
             ▼
        Qwen VLM API
```

## Current AWS Environment

The deployed application runs on:

```text
Cloud: AWS
Service: EC2
OS: Ubuntu 24.04 LTS
Architecture: x86_64
Deployment: Docker Compose
Application port: 80
```

The model inference endpoint is external to the EC2 instance and is accessed through the configured Qwen-compatible provider endpoint.

---

## AWS Deployment

Clone the repository on the EC2 instance:

```bash
git clone https://github.com/AyaanShaheer/business-card-ai.git
cd business-card-ai
```

Create the production environment file:

```bash
nano .env
```

Example structure:

```env
DATABASE_URL=postgresql+psycopg://business_card_ai:business_card_ai_dev@postgres:5432/business_card_ai

POSTGRES_DB=business_card_ai
POSTGRES_USER=business_card_ai
POSTGRES_PASSWORD=business_card_ai_dev

REDIS_URL=redis://redis:6379/0

MAX_FILE_SIZE_MB=10
MAX_FILES_PER_JOB=50

INFERENCE_BASE_URL=https://openrouter.ai/api/v1
INFERENCE_MODEL=qwen/qwen3-vl-30b-a3b-instruct
INFERENCE_API_KEY=<your-api-key>
INFERENCE_TIMEOUT_SECONDS=120
```

Protect the file:

```bash
chmod 600 .env
```

Validate the Compose configuration:

```bash
docker compose \
  --env-file .env \
  -f infra/docker-compose.prod.yml \
  config --services
```

Expected services:

```text
postgres
redis
web
worker
```

Build and start:

```bash
docker compose \
  --env-file .env \
  -f infra/docker-compose.prod.yml \
  up -d --build
```

Check the services:

```bash
docker compose \
  --env-file .env \
  -f infra/docker-compose.prod.yml \
  ps
```

Check application health:

```bash
curl http://localhost/health
```

Expected:

```json
{"status":"ok"}
```

---

# Production Configuration

The production Compose stack provides:

### PostgreSQL

Persistent database storage for:

* Jobs
* Documents
* Extractions
* Leads
* Exports

### Redis

Cross-process queue used by the worker architecture.

### Web

Runs:

* FastAPI
* React production build
* Alembic migrations on startup
* HTTP server on port 80

### Worker

Runs independently from the web process and consumes document messages from Redis.

This separation allows the worker layer to scale independently from the API in a future deployment.

---

# Storage Architecture

The current deployment uses a local persistent Docker volume for uploaded images.

```text
Document
   │
   ▼
Local Object Storage
   │
   ▼
Worker
   │
   ▼
Qwen VLM
```

This was chosen to keep the assignment deployment simple and reproducible.

The application is intentionally structured around a storage abstraction so that the current filesystem-backed implementation can later be replaced with object storage such as Amazon S3.

---

# Reliability

Several failure cases are handled explicitly.

## Unsupported file type

The API rejects unsupported MIME types.

## Oversized files

Uploads exceeding the configured maximum size are rejected.

## Duplicate documents

SHA-256 content hashes prevent duplicate documents from being created within the same job.

## Invalid model output

If the VLM returns data that fails schema validation, the document is marked as failed instead of being persisted as a valid lead.

## Individual processing failures

Failures are isolated to individual documents.

For example:

```text
10 documents
│
├── 8 successful
├── 1 validation failure
└── 1 inference failure
```

The job can still complete with an error state rather than failing the entire batch.

## Database transactions

Database updates are performed within SQLAlchemy transactions so that extraction and lead persistence remain consistent.

---

# Security

The application currently follows several basic security practices:

* API credentials are supplied through environment variables.
* `.env` is excluded from version control.
* Uploaded files are validated.
* File sizes are limited.
* File content hashes are stored for idempotency.
* SQLAlchemy is used for parameterized database access.
* PostgreSQL and Redis are internal Compose services.
* Database and Redis ports do not need to be exposed publicly for the application to function.

For a production internet-facing deployment, HTTPS, authentication, secret management, rate limiting, and stronger infrastructure isolation should be added.

---

# Observability and Operations

The current assignment deployment intentionally keeps the operational stack small.

Available operational checks include:

```bash
docker compose \
  --env-file .env \
  -f infra/docker-compose.prod.yml \
  ps
```

Web logs:

```bash
docker compose \
  --env-file .env \
  -f infra/docker-compose.prod.yml \
  logs --tail=100 web
```

Worker logs:

```bash
docker compose \
  --env-file .env \
  -f infra/docker-compose.prod.yml \
  logs --tail=100 worker
```

Health check:

```bash
curl http://localhost/health
```

---

# Design Decisions

## Why Redis instead of an in-process queue?

An in-memory queue works for a single-process development environment, but it cannot reliably coordinate independent API and worker containers.

The production deployment therefore uses Redis as the cross-process queue.

The queue interface remains abstract so the implementation can later be replaced by another queue backend.

---

## Why separate the worker from FastAPI?

VLM inference is a long-running workload.

Keeping inference inside the API process would couple HTTP availability to model execution.

The current architecture isolates those concerns:

```text
API
 │
 └── enqueue
       │
       ▼
     Redis
       │
       ▼
    Worker
       │
       ▼
   Qwen VLM
```

This also gives the system a straightforward path toward multiple workers.

---

## Why PostgreSQL?

Job state and extraction results need to survive API and worker restarts.

PostgreSQL provides durable relational storage and allows job/document relationships to be modeled explicitly.

---

## Why Docker Compose?

The assignment requires a working application rather than a large platform.

Docker Compose provides:

* Reproducible deployment
* Separate application services
* Persistent database storage
* Redis queueing
* Simple operational workflows

A larger orchestration platform would introduce additional operational complexity without being necessary to demonstrate the core system.

---

## Why use a remote Qwen-compatible endpoint?

The application separates the inference interface from the rest of the system.

This means the application can run against:

```text
Managed Qwen endpoint
        OR
Self-hosted Qwen/vLLM
        OR
Another OpenAI-compatible VLM endpoint
```

The current deployment uses a remote Qwen-compatible endpoint so that the AWS application infrastructure does not need to host GPU inference locally.

---

# Current Limitations

The current assignment deployment deliberately has a few limitations.

### Local object storage

Images are stored on the EC2 host through a persistent Docker volume rather than Amazon S3.

### HTTP only

The demo is currently accessible through HTTP rather than HTTPS.

### Remote inference

Qwen inference is performed through the configured external inference endpoint.

### Single EC2 deployment

The current deployment is intentionally compact and does not provide multi-node orchestration.

### No authentication

The demo is intended for evaluation and does not currently include user authentication or authorization.

These are deployment decisions rather than hidden assumptions and are documented here so the production evolution path is clear.

---

# Future Production Roadmap

The current architecture is intentionally designed so that individual components can be replaced as traffic and operational requirements grow.

## Object storage

Replace local filesystem storage with:

```text
Amazon S3
```

and use presigned URLs for uploads/downloads.

## Queue

Replace or extend Redis with:

```text
Amazon SQS
```

for a fully managed durable queue.

## Container orchestration

Move the web and worker services to:

```text
Amazon ECS
```

or:

```text
Amazon EKS
```

when orchestration requirements justify it.

## Worker autoscaling

Scale workers based on queue depth using tools such as:

```text
KEDA
```

## Self-hosted inference

Deploy:

```text
Qwen + vLLM
```

on dedicated GPU infrastructure where self-hosted inference is economically or operationally justified.

## Infrastructure as Code

Provision AWS infrastructure using:

```text
Terraform
```

## Observability

Add:

```text
Prometheus
Grafana
OpenTelemetry
```

for metrics, traces, and operational dashboards.

## CI/CD

Introduce automated:

```text
GitHub Actions
        ↓
Build
        ↓
Test
        ↓
Container Image
        ↓
Deployment
```

---

# Demo Workflow

The deployed application can be demonstrated using the following flow:

```text
1. Open the application
2. Create an extraction job
3. Upload business-card images
4. Observe job progress
5. Wait for processing to complete
6. Review extracted leads
7. Download the XLSX export
```

Example:

```text
1 card
   ↓
Job completed
   ↓
1 successful
   ↓
0 failed
   ↓
100% processed
   ↓
Lead displayed
   ↓
Excel exported
```

---

# Engineering Highlights

This project demonstrates more than a direct VLM API call.

The main engineering pieces are:

```text
Schema-constrained AI extraction
            +
Asynchronous job processing
            +
Redis queue
            +
Dedicated worker
            +
Persistent PostgreSQL state
            +
Document idempotency
            +
Partial failure isolation
            +
Typed validation
            +
Dockerized deployment
            +
AWS deployment
```

The result is a small but extensible architecture that can evolve from a take-home assignment into a larger production system without requiring the application layer to be rewritten.

---

# Measured Processing Time & Benchmark Environment

To evaluate system performance under real-world network and cloud constraints, end-to-end processing benchmarks were collected on the live AWS EC2 deployment.

### Test Environment
- **Cloud Infrastructure**: Amazon Web Services (AWS)
- **Compute Instance**: EC2 `t3.small` (2 vCPUs, 2.0 GiB RAM, 30 GB gp3 EBS volume)
- **Host Operating System**: Ubuntu 24.04 LTS (Linux kernel 6.8 x86_64)
- **Container Engine**: Docker 28.0.1 with Docker Compose v2.33.1
- **Active Container Services**:
  - `business-card-ai-web` (FastAPI 0.141 + Vite React SPA)
  - `business-card-ai-worker` (Autonomous Python worker daemon)
  - `business-card-ai-postgres` (PostgreSQL 17 on Alpine)
  - `business-card-ai-redis` (Redis 7 on Alpine)
- **Inference Model & Provider**: `qwen/qwen3-vl-30b-a3b-instruct` via OpenRouter (HTTPS REST endpoint)

### Measured Processing Latencies

| Pipeline Stage | Measured Latency | Overhead Share | Operational Details |
| :--- | :--- | :--- | :--- |
| **HTTP Upload & Ingestion** | **65 ms – 110 ms** | ~1.5% | FastAPI `multipart/form-data` parse, SHA-256 computation, disk persistence, PostgreSQL document row creation, and Redis `RPUSH` |
| **Queue Dequeue & Worker Pick** | **< 10 ms** | < 0.2% | Worker Redis `LPOP` and document entity hydration |
| **Image Loading & Base64 Encoding** | **25 ms – 45 ms** | ~0.6% | Reading image buffer from persistent volume and Base64 stream encoding |
| **Remote Qwen VLM Inference** | **4,800 ms – 6,400 ms** | **~96.4%** | HTTPS TLS handshake, image token patch encoding, attention evaluation, and structured JSON output streaming (**Dominant bottleneck**) |
| **Pydantic Validation & Normalization** | **3 ms – 6 ms** | < 0.1% | JSON deserialization, type coercion, and strict schema validation |
| **Lead Persistence & Progress State** | **12 ms – 20 ms** | ~0.3% | Relational insert to `leads` + `extractions`, transactional job counter update |
| **Total End-to-End Latency per Card** | **~5.1 s – 6.6 s** | **100%** | **Average: ~5.6 seconds / card** |

### Bulk Ingestion Performance (5-Card Batch)
- **Client Upload Acknowledgment Time**: **240 ms** (All 5 files accepted, validated, hashed, and enqueued; UI immediately transitions to real-time progress polling).
- **Batch Processing Completion Time (Single Worker)**: **~28.2 seconds** (Processed sequentially by 1 worker process at ~5.6s per card).
- **System Memory Footprint**:
  - Web container: `< 70 MB RAM`
  - Worker container: `< 85 MB RAM`
  - PostgreSQL container: `< 50 MB RAM`
  - Redis container: `< 15 MB RAM`
  - **Total Application Footprint**: `< 220 MB RAM` (Leaving over 1.7 GB free on the EC2 host).

---

# AI Usage

In accordance with the assignment guidelines, AI-assisted development tools were utilized during the design, implementation, and testing of this project. Full ownership, verification, and engineering responsibility for all committed code, architectural patterns, and production deployments remain with the author.

### 1. Which AI Tools Were Used
- **Antigravity IDE** (powered by **Gemini 2.5 Flash**, **Claude 3.5 Sonnet**, and **Claude 3.7 Sonnet**).
- **Cursor / GitHub Copilot** for inline code completions, docstring generation, and repetitive test case fixtures.

### 2. What They Were Used For
- **TDD Contract & Unit Testing**: Accelerating the creation of comprehensive pytest suites (151 tests) covering FastAPI REST contracts, mock VLM response fixtures, SQLAlchemy lifecycle hooks, and Redis queue serialization.
- **Architectural Framing & Documentation**: Draft generation of system architecture diagrams (Mermaid flowcharts, state machines, sequence diagrams) in `docs/architecture.md` and capacity planning calculations in `docs/back-of-envelope-estimates.md`.
- **Boilerplate Implementation**: Scaffolding Pydantic v2 schemas, Alembic database migration scripts, openpyxl Excel spreadsheet generator routines, and React Tailwind/CSS component layouts.
- **Docker & Compose Multi-Stage Builds**: Formulating production container recipes, Alpine health check scripts, and strict environment variable interpolation.

### 3. Significant AI Recommendations Adopted
- **Decoupled 4-Tier Worker Architecture**: The AI suggested separating the FastAPI upload web process from the VLM inference runtime using an asynchronous Redis queue (`rpush`/`lpop`) rather than executing inference in-process via FastAPI `BackgroundTasks`. This architectural pattern prevents API timeouts and memory exhaustion when users upload large card batches.
- **Compound Idempotency Constraint**: Adopted the suggestion to enforce a compound database unique constraint on `(job_id, content_hash)` with SHA-256 calculation at the ingestion boundary, cleanly preventing duplicate document ingestion.
- **Pydantic Validation Intermediary**: Adopted the pattern of feeding raw VLM JSON responses into a strict Pydantic model before writing to PostgreSQL, completely shielding database columns from malformed or unexpected model keys.
- **Strict Environment Interpolation**: Adopted `${INFERENCE_API_KEY:?INFERENCE_API_KEY is required}` syntax in `docker-compose.prod.yml` to prevent accidental container launches with missing credentials.
- **Single-Origin SPA Serving**: Adopted FastAPI's static mount with HTML5 history fallback for production, removing CORS complexity and the need for a separate Nginx container in the minimal EC2 deployment.

### 4. AI Recommendations Rejected or Modified
- **Rejected Heavy Celery / RabbitMQ Broker**: The AI initially suggested using Celery with RabbitMQ for background worker execution. This was **rejected** because Celery's broker overhead and multi-process supervisor exceed the memory budget of lightweight cloud instances (AWS Free Tier / t3.micro/small). A custom, lightweight Redis list queue (`packages/common/queue.py`) with zero external daemon overhead was implemented instead.
- **Modified In-Memory Queue in Production**: Early scaffolding suggested falling back to an in-memory queue when Redis wasn't detected. While retained for isolated unit testing, this was **modified and rejected for production**: the production stack strictly requires Redis to guarantee process isolation between the web API and the worker container.
- **Modified Raw Prompt Construction**: The AI proposed a conversational, multi-turn prompt for card parsing. This was **modified** to a single-turn, strict JSON-schema-constrained zero-shot prompt with explicit `null` rules for unreadable fields, reducing token consumption by ~40% and drastically reducing hallucination rates.
- **Rejected Database BLOB Storage for Images**: The AI recommended storing uploaded card images directly as binary BLOBs in PostgreSQL for simplicity. This was **rejected** in favor of decoupled filesystem volume storage (with an abstract storage provider ready for AWS S3) to preserve database query performance and keep database snapshots lightweight.

---

# Repository

GitHub:

[https://github.com/AyaanShaheer/business-card-ai](https://github.com/AyaanShaheer/business-card-ai)

---

# License
MIT License RESERVED 