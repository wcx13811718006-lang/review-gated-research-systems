# Local Console And Monitoring

The local console is a small, status-first operations surface for researchers who do not want to inspect internal files before every run.

It is intentionally conservative:

- local-only by default
- read-focused
- no automatic finalization
- no background batch automation
- no remote upload
- no hidden model switching

## Start The Console

From Finder, double-click:

```text
start_local_ai_console.command
```

The script starts the local console and opens the browser automatically.

From the terminal:

```bash
research-ai-local --config local_ai.config.json console
```

Then open:

```text
http://127.0.0.1:8765
```

The console is now organized as a compact researcher workbench:

- left command rail for common safe operations
- center chat-like task workspace for preparing prompts and source paths
- right inspector for computer status, model status, and recent review-gated runs
- copy buttons for safe commands generated from the selected task
- CPU load
- memory pressure approximation
- disk space for key paths
- macOS thermal pressure when available
- local artifact token estimates
- Ollama and LM Studio status
- configured, discovered, and effective model information
- safe command examples
- prompt-compression command examples for lowering draft-generation token cost

The raw diagnostic log is still available under "原始诊断" for debugging, but it is folded by default so the page does not become one long terminal dump.

## Basic Researcher Workflow

1. Start the console from Finder or terminal.
2. Check the right-side status panel for CPU, memory, disk, Ollama, and LM Studio.
3. Choose a task from the left command rail.
4. Type a research prompt and optional source path in the center workspace.
5. Click "生成命令" and run the copied command in the terminal.
6. Inspect the right-side recent runs and the generated `review_gate.json` before treating any output as useful research material.

The console still does not auto-finalize, auto-export, or silently clear review gates.

## Terminal Monitor

For a terminal-only status view:

```bash
research-ai-local --config local_ai.config.json monitor
```

Write a monitor snapshot:

```bash
research-ai-local --config local_ai.config.json monitor --write
```

Print full JSON:

```bash
research-ai-local --config local_ai.config.json monitor --json
```

## Model Switching

Show model routing status:

```bash
research-ai-local --config local_ai.config.json models
```

The system distinguishes:

- configured target model
- discovered available model IDs
- effective selected model
- primary backend
- review/fallback backend

If the primary model fails, the configured fallback can be used for draft generation. This does not bypass review gates or human approval.

## Token Accounting

Token counts are estimates from local artifacts. They are useful for operational planning, but they are not provider billing records.

Current limits:

- hidden reasoning tokens may not be visible
- Codex or ChatGPT UI tokens are not accessible to this repository
- local model APIs may not return complete usage metadata

The monitor therefore estimates tokens from stored prompts, source-context character counts, and output files.

## Temperature And System Sensors

On macOS, precise CPU/GPU temperature is not exposed through a stable non-privileged standard-library API. The monitor reports thermal pressure when `pmset -g therm` is available and marks precise temperature as unavailable otherwise.

This is intentional. The public local layer should not require sudo or privileged hardware sensor access.

## Design Influence

The console borrows patterns from current agent systems without adopting their full stacks:

- Hermes/OpenClaw: local dashboard, model/provider visibility, user-friendly command surface
- Google AI co-scientist: generation/reflection/ranking/meta-review as a research workflow pattern
- DeepScientist: findings memory, experiment logging, and preserving failed branches
- LLMLingua-style prompt compression: cost reduction with explicit lossy-compression warnings

This project keeps those ideas inside a stricter review-gated local workflow.
