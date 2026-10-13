# HL7 Mirth Auditor

A Python toolkit for inspecting HL7 v2 message streams, reporting selected structural/identifier findings, and masking common identifiers. It also includes a separate FastAPI supervisory service with demonstration QC thresholds and an HMAC-signed, in-memory audit trail.

## Browser application

The browser interface at `web/index.html` runs the **same Python HL7 parsing, audit, and masking modules** through Pyodide, without uploading message content. It accepts pasted text or local HL7 files (up to 2 MB), displays categorized findings without raw identifying values, and allows the masked stream to be downloaded.

To run it locally, from the repository root:

```bash
python -m http.server 8000
```

Open `http://localhost:8000/web/`. First use requires network access to download the pinned Pyodide runtime from jsDelivr; Python source files are served from the repository. The standalone browser interface needs no FastAPI backend.

**Important:** The audit implements selected checks, not complete HL7 conformance testing. The sanitizer performs **best-effort masking only**, not verified HIPAA Safe Harbor de-identification. Identifiers may persist in free-text, headers, notes, extension segments, or other fields. Do not use its output as certified de-identified data; review independently before sharing. Use synthetic messages for demonstrations.

## Python installation

Requires Python 3.9 or newer.

```bash
python -m pip install -e '.[server,test]'
python -m pytest -v
```

Core CLI (installed as `hl7-auditor`):

```bash
hl7-auditor audit -i sample_lab_stream.hl7
hl7-auditor sanitize -i sample_lab_stream.hl7 -o masked.hl7
hl7-auditor sample-hl7 -o sample.hl7
```

The audit command hides all raw source values by default. An explicit `--show-raw-values` flag is available for controlled local debugging, but should never be used in shared logs. Masking preserves the stream structure where feasible and uses per-process keyed pseudonyms; mappings are not stable across restarts.

## Supervisory service and API

The separate `agents/` workflow evaluates numeric sample metrics against **illustrative, non-validated thresholds**. It is not clinical decision support, a Mirth server, or an HL7 integration engine.

```bash
python cli.py audit --task-id T-001 --target SYNTH-01 --primary 28.5 --secondary 14.2
python cli.py batch -i tasks.csv -o results.csv
python cli.py verify-audit
python cli.py serve --host 127.0.0.1 --port 8000
```

API endpoints: `GET /health`, `GET /metrics`, `POST /api/audit`, `POST /api/chat`, `GET /api/audit/logs`.

By default, local operation is intended for trusted development. For any non-loopback listener, set `AUDITOR_API_KEY` to a high-entropy random value; the CLI refuses non-local binding without it. When configured, clients must provide `X-API-Key: <value>` for API operations other than health checks. Use HTTPS behind an authenticated reverse proxy for network deployment. Avoid submitting real patient information: regex-based safeguards are incomplete, and process memory contains submitted task identifiers.

Set `AUDIT_SECRET_KEY` to a stable, randomly generated secret when reproducible verification of the **current in-memory** HMAC chain matters. Without it, a new ephemeral signing key is used with a warning. Audit records are not persisted across process restarts.

## Containers

```bash
export AUDIT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export AUDITOR_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up --build
```

The container runs as an unprivileged user and requires both secrets. Do not commit them, include them in static site files, or publish private HL7 input.

## Repository layout

- `hl7_auditor/`: stream parser, auditing, masking, core CLI
- `agents/`: task models, worker evaluations, local audit trail, FastAPI
- `web/`: browser interface using Pyodide and local Python modules
- `tests/`: regression tests for parser, masking, API, validation, audit integrity
- `.github/workflows/`: Python CI and optional GitHub Pages delivery
- `simulator.py`, `enrichment.py`: supplementary demonstration workflows

## Technology, compatibility, and privacy

Python standard library (HL7 core), Pydantic, optional FastAPI/Uvicorn, Pyodide for modern browsers with JavaScript and WebAssembly support. The browser application processes messages locally; the Pyodide code runtime is downloaded externally on first load. The server application is separate and may receive submitted data. The complete project has not been independently validated for handling protected health information in production.

## License

MIT — see [LICENSE](LICENSE).
