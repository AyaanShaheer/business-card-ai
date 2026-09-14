# Business Card AI

> Scalable multimodal document-processing system for extracting structured lead data from business-card images using Qwen Vision-Language Models.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Ready-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Planned-326CE5?logo=kubernetes&logoColor=white)](https://kubernetes.io/)

## Overview

Business Card AI is being built as a production-oriented, horizontally scalable multimodal extraction system.

The core workflow is:

```text
Business-card images
        │
        ▼
    Upload layer
        │
        ▼
      Job API
        │
        ▼
 Durable queue
        │
        ▼
 Extraction workers
        │
        ▼
 Qwen Vision-Language Model
        │
        ▼
 Structured extraction
        │
        ▼
 Validation + normalization
        │
        ▼
 PostgreSQL
        │
        ▼
 Lead records
        │
        ▼
 Excel export
````

The system is intentionally designed so that API capacity, CPU workers, and GPU inference capacity can scale independently.

---

## Current Project Status

### Completed

* Repository and monorepo foundation
* Shared Pydantic domain contracts
* Lead, Job, Document, Extraction, and Export models
* SQLAlchemy 2.x persistence layer
* PostgreSQL development environment
* Alembic migration system
* Environment-based configuration
* Database engine/session infrastructure
* PostgreSQL integration tests
* Migration tests
* Domain validation tests

### Current Test Status

```text
41 tests passing
```

The project is being developed incrementally with tests written before implementation for each major component.

### In Progress

* Application service layer
* FastAPI API
* Transaction boundaries
* Object storage integration
* Asynchronous job processing
* Qwen VLM inference service
* Result validation and normalization
* Frontend
* Observability
* Kubernetes deployment
* GPU inference scaling
* Infrastructure as Code

---

# Architecture

The target architecture separates the control plane from the inference plane.

```text
                                  INTERNET
                                      │
                                      ▼
                           ┌────────────────────┐
                           │ CloudFront / ALB   │
                           └─────────┬──────────┘
                                     │
                              ┌──────▼──────┐
                              │    EKS      │
                              │             │
                              │ React       │
                              │ FastAPI     │
                              │ Go          │
                              └──────┬──────┘
                                     │
                       ┌─────────────┼─────────────┐
                       │             │             │
                       ▼             ▼             ▼
                  PostgreSQL       Redis           S3
                       │
                       │
                       ▼
                      SQS
                       │
                       ▼
                 KEDA Autoscaling
                       │
             ┌─────────┼─────────┐
             ▼         ▼         ▼
          Worker    Worker    Worker
             │         │         │
             └─────────┼─────────┘
                       │
                       ▼
              Image preprocessing
                       │
                       ▼
              VLM inference API
                       │
                       ▼
                     vLLM
                       │
                       ▼
                    Qwen-VL
                       │
                     GPU
                       │
                  EKS GPU nodes
                       │
                   Karpenter
```

This architecture is the long-term target. Individual infrastructure components will be introduced only when the corresponding application behavior has been tested and validated.

---

# Engineering Principles

## 1. Tests before implementation

Every significant component follows:

```text
Requirements
    ↓
Edge cases
    ↓
Tests
    ↓
Implementation
    ↓
Integration
    ↓
Benchmark
```

This is a deliberate project-wide development rule.

## 2. Independent scaling

The system should never require scaling the entire stack simply because one component is under load.

Examples:

```text
API traffic increases
    → scale API replicas

Queue backlog increases
    → scale workers

GPU inference demand increases
    → scale inference replicas

Uploaded data increases
    → S3 handles object storage
```

## 3. Failure isolation

One malformed or failed business card must not fail the entire batch.

Example:

```text
10,000 documents

9,960 successful
25 review required
15 failed
```

The job can still complete with errors.

## 4. Model abstraction

The business logic will depend on an inference interface rather than directly coupling every service to Qwen.

Conceptually:

```text
VLMExtractor
    │
    ├── QwenVLExtractor
    ├── MockVLMExtractor
    └── FutureModelExtractor
```

This makes model replacement, benchmarking, and testing easier.

## 5. Persistent extraction history

Every model attempt is preserved.

```text
Document
   │
   ├── Attempt 1 → failed
   ├── Attempt 2 → failed
   └── Attempt 3 → success
```

This enables later analysis of:

* model reliability
* retry rates
* latency
* failure causes
* model version changes

---

# Core Data Model

```text
Job
 │
 ├── Documents
 │      │
 │      └── Extractions
 │              │
 │              └── Lead
 │
 └── Exports
```

## Lead fields

The current extraction contract contains:

```text
first_name
last_name
job_title
company
location
phone_number
email_address
```

Additional operational metadata lives outside the Lead business object.

---

# Repository Structure

```text
business-card-ai/
│
├── apps/
│   ├── api/
│   ├── frontend/
│   ├── inference/
│   ├── orchestrator/
│   └── worker/
│
├── packages/
│   ├── clients/
│   ├── common/
│   ├── observability/
│   └── schemas/
│
├── infra/
│   ├── alembic/
│   ├── helm/
│   └── terraform/
│
├── tests/
│   ├── contract/
│   ├── fixtures/
│   └── integration/
│
├── benchmarks/
├── evaluation/
├── docs/
│   ├── adr/
│   ├── architecture/
│   └── performance/
│
├── .github/
│   └── workflows/
│
├── alembic.ini
├── Makefile
├── README.md
└── .gitignore
```

---

# Technology Stack

## Application

* Python 3.12+
* FastAPI
* Pydantic v2
* SQLAlchemy 2.x

## Data

* PostgreSQL
* Redis
* Amazon S3

## Messaging

* Amazon SQS

## AI / ML

* Qwen Vision-Language Model
* PyTorch
* Hugging Face
* vLLM

## Systems

* Go
* Docker
* Kubernetes
* Amazon EKS

## Infrastructure

* Terraform
* Helm
* KEDA
* Karpenter
* AWS IAM
* AWS Secrets Manager

## Observability

* Prometheus
* Grafana
* OpenTelemetry
* NVIDIA DCGM

## Delivery

* GitHub Actions
* Argo CD

---

# Development Philosophy

This project intentionally avoids adding technologies purely for complexity.

For example, Kafka, Airflow, service meshes, vector databases, agents, and excessive microservice decomposition are not part of the core architecture unless a real requirement emerges for them.

The objective is:

> Use distributed systems where distribution solves a real bottleneck.

---

# Performance Strategy

The system will eventually be benchmarked across:

```text
1 document
5 documents
10 documents
25 documents
50 documents
100 documents
1,000 documents
10,000+ documents
```

Metrics will include:

```text
P50 latency
P95 latency
P99 latency
cards/minute
queue wait time
preprocessing time
inference time
end-to-end job duration
GPU utilization
GPU memory
failure rate
retry rate
```

Performance claims will be based on measured results from the actual deployed configuration rather than assumptions.

---

# Security Considerations

Business-card images are treated as untrusted input.

The system will enforce:

* allowed MIME types
* file-size limits
* batch-size limits
* malformed-image rejection
* schema validation
* controlled model output
* prompt-injection resistance
* secret management outside source control
* least-privilege cloud access

---

# Development Workflow

The project follows incremental milestones.

```text
Domain
  ↓
Persistence
  ↓
Services
  ↓
API
  ↓
Storage
  ↓
Queue
  ↓
Workers
  ↓
VLM
  ↓
Frontend
  ↓
Observability
  ↓
Kubernetes
  ↓
Cloud
  ↓
Benchmarking
```

Each milestone is independently tested before the next layer is introduced.

---

# Local Development

The current local infrastructure uses Docker for PostgreSQL.

Start PostgreSQL:

```bash
docker compose -f infra/docker-compose.dev.yml up -d
```

Set the development database URL:

```bash
export DATABASE_URL="postgresql+psycopg://business_card_ai:business_card_ai_dev@localhost:5432/business_card_ai"
```

Apply migrations:

```bash
alembic upgrade head
```

Run the complete test suite:

```bash
pytest -v
```

---

# Database Migrations

Database schemas are version-controlled through Alembic.

Current migration:

```text
09aaba0e3a3e
create initial schema
```

Migration workflow:

```text
ORM model change
      ↓
Alembic migration
      ↓
Review migration
      ↓
Test upgrade
      ↓
Test downgrade
      ↓
Apply to environment
```

---

# Roadmap

### Phase 1 — Foundation

* [x] Repository structure
* [x] Domain schemas
* [x] SQLAlchemy models
* [x] PostgreSQL
* [x] Alembic
* [x] Configuration
* [x] Database session infrastructure

### Phase 2 — Application

* [ ] Transaction/service layer
* [ ] FastAPI application
* [ ] Job creation
* [ ] Job status
* [ ] Result retrieval

### Phase 3 — Storage & Processing

* [ ] S3 uploads
* [ ] Presigned URLs
* [ ] SQS
* [ ] Worker service
* [ ] Retry handling
* [ ] Dead-letter processing

### Phase 4 — AI

* [ ] Image preprocessing
* [ ] Qwen-VL integration
* [ ] Structured extraction
* [ ] Validation
* [ ] Normalization
* [ ] Review scoring

### Phase 5 — Product

* [ ] React frontend
* [ ] Bulk upload
* [ ] Progress tracking
* [ ] Lead table
* [ ] Excel export

### Phase 6 — Production Engineering

* [ ] Docker images
* [ ] Kubernetes
* [ ] Helm
* [ ] KEDA
* [ ] GPU workloads
* [ ] Observability
* [ ] Terraform
* [ ] CI/CD
* [ ] GitOps

### Phase 7 — Evaluation

* [ ] Accuracy benchmark
* [ ] Latency benchmark
* [ ] Throughput benchmark
* [ ] GPU utilization analysis
* [ ] Failure-rate analysis
* [ ] Cost/performance analysis

---

# Status

**Active development**

The repository currently represents the production foundation of a scalable multimodal extraction system. More application and infrastructure components will be introduced incrementally as they are validated by tests and benchmarks.


