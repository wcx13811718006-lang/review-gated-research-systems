# Diagrams

This folder collects the main diagrams for the public showcase. The Mermaid versions below are intended for GitHub rendering. If Mermaid does not display well in your viewer, each diagram is followed by a short plain-language fallback explanation.

## 1. Top-Level Architecture

```mermaid
flowchart LR
    A["Public-safe inputs"] --> B["Ingestion"]
    B --> C["Routing"]
    C --> D["Validation gate"]
    D -->|approved| E["Analysis-ready export"]
    D -->|review required| F["Review packet"]
    D -->|not suitable| G["Hold / exclude"]
    F --> H["Human review"]
    H -->|approve or revise| E
    H -->|decline or defer| G
```

Fallback reading: records are ingested, routed, and validated before they are exported. Uncertain records go to review. Unsuitable records are held back.

## 2. Routing And Review Decision Flow

```mermaid
flowchart TD
    A["New record"] --> B["Assign source lane"]
    B --> C["Run validation checks"]
    C -->|checks pass| D["Approved for analysis"]
    C -->|metadata weak or extraction degraded| E["Create review packet"]
    E --> F["Human review"]
    F -->|approve| D
    F -->|revise and resubmit| C
    F -->|exclude or defer| G["Hold"]
```

Fallback reading: the system does not force every record straight to export. If evidence is weak, it creates a review packet and waits for a human decision.

## 3. Compact Record Lifecycle

```mermaid
flowchart LR
    A["Intake"] --> B["Routed"]
    B --> C["Validated"]
    C -->|clear| D["Analysis-ready"]
    C -->|uncertain| E["Review-gated"]
    C -->|not fit| F["Held"]
    E --> G["Reviewed"]
    G -->|approved| D
    G -->|not approved| F
```

Fallback reading: the key lifecycle distinction is between analysis-ready, review-gated, and held records.

## 4. Module Map

```mermaid
flowchart LR
    A["ingest"] --> B["routing"]
    B --> C["validation"]
    C --> D["review"]
    C --> E["export"]
    F["utils"] --> A
    F --> B
    F --> C
    F --> D
    F --> E
```

Fallback reading: the public code is intentionally modular. Ingestion, routing, validation, review, and export are separated so each stage remains inspectable.
