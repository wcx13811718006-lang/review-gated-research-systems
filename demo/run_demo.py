from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research_systems_showcase.pipeline import run_demo_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the public showcase demo for review-gated research systems."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "demo" / "sample_outputs",
        help="Directory for generated demo artifacts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = run_demo_pipeline(
        input_dir=PROJECT_ROOT / "demo" / "sample_inputs",
        output_dir=args.output_dir,
    )

    print("Demo run completed.")
    print(
        f"Approved for analysis: {manifest['summary']['approved_for_analysis']} | "
        f"Needs review: {manifest['summary']['needs_human_review']}"
    )
    print("Artifacts:")
    for name, relative_path in manifest["artifact_manifest"].items():
        print(f"  - {name}: {relative_path}")


if __name__ == "__main__":
    main()
