# Conservative Data Acquisition

This layer gives the local research assistant a controlled file-in capability for data acquisition. It is not an open-ended crawler.

## What It Does

The `acquire` command accepts:

- explicit `http` or `https` URLs
- a text file containing one URL per line
- local source files

It writes:

- a raw copied/downloaded artifact
- extracted text when the source is readable by the local extractor
- `intake_manifest.json`
- source metadata including status, byte count, sha256, content type, extraction status, and error reason

## Command Examples

Acquire one URL:

```bash
research-ai-local --config local_ai.config.json acquire --url "https://example.com/data.csv"
```

Acquire URLs from a list:

```bash
research-ai-local --config local_ai.config.json acquire --url-file urls.txt
```

Copy a local file into intake artifacts:

```bash
research-ai-local --config local_ai.config.json acquire --local-source README.md
```

Plan without downloading or copying:

```bash
research-ai-local --config local_ai.config.json acquire --url "https://example.com/data.csv" --dry-run
```

## Safety Boundaries

- Only user-supplied sources are fetched or copied.
- No recursive crawling is performed.
- Every source receives a manifest record.
- Failures are recorded instead of silently ignored.
- Acquired data is not treated as validated research output.
- Model processing and final export remain review-gated.

## Follow-On Processing

After acquisition, use the extracted text file or raw artifact as a source for existing commands:

```bash
research-ai-local --config local_ai.config.json ask "Draft a review-gated summary." --source outputs/data_intake/.../extracted_text/source.txt
```

or:

```bash
research-ai-local --config local_ai.config.json ideate "Generate research starting points." --source outputs/data_intake/.../extracted_text/source.txt
```

The acquisition layer improves traceability. It does not guarantee source correctness, license compatibility, or downstream validity.
