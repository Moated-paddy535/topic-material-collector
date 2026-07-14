#!/usr/bin/env python3
"""Search YouTube, locate relevant subtitle/chapter ranges, and fetch materials."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from material_common import (
    CommandError,
    ProjectPaths,
    download_video,
    filename_time,
    fit_label,
    infer_risk,
    require_commands,
    run_command,
    run_ytdlp_with_cookie_fallback,
    slugify,
    write_manifests,
)


ENGLISH_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "is",
    "it", "of", "on", "or", "that", "the", "this", "to", "video", "with", "documentary",
    "footage", "archive", "official", "full", "hd",
}
TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3})\s+-->\s+(?P<end>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Cue:
    start: float
    end: float
    text: str


def tokenize(text: str) -> set[str]:
    lowered = html.unescape(text or "").lower()
    tokens = {
        token for token in re.findall(r"[a-z0-9][a-z0-9'-]+", lowered)
        if len(token) > 1 and token not in ENGLISH_STOPWORDS
    }
    for chunk in re.findall(r"[\u3400-\u9fff]+", lowered):
        if len(chunk) <= 4:
            tokens.add(chunk)
        tokens.update(chunk[index:index + 2] for index in range(len(chunk) - 1))
    return tokens


def text_score(text: str, terms: set[str], phrases: Iterable[str] = ()) -> float:
    lowered = html.unescape(text or "").lower()
    score = float(len(tokenize(lowered) & terms))
    for phrase in phrases:
        normalized = phrase.strip().lower()
        if len(normalized) >= 3 and normalized in lowered:
            score += 4.0
    return score


def parse_vtt_timestamp(raw: str) -> float:
    parts = raw.replace(",", ".").split(":")
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


def parse_vtt(path: Path) -> list[Cue]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    cues: list[Cue] = []
    index = 0
    previous_text = ""
    while index < len(lines):
        match = TIMESTAMP_RE.search(lines[index])
        if not match:
            index += 1
            continue
        start = parse_vtt_timestamp(match.group("start"))
        end = parse_vtt_timestamp(match.group("end"))
        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            cleaned = TAG_RE.sub("", html.unescape(lines[index])).strip()
            if cleaned:
                text_lines.append(cleaned)
            index += 1
        text = re.sub(r"\s+", " ", " ".join(text_lines)).strip()
        if text and text != previous_text:
            cues.append(Cue(start=start, end=end, text=text))
            previous_text = text
        index += 1
    return cues


def find_segments(
    cues: list[Cue],
    *,
    terms: set[str],
    phrases: list[str],
    clip_duration: float,
    context: float,
    count: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for cue_index, cue in enumerate(cues):
        cue_relevance = text_score(cue.text, terms, phrases)
        if cue_relevance <= 0:
            continue
        window_end = cue.start + clip_duration
        selected = [item for item in cues[cue_index:] if item.start < window_end]
        if not selected:
            continue
        relevance = sum(text_score(item.text, terms, phrases) for item in selected)
        excerpt = " ".join(item.text for item in selected)
        start = max(0.0, cue.start - context)
        end = max(start + 1.0, min(selected[-1].end + context, window_end + context))
        candidates.append({"start": start, "end": end, "score": relevance, "excerpt": excerpt[:320]})
    candidates.sort(key=lambda item: (item["score"], -(item["end"] - item["start"])), reverse=True)
    chosen: list[dict[str, Any]] = []
    for candidate in candidates:
        overlaps = any(candidate["start"] < item["end"] and candidate["end"] > item["start"] for item in chosen)
        if not overlaps:
            chosen.append(candidate)
        if len(chosen) >= count:
            break
    return chosen


def chapter_segments(
    chapters: list[dict[str, Any]],
    *,
    terms: set[str],
    phrases: list[str],
    clip_duration: float,
    count: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for chapter in chapters or []:
        title = str(chapter.get("title") or "")
        score = text_score(title, terms, phrases)
        if score <= 0:
            continue
        start = float(chapter.get("start_time") or 0)
        chapter_end = float(chapter.get("end_time") or start + clip_duration)
        candidates.append(
            {
                "start": start,
                "end": min(chapter_end, start + clip_duration),
                "score": score,
                "excerpt": f"章节：{title}",
            }
        )
    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[:count]


def default_queries(topic: str) -> list[str]:
    return [
        topic,
        f"{topic} documentary",
        f"{topic} footage",
        f"{topic} archive footage",
        f"{topic} 纪录片",
        f"{topic} 历史影像",
    ]


def search_youtube(query: str, limit: int, proxy: str = "", browser: str = "") -> list[dict[str, Any]]:
    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--no-update",
        "--flat-playlist",
        "--dump-single-json",
        "--playlist-end",
        str(limit),
    ]
    if proxy:
        cmd += ["--proxy", proxy]
    cmd.append(f"ytsearch{limit}:{query}")
    output = run_ytdlp_with_cookie_fallback(cmd, browser=browser).stdout
    payload = json.loads(output)
    return [entry for entry in payload.get("entries", []) if entry and entry.get("id")]


def candidate_score(candidate: dict[str, Any], terms: set[str], phrases: list[str]) -> float:
    rank_bonus = max(0.0, 5.0 - float(candidate.get("best_rank", 99)) * 0.35)
    title = str(candidate.get("title") or "")
    description = str(candidate.get("description") or "")
    creator = str(candidate.get("channel") or candidate.get("uploader") or "")
    return (
        text_score(title, terms, phrases) * 4.0
        + text_score(description, terms, phrases)
        + text_score(creator, terms, phrases) * 0.5
        + rank_bonus
    )


def fetch_metadata(
    candidate: dict[str, Any],
    project: ProjectPaths,
    *,
    languages: str,
    proxy: str,
    browser: str,
    thumbnails: bool,
) -> tuple[dict[str, Any], list[Path]]:
    video_id = str(candidate["id"])
    workdir = project.metadata / video_id
    workdir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"
    output_template = workdir / "source.%(ext)s"
    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--no-update",
        "--no-playlist",
        "--skip-download",
        "--write-info-json",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        languages,
        "--sub-format",
        "vtt",
        "-o",
        str(output_template),
    ]
    if thumbnails:
        cmd += ["--write-thumbnail", "--convert-thumbnails", "jpg"]
    if proxy:
        cmd += ["--proxy", proxy]
    cmd.append(url)
    run_ytdlp_with_cookie_fallback(cmd, browser=browser)

    info_files = list(workdir.glob("*.info.json"))
    metadata = json.loads(info_files[0].read_text(encoding="utf-8")) if info_files else candidate
    subtitles = list(workdir.glob("*.vtt"))
    for thumbnail in workdir.glob("*.jpg"):
        shutil.copy2(thumbnail, project.thumbnails / f"{video_id}.jpg")
        break
    return metadata, subtitles


def confidence_label(score: float) -> str:
    if score >= 8:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="按选题检索 YouTube，利用字幕/章节定位相关时间段，并可下载目标片段。"
    )
    parser.add_argument("--topic", required=True)
    parser.add_argument("--outdir", required=True, help="绝对输出目录")
    parser.add_argument("--project-name", default="")
    parser.add_argument("--query", action="append", default=[], help="额外或替代检索词，可重复")
    parser.add_argument("--results-per-query", type=int, default=6)
    parser.add_argument("--analyze", type=int, default=10, help="深入分析的视频数量")
    parser.add_argument("--max-downloads", type=int, default=5)
    parser.add_argument("--mode", choices=("catalog", "clips", "full"), default="clips")
    parser.add_argument("--clip-duration", type=float, default=20.0)
    parser.add_argument("--context", type=float, default=2.5)
    parser.add_argument("--segments-per-video", type=int, default=1, choices=(1, 2, 3))
    parser.add_argument("--height", type=int, default=1080, choices=(360, 480, 720, 1080, 1440, 2160))
    parser.add_argument("--languages", default="zh-Hans,zh-CN,zh,en.*")
    parser.add_argument("--proxy", default="")
    parser.add_argument("--cookies-from-browser", default="auto", help="默认自动探测；也可指定 brave/firefox/chrome")
    parser.add_argument("--no-thumbnails", action="store_true")
    args = parser.parse_args()

    require_commands(["yt-dlp", "ffmpeg", "ffprobe"])
    queries = args.query or default_queries(args.topic)
    project = ProjectPaths.create(args.outdir, args.project_name or args.topic)
    terms = tokenize(" ".join([args.topic, *queries]))
    phrases = [args.topic, *queries]

    candidates_by_id: dict[str, dict[str, Any]] = {}
    search_errors: list[str] = []
    for query in queries:
        try:
            entries = search_youtube(
                query,
                args.results_per_query,
                args.proxy,
                args.cookies_from_browser,
            )
        except Exception as exc:
            search_errors.append(f"{query}: {exc}")
            continue
        for rank, entry in enumerate(entries, start=1):
            video_id = str(entry["id"])
            stored = candidates_by_id.setdefault(video_id, dict(entry))
            stored.setdefault("queries", [])
            if query not in stored["queries"]:
                stored["queries"].append(query)
            stored["best_rank"] = min(int(stored.get("best_rank", 999)), rank)

    candidates = list(candidates_by_id.values())
    for candidate in candidates:
        candidate["candidate_score"] = candidate_score(candidate, terms, phrases)
    candidates.sort(key=lambda item: item["candidate_score"], reverse=True)
    candidates = candidates[: max(1, args.analyze)]

    records: list[dict[str, Any]] = []
    download_count = 0
    for candidate in candidates:
        video_id = str(candidate["id"])
        source_url = f"https://www.youtube.com/watch?v={video_id}"
        metadata: dict[str, Any] = candidate
        subtitles: list[Path] = []
        analysis_error = ""
        try:
            metadata, subtitles = fetch_metadata(
                candidate,
                project,
                languages=args.languages,
                proxy=args.proxy,
                browser=args.cookies_from_browser,
                thumbnails=not args.no_thumbnails,
            )
        except Exception as exc:
            analysis_error = str(exc)

        candidate_fit = candidate_score(candidate | metadata, terms, phrases)
        segments: list[dict[str, Any]] = []
        best_subtitle: Path | None = None
        for subtitle in subtitles:
            subtitle_segments = find_segments(
                parse_vtt(subtitle),
                terms=terms,
                phrases=phrases,
                clip_duration=args.clip_duration,
                context=args.context,
                count=args.segments_per_video,
            )
            subtitle_score = sum(float(item.get("score") or 0) for item in subtitle_segments)
            current_score = sum(float(item.get("score") or 0) for item in segments)
            if subtitle_score > current_score:
                segments = subtitle_segments
                best_subtitle = subtitle
        if best_subtitle:
            destination = project.subtitles / f"{video_id}_{best_subtitle.name}"
            shutil.copy2(best_subtitle, destination)
        if not segments:
            segments = chapter_segments(
                metadata.get("chapters") or [],
                terms=terms,
                phrases=phrases,
                clip_duration=args.clip_duration,
                count=args.segments_per_video,
            )
        if args.mode == "full" and not segments:
            segments = [{"start": None, "end": None, "score": 0.0, "excerpt": "未定位片段，按整段下载"}]
        if not segments:
            segments = [{"start": None, "end": None, "score": 0.0, "excerpt": "未在字幕或章节中可靠定位"}]

        for segment_number, segment in enumerate(segments, start=1):
            index = len(records) + 1
            start = segment.get("start")
            end = segment.get("end")
            segment_score = float(segment.get("score") or 0)
            confidence = confidence_label(segment_score)
            title = str(metadata.get("title") or candidate.get("title") or video_id)
            creator = str(metadata.get("channel") or metadata.get("uploader") or "")
            license_text = str(metadata.get("license") or "")
            record: dict[str, Any] = {
                "index": index,
                "type": "video",
                "need": args.topic,
                "title": title,
                "creator": creator,
                "source": "YouTube",
                "source_url": source_url,
                "source_duration": metadata.get("duration", candidate.get("duration", "")),
                "segment_start": start,
                "segment_end": end,
                "segment_excerpt": segment.get("excerpt", ""),
                "fit": fit_label(candidate_fit + segment_score),
                "confidence": confidence,
                "license": license_text,
                "risk": infer_risk(license_text, title, creator),
                "local_file": "",
                "status": "cataloged",
                "notes": analysis_error,
            }
            should_download = download_count < args.max_downloads and args.mode != "catalog"
            if args.mode == "clips":
                should_download = should_download and start is not None and end is not None and confidence != "low"
            if should_download:
                time_suffix = ""
                if start is not None and end is not None:
                    time_suffix = f"_{filename_time(start)}-{filename_time(end)}"
                stem = f"{index:03d}_{slugify(title, 54)}{time_suffix}"
                target_dir = project.clips if start is not None and end is not None else project.full
                try:
                    local = download_video(
                        url=source_url,
                        output_stem=target_dir / stem,
                        start=start,
                        end=end,
                        height=args.height,
                        proxy=args.proxy,
                        browser=args.cookies_from_browser,
                    )
                    record["local_file"] = local
                    record["status"] = "downloaded"
                    download_count += 1
                except Exception as exc:
                    record["status"] = "download-failed"
                    record["notes"] = f"{record['notes']} | {exc}".strip(" |")
            elif args.mode == "clips" and (start is None or confidence == "low"):
                record["status"] = "needs-manual-review"
            records.append(record)
            write_manifests(
                records,
                project,
                topic=args.topic,
                queries=queries,
                settings={
                    "mode": args.mode,
                    "height": args.height,
                    "clip_duration": args.clip_duration,
                    "search_errors": search_errors,
                },
            )

    if not records:
        write_manifests(
            [],
            project,
            topic=args.topic,
            queries=queries,
            settings={"mode": args.mode, "search_errors": search_errors},
        )
    print(project.root)
    return 0 if records else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CommandError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(exc.returncode)
    except KeyboardInterrupt:
        print("已取消", file=sys.stderr)
        raise SystemExit(130)
