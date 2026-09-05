# HL7 Mirth Auditor

> **Domain:** Clinical Decision Support & Biomedical Computing
> **Standards:** CAP / CLSI / ISO / HIPAA Safe Harbor

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg?logo=fastapi&logoColor=white)
![Audit Trail](https://img.shields.io/badge/Audit-HMAC--SHA256_Tamper--Evident-brightgreen.svg)
![Zero-PHI Guard](https://img.shields.io/badge/Guard-Zero--PHI_Outbound-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)

</div>

---

## Overview

**HL7 Mirth Auditor** is a clinical LIS/HIS HL7 v2.x message stream inspector, validation engine, and HIPAA Safe Harbor PHI sanitizer. It provides:

- **HL7 v2.x Stream Parser** — Parses HL7 message files with proper delimiter extraction and multi-message support
- **Structural & PHI Auditor** — Validates message structure, detects PHI (MRN, SSN, DOB, names, phone numbers), and flags abnormal lab results
- **PHI Sanitizer** — De-identifies HL7 messages using HIPAA Safe Harbor methods (pseudonymization, redaction, date shifting)
- **Multi-Agent Supervisor** — Distributed task evaluation with specialized workers (QC, Safety, Protocol Conformance)
- **HMAC-SHA256 Audit Trail** — Tamper-evident cryptographic logging of all operations
- **FastAPI REST API** — HTTP endpoints for audit, chat, and metrics
- **Zero-PHI Outbound Guard** — Prevents accidental PHI leakage in outbound data

---

## Installation

```bash
# Clone the repository
git clone https://github.com/abusuraihsakhri/hl7-mirth-auditor.git
cd hl7-mirth-auditor

# Install dependencies
pip install fastapi uvicorn pydantic pytest
```

---

## Usage

### HL7 Message Auditing (hl7_auditor CLI)

```bash
# Audit an HL7 message file for syntax errors, PHI, and clinical issues
python -m hl7_auditor.cli audit -i sample_lab_stream.hl7

# Sanitize (de-identify) an HL7 message file
python -m hl7_auditor.cli sanitize -i sample_lab_stream.hl7 -o sanitized_output.hl7

# Generate a sample HL7 ORU^R01 stream
python -m hl7_auditor.cli sample-hl7 -o my_sample.hl7
```

### Multi-Agent Supervisor CLI

```bash
# Run a single task evaluation
python cli.py audit --task-id TASK-001 --target SPECIMEN-01 --primary 28.5 --secondary 14.2

# Batch process CSV records
python cli.py batch -i input.csv -o results.csv

# Verify HMAC audit trail integrity
python cli.py verify-audit

# Query the supervisory chat
python cli.py chat "Explain current system status"

# Launch FastAPI REST server
python cli.py serve --host 127.0.0.1 --port 8000
```

### FastAPI REST API

```bash
# Start the server
python cli.py serve

# Health check
curl http://localhost:8000/health

# Prometheus metrics
curl http://localhost:8000/metrics

# Submit audit task
curl -X POST http://localhost:8000/api/audit \
  -H "Content-Type: application/json" \
  -d '{"task_id":"T001","target_identifier":"SPEC-01","primary_metric":25.0,"secondary_metric":10.0,"status_descriptor":"NOMINAL"}'

# View audit logs
curl http://localhost:8000/api/audit/logs
```

### High-Throughput Simulation

```bash
# Run 1000-task simulation benchmark
python simulator.py 1000
```

---

## Project Structure

```
hl7-mirth-auditor/
├── hl7_auditor/          # Core HL7 message processing package
│   ├── models.py         # HL7 data models (HL7Message, HL7Segment, etc.)
│   ├── parser.py         # HL7 v2.x stream parser
│   ├── auditor.py        # Structural, clinical, and PHI compliance auditor
│   ├── sanitizer.py      # HIPAA Safe Harbor de-identification engine
│   └── cli.py            # CLI for HL7 operations
├── agents/               # Multi-agent supervisor system
│   ├── base.py           # PHI guard, HMAC-SHA256 audit trail, security
│   ├── models.py         # Pydantic schemas (SystemTaskPayload, ConsensusDossier)
│   ├── workers.py        # Specialized evaluation workers
│   ├── supervisor.py     # Master orchestrator
│   ├── api.py            # FastAPI REST endpoints
│   ├── llm_factory.py    # LLM provider abstraction
│   ├── learning.py       # Bayesian calibration engine
│   ├── metrics.py        # Prometheus metrics collector
│   └── streamer.py       # WebSocket telemetry broadcaster
├── tests/                # Pytest test suite
├── web/index.html        # Operations console UI
├── cli.py                # Main CLI entry point
├── simulator.py          # High-throughput simulation tool
├── enrichment.py         # Additional domain agent modules
├── Dockerfile            # Container build
└── docker-compose.yml    # Container orchestration
```

---

## Security Features

- **Zero-PHI Outbound Interceptor:** AST and regex inspection blocking SSNs, MRNs, phone numbers, emails, DOBs, and patient identifiers
- **Tamper-Evident HMAC-SHA256 Audit Trail:** Chained, cryptographically signed logs for every evaluation
- **Secure Key Management:** HMAC secret loaded from `AUDIT_SECRET_KEY` environment variable; generates ephemeral key with warning if unset
- **PHI Sanitization:** HIPAA Safe Harbor de-identification with pseudonymization and redaction

### Environment Variables

| Variable | Description | Default |
|:---------|:------------|:--------|
| `AUDIT_SECRET_KEY` | HMAC signing key for audit trail | Random ephemeral (warns if unset) |
| `MODEL_PROVIDER` | LLM provider (`mock`, `ollama`, `claude`, `openai`) | `mock` |

---

## Testing

```bash
# Run full test suite
pytest -v

# Run with coverage
pytest -v --cov=hl7_auditor --cov=agents
```

---

## Docker Deployment

```bash
# Build and run with Docker Compose
export AUDIT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
docker-compose up --build

# Or build manually
docker build -t hl7-mirth-auditor .
docker run -p 8000:8000 -e AUDIT_SECRET_KEY=your-secret-key hl7-mirth-auditor
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.
