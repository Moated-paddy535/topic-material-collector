#!/usr/bin/env python3
"""Shared utilities for topic-material-collector scripts."""

from __future__ import annotations

import csv
import html
import json
import mimetypes
import os
import platform
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
DEFAULT_VIDEO_FORMAT = (
    "bestvideo[vcodec^=avc1][height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
    "bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
    "best[height<={height}][ext=mp4]/best[height<={height}]/best"
)
MANIFEST_FIELDS = [
    "index",
    "type",
    "need",
    "title",
    "creator",
    "source",
    "source_url",
    "source_duration",
    "segment_start",
    "segment_end",
    "segment_excerpt",
    "fit",
    "confidence",
    "license",
    "risk",
    "local_file",
    "status",
    "notes",
]


class CommandError(RuntimeError):
    """Raised when an external command exits unsuccessfully."""

    def __init__(self, cmd: Sequence[str], returncode: int, output: str):
        self.cmd = list(cmd)
        self.returncode = returncode
        self.output = output
        super().__init__(f"command failed ({returncode}): {' '.join(cmd)}\n{output[-2000:]}")


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    clips: Path
    full: Path
    images: Path
    metadata: Path
    subtitles: Path
    thumbnails: Path
    tmp: Path

    @classmethod
    def create(cls, outdir: str, project_name: str) -> "ProjectPaths":
        base = Path(os.path.expanduser(outdir))
        if not base.is_absolute():
            raise ValueError("--outdir 必须是绝对路径或以 ~ 开头")
        root = base / slugify(project_name, max_length=90)
        paths = cls(
            root=root,
            clips=root / "clips",
            full=root / "full",
            images=root / "images",
            metadata=root / "metadata",
            subtitles=root / "subtitles",
            thumbnails=root / "thumbnails",
            tmp=root / "tmp",
        )
        for path in paths.__dict__.values():
            Path(path).mkdir(parents=True, exist_ok=True)
        return paths


def require_commands(names: Iterable[str]) -> None:
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        raise SystemExit(f"缺少依赖：{', '.join(missing)}")


