from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research_systems_showcase.local_ai.assistant import run_local_research_prompt
from src.research_systems_showcase.local_ai.quality import evaluate_local_answer


class LocalAIRuntimeTests(unittest.TestCase):
    def test_quality_gate_blocks_unreviewed_model_output(self) -> None:
        gate = evaluate_local_answer(
            answer="A cautious draft answer with enough characters to pass the simple length check.",
            source_context="source " * 100,
            backend_status={"reachable": True, "status_label": "reachable"},
            quality_config={
                "allow_final_without_review": False,
                "require_human_review": True,
                "minimum_answer_characters": 10,
                "minimum_source_context_characters": 10,
            },
        )

        self.assertEqual(gate["decision"], "needs_human_review")
        self.assertTrue(gate["review_required"])
        self.assertFalse(gate["can_export_final"])

    def test_quality_gate_flags_reasoning_only_output(self) -> None:
        gate = evaluate_local_answer(
            answer="LM Studio returned reasoning content without a final answer.\n\nThinking Process...",
            source_context="source " * 100,
            backend_status={"reachable": True, "status_label": "reachable"},
            quality_config={
                "allow_final_without_review": False,
                "require_human_review": True,
                "minimum_answer_characters": 10,
                "minimum_source_context_characters": 10,
            },
        )

        self.assertIn("final_answer_present", gate["failed_checks"])
        self.assertTrue(gate["review_required"])

    def test_dry_run_writes_review_gated_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            manifest = run_local_research_prompt(
                user_prompt="Smoke test local AI artifacts.",
                repo_root=PROJECT_ROOT,
                config_path=PROJECT_ROOT / "configs" / "local_ai.example.json",
                source_paths=[PROJECT_ROOT / "README.md"],
                output_dir=output_dir,
                dry_run=True,
            )

            self.assertTrue(manifest["review_required"])
            self.assertFalse(manifest["can_export_final"])
            self.assertTrue(Path(manifest["artifacts"]["request"]).exists())
            self.assertTrue(Path(manifest["artifacts"]["draft_response"]).exists())
            self.assertTrue(Path(manifest["artifacts"]["review_gate"]).exists())


if __name__ == "__main__":
    unittest.main()
