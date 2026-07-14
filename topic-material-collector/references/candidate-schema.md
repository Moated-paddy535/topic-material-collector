# Candidate List Schema

Read this reference when creating a cross-platform `candidates.json` for `fetch_candidates.py`.

## Shape

Use a JSON object with `topic` and `materials`. A bare array is accepted, but the object form produces a clearer project name.

```json
{
  "topic": "第一代 iPhone 发布",
  "materials": [
    {
      "type": "video",
      "need": "乔布斯滑动解锁并展示触控操作",
      "title": "Steve Jobs introduces iPhone in 2007",
      "creator": "Source channel",
      "source": "YouTube",
      "url": "https://www.youtube.com/watch?v=VIDEO_ID",
      "start": "00:03:42",
      "end": "00:04:02",
      "segment_excerpt": "Jobs demonstrates slide to unlock",
      "fit": "A",
      "confidence": "high",
      "license": "",
      "risk": "Medium",
      "download": true,
      "notes": "Private editing reference; verify publication rights"
    },
    {
      "type": "image",
      "need": "第一代 iPhone 产品正面图",
      "title": "Original iPhone product image",
      "creator": "Museum or archive",
      "source": "Institutional archive",
      "url": "https://example.org/original-iphone.jpg",
      "fit": "A",
      "confidence": "reviewed",
      "license": "CC BY 4.0",
      "risk": "Low",
      "download": true
    },
    {
      "type": "video",
      "need": "商业纪录片参考镜头",
      "title": "Licensed archive reference",
      "source": "Paid archive",
      "url": "https://example.org/licensing-page",
      "download": false,
      "risk": "High",
      "notes": "Reference only; requires manual licensing"
    }
  ]
}
```

## Fields

| Field | Required | Meaning |
|---|---:|---|
| `type` | Yes | `video` or `image` |
| `url` / `source_url` | Yes | Direct asset URL or a downloader-supported platform page |
| `need` | Recommended | The requested visual this candidate serves |
| `title` | Recommended | Human-readable source title; also used in filenames |
| `creator` | Recommended | Channel, photographer, archive, or publisher |
| `source` | Recommended | Platform or repository name |
| `start`, `end` | For clips | Seconds or `HH:MM:SS`; omit both for full video |
| `segment_excerpt` | Recommended | Why this time range matches |
| `fit` | Recommended | `A`, `B`, or `C` |
| `confidence` | Recommended | `high`, `medium`, `low`, or `reviewed` |
| `license` | Recommended | Exact source metadata; leave blank rather than guessing |
| `risk` | Recommended | `Low`, `Medium`, or `High` |
| `download` | Optional | Defaults to `true`; set `false` for reference-only items |
| `notes` | Optional | Crop, edit, licensing, login, or fallback guidance |

For images, prefer a direct image URL. If the page hides the asset behind JavaScript, login, payment, or a license flow, set `download: false` and retain the source page for manual action.

