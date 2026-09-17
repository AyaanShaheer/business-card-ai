# Back-of-the-Envelope Estimates & Capacity Planning

> Quantitative performance, storage, compute, bandwidth, and cost analysis for the **Business Card AI** platform.

This document outlines capacity planning and cost economics across three operational scales:
- **Tier 1 (Prototype / Evaluation)**: 1,000 business cards / day
- **Tier 2 (Mid-Market B2B / High Growth)**: 10,000 business cards / day
- **Tier 3 (Enterprise Scale / High-Volume SaaS)**: 100,000 business cards / day

---

## 1. Workload Assumptions & Core Constants

| Parameter | Baseline Value | Notes / Derivation |
| :--- | :--- | :--- |
| **Card Image Resolution** | $1200 \times 700$ px | Typical standard $3.5" \times 2"$ business card scanned at 300 DPI |
| **Average Raw Image Size** | **800 KB** (0.8 MB) | Compressed JPEG/PNG/WebP format |
| **Base64 Payload Size** | **1.07 MB** | Image raw bytes $\times 4/3$ overhead during VLM dispatch |
| **Average Inference Latency** | **5.5 seconds** | Remote Qwen 2.5 / 2-VL inference over HTTPS via OpenRouter/DashScope |
| **Inference Token Consumption** | ~1,250 tokens / card | ~1,150 image patch tokens (input) + ~100 JSON tokens (output) |
| **Normalized Lead Record** | **3.15 KB** | Combined storage per card: Document row + Lead row + Raw Extraction JSON |
| **Operating Window (Peak)** | **8 hours / day** | Most enterprise ingestion occurs during business hours ($28,800\text{ seconds}$) |

---

## 2. Storage Capacity Planning

### 2.1. Object Storage (Images)

Every uploaded business card image is persisted so users can view or re-extract cards if validation schemas change.

$$\text{Daily Image Storage} = \text{Cards/Day} \times 0.8\text{ MB}$$

| Metric | Tier 1 (1k/day) | Tier 2 (10k/day) | Tier 3 (100k/day) |
| :--- | :--- | :--- | :--- |
| **Daily Ingestion** | 800 MB | 8.0 GB | 80.0 GB |
| **Monthly Accumulation (30 Days)** | **24.0 GB** | **240.0 GB** | **2.40 TB** |
| **Annual Accumulation (365 Days)** | **292.0 GB** | **2.92 TB** | **29.2 TB** |
| **AWS S3 Standard Cost ($0.023/GB/mo)** | $0.55 / month | $5.52 / month | $55.20 / month |
| **S3 Lifecycle Tiering (Glacier Instant after 30d)** | $0.20 / month | $2.00 / month | $20.00 / month |

> **Storage Strategy Recommendation**:
> Retain uploaded card images in high-durability AWS S3 Standard with server-side AES-256 encryption. Apply an S3 Lifecycle policy that transitions raw image artifacts to S3 Glacier Instant Retrieval after 30 days and deletes them after 1 year, cutting long-term storage spend by over 70%.

---

### 2.2. Relational Database Storage (PostgreSQL)

Each extracted business card populates three relational entities:
1. **`documents` table**: $\approx 500\text{ bytes}$ (UUID, content hash, mime type, file size, status, foreign keys, timestamps).
2. **`leads` table**: $\approx 400\text{ bytes}$ (Normalized strings: name, title, company, location, phone, email).
3. **`extractions` table**: $\approx 2,000\text{ bytes}$ (Raw model response JSON, token usage metadata, inference latency, model version).
4. **B-Tree Index Overhead**: $\approx 25\%$ additional disk overhead for indexes on `job_id`, `content_hash`, and primary keys.

$$\text{Total Storage per Lead} \approx (500 + 400 + 2000) \times 1.25 \approx 3,625\text{ bytes} \approx 3.54\text{ KB}$$

| Metric | Tier 1 (1k/day) | Tier 2 (10k/day) | Tier 3 (100k/day) |
| :--- | :--- | :--- | :--- |
| **Daily DB Growth** | 3.54 MB | 35.4 MB | 354 MB |
| **Monthly DB Growth (30 Days)** | **106.2 MB** | **1.06 GB** | **10.62 GB** |
| **Annual DB Growth (365 Days)** | **1.29 GB** | **12.9 GB** | **129.2 GB** |
| **RDS PostgreSQL Storage Required** | 20 GB gp3 | 50 GB gp3 | 250 GB gp3 |
| **Monthly RDS Storage Cost ($0.115/GB)** | $2.30 / month | $5.75 / month | $28.75 / month |

---

### 2.3. Redis In-Memory Queue Footprint

The message queue holds references to uncompleted documents (`DocumentMessage`: `document_id`, `job_id`, `storage_path`, `retry_count`).

