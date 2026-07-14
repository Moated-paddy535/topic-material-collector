# Topic Material Collector

[中文](#中文说明) | [English](#english)

An open-source Codex skill for researching, timestamping, downloading, clipping, renaming, and cataloging video-first materials for a topic, script, narration, or shot list.

It uses YouTube discovery, subtitles, chapters, `yt-dlp`, and FFmpeg to create traceable editing packages with source URLs, timestamps, confidence levels, license notes, and reuse-risk labels.

## 中文说明

`topic-material-collector` 是一个面向 Codex 的开源素材收集 Skill。输入选题、脚本、旁白或分镜需求后，它可以：

- 生成中英文素材检索词；
- 优先检索 YouTube 视频；
- 根据字幕和章节自动定位相关时间段；
- 下载完整视频或只裁剪目标片段；
- 下载跨平台候选视频与图片；
- 统一重命名素材；
- 输出 Markdown、CSV 和 JSON 素材清单；
- 保留来源、作者、时间戳、许可信息和复用风险。

“全网检索”表示尽可能覆盖多个公开来源，不代表能够索引互联网中的所有页面。下载素材也不代表获得公开发布授权。

### 系统要求

- Python 3.10 或更高版本；
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp)；
- [`ffmpeg` 和 `ffprobe`](https://ffmpeg.org/)；
- Codex 或其他支持 `SKILL.md` 工作流的智能体环境。

macOS：

```bash
brew install python yt-dlp ffmpeg
```

Ubuntu / Debian：

```bash
sudo apt update
sudo apt install -y python3 ffmpeg
python3 -m pip install --user -U yt-dlp
```

Windows：

```powershell
winget install Python.Python.3.12
winget install yt-dlp.yt-dlp
winget install Gyan.FFmpeg
```

安装完成后确认以下命令可用：

```bash
python3 --version
yt-dlp --version
ffmpeg -version
ffprobe -version
```

### 安装 Skill

克隆仓库：

```bash
git clone https://github.com/macong0420/topic-material-collector.git
```

安装到 Codex 默认 Skill 目录：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R topic-material-collector/topic-material-collector \
  "${CODEX_HOME:-$HOME/.codex}/skills/topic-material-collector"
```

重新启动 Codex 或刷新 Skill 列表，然后使用 `$topic-material-collector` 调用。

### 在 Codex 中使用

示例提示词：

```text
$topic-material-collector 收集伊隆·马斯克相关视频素材，覆盖 PayPal、Tesla、SpaceX、Twitter/X 和 Grok，制作约 10 分钟人物解说片。
```

```text
$topic-material-collector 根据这份旁白寻找 B-roll，只下载中高置信度片段，输出到 /绝对路径/project-name。
```

默认使用 `clips` 模式，只下载自动判断为中高置信度的目标片段。正式剪辑前仍应检查实际画面。

### 直接运行脚本

YouTube 检索、时间戳定位与片段下载：

```bash
python3 topic-material-collector/scripts/collect_youtube.py \
  --topic "第一代 iPhone 发布" \
  --outdir "/absolute/path/materials" \
  --mode clips \
  --query "Steve Jobs introduces iPhone 2007"
```

只生成候选目录，不下载：

```bash
python3 topic-material-collector/scripts/collect_youtube.py \
  --topic "第一代 iPhone 发布" \
  --outdir "/absolute/path/materials" \
  --mode catalog \
  --max-downloads 0
```

按人工审核后的跨平台清单下载：

```bash
python3 topic-material-collector/scripts/fetch_candidates.py \
  /absolute/path/candidates.json \
  --outdir "/absolute/path/materials"
```

候选 JSON 格式见 [`candidate-schema.md`](topic-material-collector/references/candidate-schema.md)。

### 输出结构

```text
project/
├── clips/                  # 已裁剪的目标片段
├── full/                   # 完整视频
├── images/                 # 图片素材
├── metadata/               # 视频元数据与分析文件
├── subtitles/              # 时间戳分析使用的字幕
├── thumbnails/             # 候选缩略图
├── material-manifest.md    # 人工阅读清单
├── material-manifest.csv   # 表格清单
└── material-manifest.json  # 机器可读清单
```

### Cookie、代理与下载失败

YouTube 返回 403 或 SABR 错误时，脚本会自动检测本机浏览器 Cookie。也可以手动指定：

```bash
--cookies-from-browser brave
```

需要代理时：

```bash
--proxy http://127.0.0.1:7890
```

不要绕过 DRM、付费墙、登录限制、地理限制或水印。

### 版权与使用风险

- `Low`：来源明确标注 Public Domain、CC0 或开放许可；
- `Medium`：可以观看，但复用权利不明确或受到平台条款限制；
- `High`：电影、电视、付费新闻、来源不明搬运或明显受保护素材。

本项目提供研究与素材管理工具，不提供版权授权。公开或商业发布前，请自行核验并取得必要许可。

## English

`topic-material-collector` is an open-source Codex skill that turns a topic, script, narration, or shot list into a traceable, video-first material package.

### Features

- Generate focused Chinese and English search queries.
- Search YouTube first and deduplicate candidates.
- Locate relevant ranges using subtitles and creator chapters.
- Download complete videos or targeted clips.
- Fetch reviewed cross-platform video and image candidates.
- Normalize filenames and preserve attribution.
- Produce Markdown, CSV, and JSON manifests.
- Track source URLs, creators, timestamps, confidence, license metadata, and reuse risk.

“Broad web research” means researching across useful public sources; it is not a claim that every page on the internet is indexed. Downloading an asset does not grant publication rights.

### Requirements

- Python 3.10+
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp)
- [`ffmpeg` and `ffprobe`](https://ffmpeg.org/)
- Codex or another agent environment that supports `SKILL.md` workflows

macOS:

```bash
brew install python yt-dlp ffmpeg
```

Ubuntu / Debian:

```bash
sudo apt update
sudo apt install -y python3 ffmpeg
python3 -m pip install --user -U yt-dlp
```

Windows:

```powershell
winget install Python.Python.3.12
winget install yt-dlp.yt-dlp
winget install Gyan.FFmpeg
```

### Installation

```bash
git clone https://github.com/macong0420/topic-material-collector.git
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R topic-material-collector/topic-material-collector \
  "${CODEX_HOME:-$HOME/.codex}/skills/topic-material-collector"
```

Restart Codex or refresh the skill list, then invoke `$topic-material-collector`.

### Use with Codex

```text
$topic-material-collector Collect video materials about Elon Musk, covering PayPal, Tesla, SpaceX, Twitter/X, and Grok for a 10-minute explainer.
```

```text
$topic-material-collector Find B-roll for this narration, download only medium/high-confidence clips, and save the package under /absolute/path/project-name.
```

### Run the scripts directly

Research YouTube, locate timestamps, and download clips:

```bash
python3 topic-material-collector/scripts/collect_youtube.py \
  --topic "The original iPhone launch" \
  --outdir "/absolute/path/materials" \
  --mode clips \
  --query "Steve Jobs introduces iPhone 2007"
```

Catalog candidates without downloading:

```bash
python3 topic-material-collector/scripts/collect_youtube.py \
  --topic "The original iPhone launch" \
  --outdir "/absolute/path/materials" \
  --mode catalog \
  --max-downloads 0
```

Fetch a reviewed cross-platform candidate list:

```bash
python3 topic-material-collector/scripts/fetch_candidates.py \
  /absolute/path/candidates.json \
  --outdir "/absolute/path/materials"
```

See [`candidate-schema.md`](topic-material-collector/references/candidate-schema.md) for the candidate JSON schema.

### Output

Each run creates folders for clips, full videos, images, metadata, subtitles, and thumbnails, plus human-readable and machine-readable manifests.

### Cookies and proxies

The scripts can retry YouTube requests using locally available browser cookies. Override browser detection with:

```bash
--cookies-from-browser brave
```

Use a proxy when needed:

```bash
--proxy http://127.0.0.1:7890
```

The project does not bypass DRM, paywalls, authentication, geographic restrictions, or watermarks.

### Rights and safety

- `Low`: explicitly public domain, CC0, or clearly open-licensed.
- `Medium`: viewable, but reuse rights are unclear or platform-limited.
- `High`: films, television, paid news, unclear reuploads, or evidently protected material.

This repository provides research and material-management tooling, not copyright clearance. Verify rights and obtain permission before public or commercial use.

## License

Released under the [MIT License](LICENSE).

