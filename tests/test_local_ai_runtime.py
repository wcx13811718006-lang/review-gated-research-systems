from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research_systems_showcase.local_ai.assistant import run_local_research_prompt
from src.research_systems_showcase.local_ai.quality import evaluate_local_answer
from src.research_systems_showcase.local_ai.replay import compare_prefixed_columns


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

    def test_malformed_pdf_source_is_not_treated_as_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "out"
            pdf_path = Path(tmp_dir) / "sample.pdf"
            pdf_path.write_bytes(b"%PDF-1.7\n\x00\x01binary-ish content")

            manifest = run_local_research_prompt(
                user_prompt="Smoke test PDF handling.",
                repo_root=PROJECT_ROOT,
                config_path=PROJECT_ROOT / "configs" / "local_ai.example.json",
                source_paths=[pdf_path],
                output_dir=output_dir,
                dry_run=True,
            )
            request_text = Path(manifest["artifacts"]["request"]).read_text(encoding="utf-8")

            self.assertIn("pdf_extraction_failed", request_text)
            self.assertTrue(manifest["review_required"])

    def test_docx_source_can_be_read_for_local_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "out"
            docx_path = Path(tmp_dir) / "sample.docx"
            document_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t>Local legal memo text for validation.</w:t></w:r></w:p></w:body>"
                "</w:document>"
            )
            with ZipFile(docx_path, "w") as archive:
                archive.writestr("word/document.xml", document_xml)

            manifest = run_local_research_prompt(
                user_prompt="Smoke test DOCX handling.",
                repo_root=PROJECT_ROOT,
                config_path=PROJECT_ROOT / "configs" / "local_ai.example.json",
                source_paths=[docx_path],
                output_dir=output_dir,
                dry_run=True,
            )
            request_text = Path(manifest["artifacts"]["request"]).read_text(encoding="utf-8")

            self.assertIn("Local legal memo text for validation.", request_text)
            self.assertTrue(manifest["review_required"])

    def test_replay_comparison_reports_field_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            csv_path = root / "benchmark.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "row_id,benchmark_FinalDecision,review_machine_FinalDecision,benchmark_Plaintiff,review_machine_Plaintiff",
                        "1,1,1,Client Earth,Client Earth",
                        "2,0,1,Green Group,Green Group",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            output_path = root / "report.json"

            report = compare_prefixed_columns(csv_path=csv_path, output_path=output_path)

            self.assertEqual(report["row_count"], 2)
            self.assertEqual(report["total_compared_cells"], 4)
            self.assertEqual(report["total_mismatches"], 1)
            self.assertIn("FinalDecision", report["review_cost_signal"]["fields_requiring_review"])
            self.assertEqual(report["field_summary"]["FinalDecision"]["candidate_blank_mismatches"], 0)
            self.assertTrue(output_path.exists())

    def test_replay_comparison_reports_empty_candidate_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            csv_path = root / "benchmark.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "row_id,benchmark_FinalDecision,review_machine_FinalDecision",
                        "1,1,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            report = compare_prefixed_columns(csv_path=csv_path, output_path=root / "report.json")

            self.assertEqual(report["field_summary"]["FinalDecision"]["candidate_blank_mismatches"], 1)
            self.assertIn(
                "FinalDecision",
                report["review_cost_signal"]["fields_with_empty_candidate_outputs"],
            )


if __name__ == "__main__":
    unittest.main()
