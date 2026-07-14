#!/usr/bin/env python3
"""Download and catalog a reviewed cross-platform material candidate list."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from material_common import (
    ProjectPaths,
    download_image,
    download_video,
    filename_time,
    infer_risk,
    parse_timecode,
    require_commands,
    slugify,
    write_manifests,
)


def load_candidates(path: Path) -> tuple[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return path.stem, payload
    if not isinstance(payload, dict):
        raise ValueError("候选清单必须是 JSON 数组或包含 materials/candidates 的对象")
    candidates = payload.get("materials", payload.get("candidates", []))
    if not isinstance(candidates, list):
        raise ValueError("materials/candidates 必须是数组")
    return str(payload.get("topic") or path.stem), candidates


def candidate_filename(index: int, candidate: dict[str, Any]) -> str:
    title = slugify(str(candidate.get("title") or candidate.get("need") or "material"), 58)
    start = parse_timecode(candidate.get("start", candidate.get("segment_start")))
    end = parse_timecode(candidate.get("end", candidate.get("segment_end")))
    suffix = f"_{filename_time(start)}-{filename_time(end)}" if start is not None and end is not None else ""
    return f"{index:03d}_{title}{suffix}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="按 JSON 候选清单下载图片、视频或目标视频片段，并生成 Markdown/CSV/JSON 清单。"
    )
    parser.add_argument("candidates", type=Path, help="候选清单 JSON")
    parser.add_argument("--outdir", required=True, help="绝对输出目录")
    parser.add_argument("--project-name", default="", help="项目文件夹名；默认取清单 topic")
    parser.add_argument("--height", type=int, default=1080, choices=(360, 480, 720, 1080, 1440, 2160))
    parser.add_argument("--proxy", default="")
    parser.add_argument("--cookies-from-browser", default="auto", help="默认自动探测；也可指定 brave/firefox/chrome")
    parser.add_argument("--catalog-only", action="store_true", help="只生成清单，不下载")
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    topic, candidates = load_candidates(args.candidates)
    project = ProjectPaths.create(args.outdir, args.project_name or topic)
    if not args.catalog_only:
        require_commands(["yt-dlp", "ffmpeg"])

    records: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        media_type = str(candidate.get("type", "video")).lower()
        url = str(candidate.get("url") or candidate.get("source_url") or "").strip()
        start = parse_timecode(candidate.get("start", candidate.get("segment_start")))
        end = parse_timecode(candidate.get("end", candidate.get("segment_end")))
        title = str(candidate.get("title") or candidate.get("need") or f"material-{index}")
        license_text = str(candidate.get("license") or "")
        record: dict[str, Any] = {
            "index": index,
            "type": media_type,
            "need": candidate.get("need", topic),
            "title": title,
            "creator": candidate.get("creator", candidate.get("channel", "")),
            "source": candidate.get("source", "web"),
            "source_url": url,
            "source_duration": candidate.get("source_duration", ""),
            "segment_start": start,
            "segment_end": end,
            "segment_excerpt": candidate.get("segment_excerpt", candidate.get("excerpt", "")),
            "fit": candidate.get("fit", "B"),
            "confidence": candidate.get("confidence", "reviewed"),
            "license": license_text,
            "risk": candidate.get("risk") or infer_risk(license_text, title, str(candidate.get("creator", ""))),
            "local_file": "",
            "status": "cataloged" if args.catalog_only else "pending",
            "notes": candidate.get("notes", ""),
        }
        try:
            if not url:
                raise ValueError("缺少 url/source_url")
            if not args.catalog_only and candidate.get("download", True):
                stem = candidate_filename(index, candidate)
                if media_type == "image":
                    local = download_image(url, project.images / stem)
                else:
                    target_dir = project.clips if start is not None and end is not None else project.full
                    local = download_video(
                        url=url,
                        output_stem=target_dir / stem,
                        start=start,
                        end=end,
                        height=args.height,
                        proxy=args.proxy,
                        browser=args.cookies_from_browser,
                    )
                record["local_file"] = local
                record["status"] = "downloaded"
            elif candidate.get("download", True) is False:
                record["status"] = "reference-only"
        except Exception as exc:  # keep the rest of a batch usable
            record["status"] = "failed"
            record["notes"] = f"{record['notes']} | {exc}".strip(" |")
            if args.fail_fast:
                records.append(record)
                write_manifests(records, project, topic=topic)
                raise
        records.append(record)
        write_manifests(
            records,
            project,
            topic=topic,
            settings={"height": args.height, "catalog_only": args.catalog_only},
        )

    if not records:
        write_manifests(
            [],
            project,
            topic=topic,
            settings={"height": args.height, "catalog_only": args.catalog_only},
        )

    print(project.root)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("已取消", file=sys.stderr)
        raise SystemExit(130)
