# Correlation Agent — Handoff Notes

## What's Done

| Layer | Status |
|---|---|
| LangGraph agent pipeline | ✅ Complete |
| XGBoost correlation scoring | ✅ Complete |
| CockroachDB as persistent memory layer | ✅ Complete (replace DB URL in `.env`) |
| CockroachDB Vector Indexing (semantic memory) | ✅ Complete — Gemini embeddings stored per incident |
| CockroachDB MCP Server config | ✅ Complete (`.mcp.json` — replace URL) |
| Gemini Flash for LLM reasoning | ✅ Complete |
| Gemini text-embedding-004 for vectors | ✅ Complete |
| FastAPI REST API | ✅ Complete |
| `Dockerfile` | ✅ Written — ready to build |
| `.dockerignore` | ✅ Written |
| `requirements.txt` | ✅ Written |

## What Needs to Be Done (Your Part)

### 1. Set Up Secrets

Copy `.env.example` → `.env` and fill in the two values:

```bash
cp .env.example .env
```

```
COCKROACHDB_URL=postgresql+psycopg2://user:pass@host.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full
GEMINI_API_KEY=your-gemini-key
```

> ⚠️ Never commit `.env` — it is in `.gitignore`

---

### 2. Prerequisites to Install

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows)
- [AWS CLI](https://aws.amazon.com/cli/)

After installing AWS CLI:
```bash
aws configure
# Enter: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, region (us-east-1), output (json)
```

AWS IAM user needs: `AmazonECS_FullAccess` + `AmazonEC2ContainerRegistryFullAccess`

---

### 3. Deploy to AWS ECS

Replace `YOUR_AWS_ACCOUNT_ID` with your actual 12-digit AWS account ID throughout.

```bash
# Step 1 — Create ECR repository
aws ecr create-repository --repository-name correlation-agent --region us-east-1

# Step 2 — Log Docker into ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Step 3 — Build Docker image
docker build -t correlation-agent .

# Step 4 — Tag the image
docker tag correlation-agent:latest YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/correlation-agent:latest

# Step 5 — Push to ECR
docker push YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/correlation-agent:latest

# Step 6 — Create ECS cluster
aws ecs create-cluster --cluster-name correlation-agent-cluster --region us-east-1
```

### 4. Create ECS Task Definition (AWS Console)

Go to **AWS Console → ECS → Task Definitions → Create new task definition**:

| Setting | Value |
|---|---|
| Launch type | Fargate |
| OS | Linux/X86_64 |
| CPU | 0.5 vCPU |
| Memory | 1 GB |
| Container image | `YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/correlation-agent:latest` |
| Port mappings | None needed (agent polls DB, no inbound traffic) |

Under **Environment variables**, add:

| Key | Value |
|---|---|
| `COCKROACHDB_URL` | Your CockroachDB connection string |
| `GEMINI_API_KEY` | Your Gemini API key |

### 5. Run the Task

In **ECS → Clusters → correlation-agent-cluster → Run new task**:
- Launch type: Fargate
- Select the task definition you created
- VPC: use default
- Subnets: pick any public subnet
- Auto-assign public IP: **ENABLED**

The agent will start, connect to CockroachDB, set up the vector schema, and begin polling for alerts.

---

## Architecture Overview

```
[AWS ECS Fargate]
    └── python run.py (LangGraph agent loop)
           │
           ├── fetch_alerts → CockroachDB (reads unprocessed alerts)
           ├── score_alert  → XGBoost model (local in container)
           ├── decide       → merge or create incident
           ├── reason_node  → Gemini text-embedding-004 (embed alert)
           │                → CockroachDB VECTOR index (find similar past incidents)
           │                → Gemini Flash (generate explanation with memory context)
           └── persist_node → CockroachDB (write incident + store embedding vector)
```

## CockroachDB Tools Used

1. **Distributed Vector Indexing** — `incidents.embedding VECTOR(768)` column with ivfflat index.
   The agent queries this index with cosine similarity to retrieve semantically similar past incidents as memory context for the LLM.

2. **Cloud Managed MCP Server** — see `.mcp.json`. Replace `COCKROACHDB_CONNECTION_STRING` with your cluster URL.
   Lets Claude/Cursor query the live cluster during development (read-only, zero code required).

## Starting Locally (Without ECS)

```bash
# 1. Create venv and install deps
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 2. Fill in .env (see step 1 above)

# 3. Run the agent
python run.py

# 4. Run the API (separate terminal)
uvicorn api.main:app --reload --port 8000
```
