# Architecture

This public showcase demonstrates a compact version of a review-gated research system. The design favors inspectable stages over hidden automation and keeps uncertainty visible throughout the pipeline.

## System Overview

```mermaid
flowchart LR
    A["Public-safe inputs"] --> B["Ingestion"]
    B --> C["Routing"]
    C --> D["Validation gate"]
    D -->|approved| E["Analysis-ready export"]
    D -->|review required| F["Structured review packet"]
    D -->|not suitable| G["Hold / exclude"]
    F --> H["Human review"]
    H -->|approve or revise| E
    H -->|decline or defer| G
```

If Mermaid rendering is weak in your viewer, the fallback reading is: ingest first, route second, validate third, and only export after the record clears the gate. Review and hold states are explicit outcomes, not hidden exceptions.

## Module Boundaries

```mermaid
flowchart LR
    subgraph Inputs
        A1["sample_links.csv"]
        A2["sample_metadata.json"]
        A3["sample_pdf_placeholder.txt"]
    end

    subgraph Pipeline
        B1["ingest.loader"]
        B2["routing.router"]
        B3["validation.checks"]
        B4["review.packets"]
        B5["export.writer"]
        B6["utils.progress"]
    end

    subgraph Outputs
        C1["routing_decisions.json"]
        C2["review_packet.md"]
        C3["final_export.json"]
        C4["progress_log.jsonl"]
        C5["system_status.csv"]
    end

    A1 --> B1
    A2 --> B1
    A3 --> B1
    B1 --> B2
    B2 --> B3
    B3 --> B4
    B3 --> B5
    B4 --> C2
    B5 --> C1
    B5 --> C3
    B5 --> C5
    B6 --> C4
```

## Design Notes

- Inputs are treated as research support artifacts, not as automatically trusted evidence.
- Routing is explicit and narrow: the pipeline first decides where an item should go before asking whether it is ready to move forward.
- Validation is a gate, not a logging afterthought.
- Review packets are written for humans, with enough context to understand why an item was paused.
- Exports separate analysis-ready records from records still waiting for review.
- A downstream analysis brief is generated so approved records are immediately usable in later research-support tasks.

For quicker visual skimming, see [`../diagrams/README.md`](../diagrams/README.md).
