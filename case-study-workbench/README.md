# Evidence-First Case Study Workbench

Public-safe scaffold for a review-gated case-study automation pipeline.

This repository demonstrates the architecture and testable safety controls for
an evidence-first workflow:

- register and snapshot sources
- parse HTML/PDF documents while preserving locators
- extract structured metadata without guessing missing fields
- split public text into claim-level records
- route sensitive or uncertain claims to human review
- export only approved claims to public JSON

## Public-Safe Scope

This repo intentionally excludes:

- original workbooks and implementation notes
- real project seed data
- internal reviewer notes or supervisor-facing judgments
- private URLs, snapshots, or source archives
- local virtual environments and cache files

Tests use synthetic fixtures only.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/mypy src
```

## Core Modules

- `source_registry.py`: URL normalization, content hashing, snapshot records
- `fetch/client.py`: injectable HTTP fetcher with conservative failure routing
- `parse/document.py`: HTML/PDF parsing with stable locators
- `extract/metadata.py`: structured metadata extraction with no-guess behavior
- `classify/claim_extraction.py`: sentence-to-claim decomposition
- `classify/claim_boundary.py`: high-risk claim transformation controls
- `review/routing.py`: mandatory, targeted, random-audit, and blocked routes
- `review/queue.py`: review queue item builder
- `export/public_json.py`: approved-only JSON export

## Static Review Prototype

Open `review_app/index.html` to inspect a synthetic review queue prototype. It
shows route filters, claim/source side-by-side review, locator display, notes,
and local approve/change/park decision controls. The prototype uses
`review_app/sample_queue.json` only; it does not contain real case data.
