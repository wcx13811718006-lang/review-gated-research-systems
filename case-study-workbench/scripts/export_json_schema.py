from __future__ import annotations

import json
from pathlib import Path

from carwash.schemas import (
    Case,
    Claim,
    ExtractedSourceMetadata,
    ParsedDocument,
    PublicationArtifact,
    Review,
    ReviewQueueItem,
    SeasonalContext,
    Source,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "data" / "fixtures" / "carwash_json_schema.json"
    schema_bundle = {
        "Case": Case.model_json_schema(),
        "Source": Source.model_json_schema(),
        "Claim": Claim.model_json_schema(),
        "ParsedDocument": ParsedDocument.model_json_schema(),
        "ExtractedSourceMetadata": ExtractedSourceMetadata.model_json_schema(),
        "Review": Review.model_json_schema(),
        "ReviewQueueItem": ReviewQueueItem.model_json_schema(),
        "PublicationArtifact": PublicationArtifact.model_json_schema(),
        "SeasonalContext": SeasonalContext.model_json_schema(),
    }
    output.write_text(json.dumps(schema_bundle, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
