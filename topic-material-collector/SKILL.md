---
name: topic-material-collector
description: Collect, timestamp, download, clip, rename, and catalog video-first research materials from a topic, script, shot list, narration, or B-roll request. Use when the user asks to 全网找素材、按选题收集视频、搜索 YouTube 素材、定位视频时间段、只下载目标片段、批量下载并重命名、生成素材清单、建立剪辑素材库, or package images and videos into a specified folder with source URLs, timestamps, local paths, fit scores, and reuse-risk labels.
---

# Topic Material Collector

## Overview

Turn a topic or editing brief into a traceable, video-first material package. Combine current web research with deterministic scripts for YouTube discovery, subtitle/chapter timestamping, targeted downloads, image downloads, filename normalization, and Markdown/CSV/JSON manifests.

Treat “全网” as broad multi-source research, not a literal guarantee of indexing every page. Preserve attribution and never imply that downloading grants publication rights.

## Workflow

1. Confirm or infer the run settings.
   - Require a topic or script and an absolute output directory before downloading.
   - Default to `clips` mode: download only medium/high-confidence target segments.
   - Use `catalog` mode when the user wants research before downloading.
   - Use `full` mode only when the user explicitly needs complete source videos or timestamp detection is unavailable.
   - Default to private study/editing practice. Ask about public/commercial use only when it changes source selection materially.

2. Break the request into visual needs.
   - Extract entities, events, actions, era, location, visual style, orientation, resolution, and exclusions.
   - Create Chinese and English queries for each visual need.
   - Read [references/source-strategy.md](references/source-strategy.md) when researching beyond YouTube or when licensing risk matters.

3. Run YouTube-first automated research.

```bash
python3 scripts/collect_youtube.py \
  --topic "<选题>" \
  --outdir "/absolute/output/path" \
  --mode clips
```

   - Add repeated `--query "..."` arguments when the topic needs precise English/archive queries.
   - Use `--mode catalog --max-downloads 0` for a research-only first pass.
   - The script searches, deduplicates, scores candidates, downloads subtitles/metadata, finds relevant subtitle or chapter windows, downloads approved-confidence clips, and writes manifests after every item.
   - Automatic timestamps are semantic first passes. Verify the actual picture before treating a segment as edit-ready; spoken references can occur while unrelated B-roll is shown.

4. Research non-YouTube and image sources.
   - Use current web search and prioritize official archives, institutions, open-license repositories, creator source pages, then stock/reference platforms.
   - Build a reviewed `candidates.json` using [references/candidate-schema.md](references/candidate-schema.md).
   - Include images, direct video pages, YouTube/Vimeo links, source pages that require manual licensing, and reference-only items.
   - Set `download: false` for paywalled, login-only, licensing-required, or reference-only candidates.

5. Fetch the reviewed cross-platform candidate list.

```bash
python3 scripts/fetch_candidates.py \
  /absolute/path/candidates.json \
  --outdir "/absolute/output/path"
```

   - Video entries with `start` and `end` are downloaded as target clips.
   - Video entries without a range are downloaded in full.
   - Image entries are saved under `images/`.
   - Failed items remain in the manifest with an error instead of aborting the whole batch.

6. Verify the package.
   - Check that each local file exists, opens, and matches its manifest row.
   - Preview the beginning, middle, and end of each clip; inspect the requested action rather than relying only on transcript text.
   - Remove false positives from the delivery manifest or mark them `reference-only`.
   - Keep source URL, creator, timestamp, license text, and risk label for every retained asset.

## Output Contract

Each project folder contains:

```text
<project>/
├── clips/                  # Target video segments
├── full/                   # Complete source videos when requested
├── images/                 # Downloaded still images
├── metadata/               # Source metadata and analysis files
├── subtitles/              # Subtitle files used for timestamping
├── thumbnails/             # Candidate preview images
├── material-manifest.md    # Human-readable editing list
├── material-manifest.csv   # Spreadsheet-friendly list
└── material-manifest.json  # Machine-readable list
```

Name media as `<index>_<descriptive-title>_<start>-<end>.<ext>` when a segment exists. Keep names descriptive and stable; never overwrite unrelated user files.

The manifest must include the visual need, source title and URL, creator, source duration, target time range, excerpt/reason, fit, confidence, license metadata, risk, local path, status, and notes.

## Timestamp Rules

- Prefer creator chapters and human subtitles over auto-generated subtitles.
- Add 2–4 seconds of context around a semantic match unless the user requests frame-tight cuts.
- Mark subtitle/chapter matches as `high`, `medium`, or `low` confidence.
- Do not auto-download `low`-confidence clips in default `clips` mode.
- If no transcript or chapter match exists, mark `needs-manual-review`; do not invent a timestamp.
- For visually specific needs, inspect preview frames or a proxy before final delivery.

## Rights and Safety

- `Low`: source metadata explicitly states public domain, CC0, or a clear open license.
- `Medium`: viewable material with unclear or platform-limited reuse rights.
- `High`: films, television, paid news footage, unclear reuploads, or obviously protected material.
- Do not bypass DRM, paywalls, login controls, geographic restrictions, or watermarks.
- Do not present downloaded material as licensed. Separate private-study usefulness from public/commercial clearance.
- Preserve attribution even for open-license and public-domain material.

## Failure Handling

- If YouTube returns 403/SABR errors, the scripts automatically detect installed browsers and retry with available cookies. Pass `--cookies-from-browser brave` (or another browser name) to override detection.
- If a proxy is needed, pass `--proxy http://127.0.0.1:7890` to both scripts.
- If subtitles are unavailable, use chapters, description context, thumbnails, or manual review; do not force a weak clip.
- If a source cannot be downloaded lawfully, keep it in the catalog with `download: false` and provide a lower-friction alternative.