- **Queue Item Size**: $\approx 150\text{ bytes}$ (JSON formatted string).
- **Peak Backlog Buffer**: Suppose an upstream VLM API rate-limit stalls processing for 30 minutes during peak hours:
  - At Tier 2 (10,000 cards / 8 hrs) = $1,250\text{ cards/hr}$. In 30 minutes, 625 items accumulate.
  - Queue memory consumption = $625 \times 150\text{ bytes} \approx 94\text{ KB}$.
  - Even with a catastrophic 100,000 item backlog, memory consumed is only $\mathbf{15\text{ MB}}$.
- **Conclusion**: Redis memory requirements are trivial. A standard 256MB Redis Alpine container or minimal AWS ElastiCache instance (`cache.t4g.micro`, 0.5 GB RAM) provides 10x safety headroom.

---

## 3. Compute & Worker Concurrency Sizing

### 3.1. Single Worker Throughput

Each document worker process executes the following sequential steps per item:
1. **Redis `LPOP`**: $< 1\text{ ms}$
2. **Disk / S3 Read**: $20 - 50\text{ ms}$
3. **Base64 Encoding**: $10 - 20\text{ ms}$
4. **VLM Remote Inference**: $5,000 - 6,000\text{ ms}$ (Bottleneck)
5. **Pydantic Validation**: $5\text{ ms}$
6. **PostgreSQL Write**: $15\text{ ms}$
7. **Total Cycle Time ($T$)**: $\approx \mathbf{5.5\text{ seconds}}$ per document.

$$\text{Throughput per Single Worker} = \frac{1\text{ card}}{5.5\text{ sec}} \approx 0.182\text{ cards/sec} \approx 10.9\text{ cards/min} \approx 654\text{ cards/hour}$$

---

### 3.2. Worker Sizing for Peak Traffic

Assuming all daily volume is ingested during an **8-hour peak business window** ($28,800\text{ seconds}$):

$$\text{Required Throughput } (R) = \frac{\text{Daily Cards}}{28,800\text{ sec}}$$

$$\text{Required Concurrent Workers } (N) = \left\lceil \frac{R}{\text{Single Worker Throughput}} \right\rceil = \lceil R \times 5.5 \rceil$$

| Workload Tier | Peak Ingestion Rate | Single Worker Capacity | Required Worker Concurrency ($N$) | Target Provisioning (with $1.5\times$ burst buffer) |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1 (1k/day)** | $0.035\text{ cards/sec}$ ($125/\text{hr}$) | $654/\text{hr}$ | $\mathbf{0.2} \implies \mathbf{1\text{ worker}}$ | **1 worker thread** |
| **Tier 2 (10k/day)** | $0.347\text{ cards/sec}$ ($1,250/\text{hr}$) | $654/\text{hr}$ | $\mathbf{1.9} \implies \mathbf{2\text{ workers}}$ | **3 - 4 worker processes** |
| **Tier 3 (100k/day)** | $3.472\text{ cards/sec}$ ($12,500/\text{hr}$) | $654/\text{hr}$ | $\mathbf{19.1} \implies \mathbf{20\text{ workers}}$ | **25 - 30 worker processes** |

> **Key Insight**: Because the worker is I/O-bound (waiting on external VLM inference for 98% of the cycle time), multiple worker threads or asynchronous `asyncio` coroutines can run concurrently on a single CPU core without high CPU utilization.

---

## 4. Network Bandwidth & Transfer Estimates

$$\text{Inbound Ingestion Bandwidth} = \text{Throughput} \times 0.8\text{ MB}$$
$$\text{Outbound Inference Bandwidth} = \text{Throughput} \times 1.07\text{ MB}$$

| Metric | Tier 1 (1k/day) | Tier 2 (10k/day) | Tier 3 (100k/day) |
| :--- | :--- | :--- | :--- |
| **Average Ingestion Rate** | $0.035\text{ cards/sec}$ | $0.35\text{ cards/sec}$ | $3.5\text{ cards/sec}$ |
| **Inbound Bandwidth (Upload)** | $0.22\text{ Mbps}$ | $2.24\text{ Mbps}$ | $22.4\text{ Mbps}$ |
| **Outbound Bandwidth (to VLM)** | $0.30\text{ Mbps}$ | $3.00\text{ Mbps}$ | $30.0\text{ Mbps}$ |
| **Monthly Inbound Data Transfer** | 24 GB | 240 GB | 2.4 TB |
| **Monthly Outbound Data Transfer** | 32 GB | 320 GB | 3.2 TB |

AWS provides free inbound data transfer. Outbound internet egress to OpenRouter / external endpoints costs $\approx \$0.09/\text{GB}$ after the first 100 GB/month.

---

## 5. End-to-End Financial Cost Analysis (FinOps)

### 5.1. Option A: Managed API Inference (Current Architecture)
*Model: Qwen 2.5 72B / Qwen 2-VL 7B via OpenRouter or Alibaba DashScope ($0.40 / 1M input tokens, $0.80 / 1M output tokens).*

- **Input Cost per Card**: $1,150\text{ tokens} \times \$0.0000004 = \$0.00046$
- **Output Cost per Card**: $100\text{ tokens} \times \$0.0000008 = \$0.00008$
- **Total Model Cost per Card**: **$\approx \$0.00054$** ($0.054\text{ cents / card}$, or **\$0.54 per 1,000 cards**)

