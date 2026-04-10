# Design Principles

## 1. Review-Gated By Default

Outputs should not move downstream simply because a prior stage ran successfully. The system pauses uncertain records and makes the pause visible.

## 2. Human Oversight Is A Feature

The review queue is not treated as failure. It is part of the design. Records that need context, judgment, or extra checking should surface those needs early.

## 3. Modular Stages Beat Monolithic Prompts

This repository keeps ingestion, routing, validation, review, and export separate so each stage remains easy to inspect and revise.

## 4. Structured Outputs Improve Reuse

JSON outputs, Markdown review packets, progress logs, and analysis briefs make it easier to audit the system and connect it to downstream analysis tasks.

## 5. Reproducibility Matters

The public demo uses deterministic toy inputs and a local sample output directory so the system can be rerun and inspected without hidden dependencies.

## 6. Public Release Should Be Selective

A public showcase is not the same thing as a private lab notebook. This repository highlights architecture and system logic while excluding sensitive research materials.