def run_command(
    cmd: Sequence[str],
    *,
    check: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(cmd),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        raise CommandError(cmd, completed.returncode, completed.stdout or "")
    return completed


def slugify(value: str, max_length: int = 72) -> str:
    value = html.unescape(value or "").strip()
    value = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", value)
    value = re.sub(r"[^\w\-\u3400-\u9fff]+", "_", value, flags=re.UNICODE)
    value = re.sub(r"_+", "_", value).strip("._-")
    return (value or "material")[:max_length].rstrip("._-")


def parse_timecode(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    raw = str(value).strip().lower()
    if not raw:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", raw):
        return max(0.0, float(raw))
    unit_match = re.fullmatch(
        r"(?:(?P<h>\d+(?:\.\d+)?)h)?\s*(?:(?P<m>\d+(?:\.\d+)?)m)?\s*(?:(?P<s>\d+(?:\.\d+)?)s)?",
        raw,
    )
    if unit_match and any(unit_match.groupdict().values()):
        return (
            float(unit_match.group("h") or 0) * 3600
            + float(unit_match.group("m") or 0) * 60
            + float(unit_match.group("s") or 0)
        )
    parts = raw.replace(",", ".").split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"无法解析时间码：{value}")
    try:
        numbers = [float(part) for part in parts]
    except ValueError as exc:
        raise ValueError(f"无法解析时间码：{value}") from exc
    seconds = 0.0
    for number in numbers:
        seconds = seconds * 60 + number
    return max(0.0, seconds)


def format_timecode(seconds: Any) -> str:
    parsed = parse_timecode(seconds)
    if parsed is None:
        return ""
    total_ms = int(round(parsed * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    if millis:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def filename_time(seconds: Any) -> str:
    parsed = int(round(parse_timecode(seconds) or 0))
    hours, remainder = divmod(parsed, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}h{minutes:02d}m{secs:02d}s"
    return f"{minutes:02d}m{secs:02d}s"


def is_youtube_url(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host in YOUTUBE_HOSTS or host.endswith(".youtube.com")


def infer_risk(license_text: str, title: str = "", creator: str = "") -> str:
    license_lower = (license_text or "").lower()
    combined = f"{title} {creator}".lower()
    if any(term in license_lower for term in ("creative commons", "public domain", "cc0")):
        return "Low"
    if any(term in combined for term in ("official trailer", "full movie", "netflix", "hbo", "disney", "电影完整版")):
        return "High"
    return "Medium"


def fit_label(score: float) -> str:
    if score >= 12:
        return "A"
    if score >= 5:
        return "B"
    return "C"


def format_selector(height: int) -> str:
    return DEFAULT_VIDEO_FORMAT.format(height=height)


def _find_created_file(stem: Path) -> Path | None:
    candidates = sorted(
        (path for path in stem.parent.glob(f"{stem.name}.*") if not path.name.endswith(".part")),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def run_ytdlp_with_cookie_fallback(
    base_cmd: Sequence[str],
    *,
    browser: str = "",
) -> subprocess.CompletedProcess[str]:
    first = run_command(base_cmd, check=False)
    if first.returncode == 0:
        return first
    browsers = cookie_browser_candidates(browser)
    if not browsers:
        raise CommandError(base_cmd, first.returncode, first.stdout or "")
    attempts = [f"首次尝试：\n{first.stdout}"]
    last_command = list(base_cmd)
    last_returncode = first.returncode
    for browser_name in browsers:
        fallback = list(base_cmd[:-1]) + ["--cookies-from-browser", browser_name, base_cmd[-1]]
        completed = run_command(fallback, check=False)
        if completed.returncode == 0:
            return completed
        attempts.append(f"{browser_name} Cookies 重试：\n{completed.stdout}")
        last_command = fallback
        last_returncode = completed.returncode
    raise CommandError(last_command, last_returncode, "\n".join(attempts))


def cookie_browser_candidates(selection: str) -> list[str]:
    """Return usable yt-dlp browser names without assuming Chrome exists."""
    requested = [item.strip() for item in (selection or "").split(",") if item.strip()]
    if requested and requested != ["auto"]:
        return requested

    home = Path.home()
    system = platform.system()
    browser_paths: list[tuple[str, list[Path]]] = []
    if system == "Darwin":
        support = home / "Library" / "Application Support"
        browser_paths = [
            ("chrome", [support / "Google" / "Chrome"]),
            ("brave", [support / "BraveSoftware" / "Brave-Browser"]),
            ("firefox", [support / "Firefox" / "Profiles"]),
            ("edge", [support / "Microsoft Edge"]),
            ("chromium", [support / "Chromium"]),
            ("safari", [home / "Library" / "Cookies" / "Cookies.binarycookies"]),
        ]
    elif system == "Windows":
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        roaming = Path(os.environ.get("APPDATA", ""))
        browser_paths = [
            ("chrome", [local / "Google" / "Chrome" / "User Data"]),
            ("brave", [local / "BraveSoftware" / "Brave-Browser" / "User Data"]),
            ("edge", [local / "Microsoft" / "Edge" / "User Data"]),
            ("firefox", [roaming / "Mozilla" / "Firefox" / "Profiles"]),
        ]
    else:
        config = home / ".config"
        browser_paths = [
            ("chrome", [config / "google-chrome"]),
            ("brave", [config / "BraveSoftware" / "Brave-Browser"]),
            ("chromium", [config / "chromium"]),
            ("edge", [config / "microsoft-edge"]),
            ("firefox", [home / ".mozilla" / "firefox"]),
        ]
    return [name for name, paths in browser_paths if any(path.exists() for path in paths)]


def download_video(
    *,
    url: str,
    output_stem: Path,
    start: float | None = None,
    end: float | None = None,
    height: int = 1080,
    proxy: str = "",
    browser: str = "",
) -> Path:
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--no-update",
        "--no-playlist",
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "--concurrent-fragments",
        "1",
        "-f",
        format_selector(height),
        "--merge-output-format",
        "mp4",
        "-o",
        str(output_stem) + ".%(ext)s",
    ]
    if start is not None and end is not None:
        if end <= start:
            raise ValueError("片段结束时间必须晚于开始时间")
        cmd += [
            "--download-sections",
            f"*{start:.3f}-{end:.3f}",
            "--force-keyframes-at-cuts",
        ]
    if proxy:
        cmd += ["--proxy", proxy]
    cmd.append(url)
    run_ytdlp_with_cookie_fallback(cmd, browser=browser)
    created = _find_created_file(output_stem)
    if not created:
        raise RuntimeError(f"下载命令成功，但未找到输出文件：{output_stem}")
    return created


def download_image(url: str, output_stem: Path, timeout: int = 90) -> Path:
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 topic-material-collector/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_type()
        suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
        image_suffixes = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".bmp", ".svg"}
        if not content_type.startswith("image/") and suffix not in image_suffixes:
            raise ValueError(f"URL 未返回图片内容：{content_type}")
        if not suffix or len(suffix) > 6:
            suffix = mimetypes.guess_extension(content_type) or ".jpg"
        destination = output_stem.with_suffix(suffix)
        with destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    return destination


def relative_path(path: Path | str | None, root: Path) -> str:
    if not path:
        return ""
    path_obj = Path(path)
    try:
        return str(path_obj.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path_obj)


def normalize_record(record: dict[str, Any], root: Path) -> dict[str, Any]:
    normalized = {field: record.get(field, "") for field in MANIFEST_FIELDS}
    for field in ("segment_start", "segment_end", "source_duration"):
        if normalized[field] not in (None, ""):
            normalized[field] = format_timecode(normalized[field])
    normalized["local_file"] = relative_path(normalized.get("local_file"), root)
    return normalized


def write_manifests(
    records: list[dict[str, Any]],
    project: ProjectPaths,
    *,
    topic: str,
    queries: Sequence[str] | None = None,
    settings: dict[str, Any] | None = None,
) -> None:
    normalized = [normalize_record(record, project.root) for record in records]
    json_path = project.root / "material-manifest.json"
    csv_path = project.root / "material-manifest.csv"
    markdown_path = project.root / "material-manifest.md"
    payload = {
        "topic": topic,
        "queries": list(queries or []),
        "settings": settings or {},
        "materials": normalized,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(normalized)

    lines = [
        f"# 素材清单：{topic}",
        "",
        f"- 素材总数：{len(normalized)}",
        f"- 已下载：{sum(1 for row in normalized if row['local_file'])}",
        "- 风险说明：Low 仅用于来源明确标注开放许可/公版的情况；Medium/High 不代表已获得公开发布授权。",
        "",
        "| # | 类型 | 需要的画面 | 素材与来源 | 目标时间段 | 匹配 | 风险 | 本地文件 | 状态 |",
        "|---:|---|---|---|---|---|---|---|---|",
    ]
    for row in normalized:
        source_label = row["title"] or row["source_url"]
        if row["source_url"]:
            source_label = f"[{escape_md(source_label)}]({row['source_url']})"
        period = ""
        if row["segment_start"] or row["segment_end"]:
            period = f"{row['segment_start']}–{row['segment_end']}"
        lines.append(
            "| {index} | {type} | {need} | {source} | {period} | {fit}/{confidence} | {risk} | {local} | {status} |".format(
                index=row["index"],
                type=escape_md(row["type"]),
                need=escape_md(row["need"]),
                source=source_label,
                period=escape_md(period),
                fit=escape_md(row["fit"]),
                confidence=escape_md(row["confidence"]),
                risk=escape_md(row["risk"]),
                local=escape_md(row["local_file"]),
                status=escape_md(row["status"]),
            )
        )
    if queries:
        lines += ["", "## 使用的检索词", ""]
        lines.extend(f"- `{query}`" for query in queries)
    lines += ["", "## 来源与使用说明", ""]
    for row in normalized:
        lines.append(
            f"- {row['index']}. {row['title'] or row['source_url']} — {row['source_url']} — "
            f"许可：{row['license'] or '未核实'}；风险：{row['risk'] or 'Medium'}"
        )
    noted = [row for row in normalized if row["notes"] or "failed" in row["status"]]
    if noted:
        lines += ["", "## 备注与失败项", ""]
        for row in noted:
            lines.append(f"- {row['index']}. `{row['status']}` — {row['notes'] or '请人工复核'}")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def escape_md(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")