#### Monthly Cost Breakdown:

| Resource | Tier 1 (30k cards/mo) | Tier 2 (300k cards/mo) | Tier 3 (3M cards/mo) |
| :--- | :--- | :--- | :--- |
| **VLM Model Invocations** | $16.20 | $162.00 | $1,620.00 |
| **AWS Compute (EC2 / ECS Fargate)** | $10.00 (t4g.small) | $45.00 (2 Fargate tasks) | $210.00 (Autoscaled tasks) |
| **Managed Database (RDS PostgreSQL)** | $15.00 (db.t4g.micro) | $32.00 (db.t4g.small) | $95.00 (db.r6g.large) |
| **Managed Queue (ElastiCache Redis)** | $13.00 (cache.t4g.micro) | $13.00 (cache.t4g.micro) | $26.00 (cache.t4g.small) |
| **Object Storage (Amazon S3)** | $0.60 | $5.50 | $55.00 |
| **Data Transfer / Networking** | $0.00 (Free Tier) | $18.00 | $180.00 |
| **Total Monthly Cost** | **$54.80 / month** | **$275.50 / month** | **$2,186.00 / month** |
| **Cost per Extracted Lead** | **$0.0018** (0.18¢) | **$0.0009** (0.09¢) | **$0.0007** (0.07¢) |

---

### 5.2. Option B: Self-Hosted GPU Inference (vLLM on AWS EC2)
*Deploying Qwen 2.5-VL 7B on dedicated AWS GPU instances using vLLM.*

- **Instance Type**: `g5.xlarge` (1x NVIDIA A10G 24GB VRAM, 4 vCPUs, 16GB RAM).
- **On-Demand Hourly Rate**: $\$1.006 / \text{hour} \approx \mathbf{\$734 / \text{month}}$.
- **1-Year Reserved Instance**: $\approx \mathbf{\$450 / \text{month}}$.
- **vLLM PagedAttention Throughput**: With continuous batching, a single A10G can process $\approx 4\text{ images/sec}$ ($\approx 14,400\text{ cards/hour}$).

#### Breakeven Analysis: Managed API vs. Self-Hosted GPU
$$\text{Cost}_{\text{API}}(V) = V \times \$0.00054$$
$$\text{Cost}_{\text{Self-Hosted}} = \$450\text{ (1-Yr RI GPU)} + \$50\text{ (Platform/EBS)} = \$500/\text{month}$$

$$\text{Breakeven Volume } (V^*) = \frac{\$500}{\$0.00054} \approx \mathbf{925,000\text{ cards / month}}$$

> **Strategic Architecture Verdict**:
> - For **Tier 1 (30k/mo)** and **Tier 2 (300k/mo)**, **Managed API is dramatically cheaper and operationally superior** ($55 – $275/mo vs $500/mo minimum for GPU idle hours).
> - For **Tier 3 (>1M cards/mo)**, switching to self-hosted vLLM on dedicated GPUs saves thousands of dollars monthly and guarantees custom SLAs.

---

## 6. Bottleneck & SLA Sensitivity Matrix

| Failure Mode / Bottleneck | Impact on System | Detection Mechanism | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **VLM API Rate Limiting (HTTP 429)** | Document processing stalls; queue depth grows | Worker increments retry count; logs 429 | Exponential backoff with jitter ($2^n \times 1\text{s}$); dynamic queue pause |
| **Network Partition (API to OpenRouter)** | VLM requests timeout after 30s | `httpx.TimeoutException` caught in worker | Mark document `FAILED`, alert user via UI progress, allow single-click retry |
| **Sudden Ingestion Spike (1,000 cards in 10s)** | Upload succeeds instantly, queue accumulates | `LLEN document_processing_queue` increases | Web API remains fast (<200ms); worker drains queue linearly without crashing |
| **Host Process Crash / OOM** | Active document in-flight is interrupted | Container restart; status left as `PENDING` | `recover_pending_documents()` on worker boot restarts uncompleted jobs |

---

## 7. Summary Scorecard

```text
+------------------------+-------------------+--------------------+--------------------+
| Parameter              | Tier 1 (1k/day)   | Tier 2 (10k/day)   | Tier 3 (100k/day)  |
+------------------------+-------------------+--------------------+--------------------+
| Monthly Ingestion      | 24 GB             | 240 GB             | 2.4 TB             |
| Monthly DB Growth      | 106 MB            | 1.06 GB            | 10.6 GB            |
| Worker Concurrency     | 1 process         | 4 processes        | 25 processes       |
| Ingress Bandwidth      | 0.22 Mbps         | 2.24 Mbps          | 22.4 Mbps          |
| Monthly Infrastructure | ~$55 / mo         | ~$275 / mo         | ~$2,185 / mo       |
| Cost Per 100 Leads     | $0.18             | $0.09              | $0.07              |
+------------------------+-------------------+--------------------+--------------------+
```
