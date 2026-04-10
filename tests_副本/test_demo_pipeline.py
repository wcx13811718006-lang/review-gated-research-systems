from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research_systems_showcase.pipeline import run_demo_pipeline


class DemoPipelineTests(unittest.TestCase):
    def test_demo_pipeline_writes_expected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            manifest = run_demo_pipeline(
                input_dir=PROJECT_ROOT / "demo" / "sample_inputs",
                output_dir=output_dir,
            )

            self.assertEqual(manifest["summary"]["records_processed"], 3)
            self.assertTrue((output_dir / "review_packet.md").exists())
            self.assertTrue((output_dir / "final_export.json").exists())
            self.assertTrue((output_dir / "progress_log.jsonl").exists())
            self.assertTrue((output_dir / "system_status.csv").exists())
            self.assertTrue((output_dir / "analysis_brief.md").exists())

    def test_degraded_pdf_is_routed_to_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            manifest = run_demo_pipeline(
                input_dir=PROJECT_ROOT / "demo" / "sample_inputs",
                output_dir=output_dir,
            )

            self.assertEqual(manifest["summary"]["needs_human_review"], 2)
            review_packet_text = (output_dir / "review_packet.md").read_text(encoding="utf-8")
            self.assertIn("pdf_policy_appendix", review_packet_text)
            analysis_brief_text = (output_dir / "analysis_brief.md").read_text(encoding="utf-8")
            self.assertIn("Analysis-Ready Records", analysis_brief_text)


if __name__ == "__main__":
    unittest.main()
