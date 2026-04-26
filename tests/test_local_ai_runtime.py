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
from src.research_systems_showcase.local_ai.ideation import build_source_profile, run_literature_ideation
from src.research_systems_showcase.local_ai.local_console import (
    LocalConsoleJobManager,
    render_console_html,
    render_workbench_html,
)
from src.research_systems_showcase.local_ai.quality import evaluate_local_answer
from src.research_systems_showcase.local_ai.replay import compare_prefixed_columns
from src.research_systems_showcase.local_ai.system_monitor import (
    build_model_routing_advice,
    collect_token_snapshot,
    estimate_tokens,
)
from src.research_systems_showcase.local_ai.token_compression import compress_text


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

    def test_source_profile_extracts_keywords_for_ideation(self) -> None:
        profile = build_source_profile(
            "Climate litigation may affect transition risk through policy uncertainty. "
            "Litigation records can provide document-level signals for investment research."
        )

        terms = {item["term"] for item in profile["keyword_candidates"]}
        self.assertIn("litigation", terms)
        self.assertGreater(profile["source_context_characters"], 50)

    def test_ideation_dry_run_writes_review_gated_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            source_path = output_dir / "source.txt"
            source_path.write_text(
                "Climate litigation affects investment risk through legal uncertainty, "
                "reputational channels, and policy implementation pressure.",
                encoding="utf-8",
            )

            manifest = run_literature_ideation(
                focus="Generate research ideas about climate litigation and investment risk.",
                repo_root=PROJECT_ROOT,
                config_path=PROJECT_ROOT / "configs" / "local_ai.example.json",
                source_paths=[source_path],
                output_dir=output_dir,
                idea_count=3,
                dry_run=True,
            )

            self.assertEqual(manifest["mode"], "literature_ideation")
            self.assertTrue(manifest["review_required"])
            self.assertFalse(manifest["can_export_final"])
            self.assertTrue(Path(manifest["artifacts"]["source_profile"]).exists())
            self.assertTrue(Path(manifest["artifacts"]["idea_scaffold"]).exists())
            self.assertTrue(Path(manifest["artifacts"]["idea_brief"]).exists())
            self.assertTrue(Path(manifest["artifacts"]["review_gate"]).exists())

    def test_token_snapshot_estimates_local_artifact_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_dir = root / "outputs" / "local_ai_runs" / "local_ai_1"
            run_dir.mkdir(parents=True)
            (run_dir / "request.json").write_text(
                '{"run_id":"local_ai_1","prompt":"short prompt","source_context_characters":400}',
                encoding="utf-8",
            )
            (run_dir / "draft_response.md").write_text("draft answer " * 20, encoding="utf-8")

            snapshot = collect_token_snapshot(
                root,
                {
                    "outputs_dir": "outputs/local_ai_runs",
                    "monitor": {"token_artifact_dir": "outputs/local_ai_runs"},
                },
            )

            self.assertEqual(snapshot["runs_counted"], 1)
            self.assertGreaterEqual(snapshot["estimated_source_tokens"], 100)
            self.assertGreater(snapshot["estimated_output_tokens"], 0)

    def test_model_routing_advice_preserves_review_gate_policy(self) -> None:
        advice = build_model_routing_advice(
            {
                "ollama": {
                    "reachable": False,
                    "configured_model": "qwen2.5:7b",
                    "effective_model": "",
                    "available_models": [],
                    "status_label": "unreachable",
                },
                "lmstudio": {
                    "reachable": True,
                    "configured_model": "",
                    "effective_model": "qwen/qwen3.5-9b",
                    "available_models": ["qwen/qwen3.5-9b"],
                    "status_label": "reachable",
                },
            },
            {
                "primary_backend": "ollama",
                "review_backend": "lmstudio",
                "fallback_to_review_backend": True,
            },
        )

        self.assertIn("fallback", " ".join(advice["advisories"]).casefold())
        self.assertIn("does not bypass", advice["policy"])

    def test_local_console_html_is_status_only(self) -> None:
        snapshot = {
            "created_at": "2026-01-01T00:00:00Z",
            "summary": {"status": "ok", "advisories": []},
            "cpu": {"load_average": {"1m": 0.1}, "cpu_count": 8, "load_ratio_1m": 0.012},
            "memory": {"available_gb": 8.0},
            "thermal": {"thermal_pressure": "nominal"},
            "token_usage": {"estimated_total_tokens": estimate_tokens("hello"), "runs_counted": 1},
            "backends": {},
            "disk": [],
            "model_routing": {
                "primary_backend": "ollama",
                "review_backend": "lmstudio",
                "fallback_to_review_backend": True,
                "candidates": [],
                "advisories": ["Configured model path is available."],
                "policy": "Model switching changes draft-generation behavior only.",
            },
        }
        html = render_console_html(snapshot)

        self.assertIn("Local Research AI Console", html)
        self.assertIn("no auto-finalization", html)
        self.assertIn("/api/monitor", html)

        workbench = render_workbench_html(snapshot, [])
        self.assertIn("研究者工作台", workbench)
        self.assertIn("taskNav", workbench)
        self.assertIn("conversation", workbench)
        self.assertIn("review_gate", workbench)
        self.assertIn("/api/jobs", workbench)
        self.assertIn("运行并看反馈", workbench)

    def test_local_console_jobs_only_build_safe_whitelisted_commands(self) -> None:
        manager = LocalConsoleJobManager(repo_root=PROJECT_ROOT, config={}, config_path=PROJECT_ROOT / "configs" / "local_ai.example.json")
        job = manager._build_job({"action": "monitor"})

        self.assertIn("src.research_systems_showcase.local_ai.cli", job.argv)
        self.assertIn("monitor", job.argv)
        self.assertNotIn(";", job.command_display)

        with self.assertRaises(ValueError):
            manager._build_job({"action": "rm -rf /"})

    def test_builtin_token_compression_preserves_query_relevant_text(self) -> None:
        text = "\n\n".join(
            [
                "General background paragraph with limited relevance.",
                "Climate litigation case documents identify Plaintiff and Defendant fields.",
                "The addressed issue and final decision fields must remain reviewable.",
                "Administrative filler text that should be less important.",
            ]
        )

        result = compress_text(
            text,
            query="climate litigation plaintiff defendant final decision",
            target_tokens=35,
            method="builtin",
        )

        compressed = result["compressed_text"]
        self.assertEqual(result["method"], "builtin_extractive")
        self.assertTrue(result["lossy"])
        self.assertIn("Plaintiff", compressed)
        self.assertLessEqual(result["compressed_tokens"], result["origin_tokens"])

    def test_compression_metadata_is_written_to_local_ai_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "out"
            source_path = Path(tmp_dir) / "source.txt"
            source_path.write_text(
                "Climate litigation Plaintiff Defendant FinalDecision Addressed Issue. " * 20,
                encoding="utf-8",
            )
            config_path = Path(tmp_dir) / "config.json"
            config_path.write_text(
                """
                {
                  "prompt_compression": {
                    "enabled": true,
                    "method": "builtin",
                    "target_tokens": 60
                  }
                }
                """,
                encoding="utf-8",
            )

            manifest = run_local_research_prompt(
                user_prompt="Draft a review-gated legal coding note.",
                repo_root=PROJECT_ROOT,
                config_path=config_path,
                source_paths=[source_path],
                output_dir=output_dir,
                dry_run=True,
            )
            request_text = Path(manifest["artifacts"]["request"]).read_text(encoding="utf-8")

            self.assertIn('"enabled": true', request_text)
            self.assertIn('"method": "builtin_extractive"', request_text)
            self.assertIn('"lossy": true', request_text)


if __name__ == "__main__":
    unittest.main()
