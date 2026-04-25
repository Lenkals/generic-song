# Generic Song Video Builder

A Python script that merges audio files and generates YouTube 4K and Instagram Reels videos from images and video clips.

## Requirements

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) (must be in system PATH)

## Folder Structure

```
Generic-song/
├── audio/          # Put your .mp3 / .wav audio files here
│                   # Also place images here if images/ is empty:
│                   #   first.png, last.png, logo.png, insta-last.png
├── images/         # Optional: place first/last/logo/insta-last images here
├── video/          # Put your .mp4 video clips here
├── output/         # Generated files are saved here (auto-created)
└── build.py        # Main script
```

### Required Images

| File | Used in |
|------|---------|
| `first.png` / `.jpg` | First 3 seconds of YouTube video |
| `last.png` / `.jpg` | Last 3 seconds of YouTube video |
| `logo.png` / `.jpg` | Overlaid bottom-right on YouTube video |
| `insta-last.png` / `.jpg` | Last 2 seconds of Insta Reels video |

Images can live in either `images/` or `audio/` — the script checks both.

### Audio Files

- Place any number of `.mp3` or `.wav` files in `audio/`
- They are merged **in alphabetical order** — prefix with numbers to control sequence:
  ```
  01-intro.wav
  02-verse.mp3
  03-outro.wav
  ```

### Video Files

- Place any number of `.mp4` files in `video/`
- Sorted alphabetically — prefix with numbers to control order

## Usage

```bash
python build.py
```

The script shows a simple menu:

### Step 1 — Select video playback mode

| Mode | Behaviour |
|------|-----------|
| **Round Robin** | Videos cycle in order (`v1 → v2 → v3 → v1 → ...`), each plays its full length, repeating until the song duration is filled |
| **Static** | Song time is divided equally among videos; each video loops within its own time slot before the next one plays |

### Step 2 — Select steps to run

| Option | Description |
|--------|-------------|
| All (1+2+3) | Full pipeline |
| Step 1 only | Merge audio only |
| Step 2 only | YouTube 4K video (requires `output/merged_audio.wav`) |
| Step 3 only | Insta Reels (requires `output/youtube_4k.mp4` + `merged_audio.wav`) |
| Steps 1+2 | Audio merge + YouTube |
| Steps 2+3 | YouTube + Insta (requires `merged_audio.wav`) |

## Output Files

| File | Format | Details |
|------|--------|---------|
| `output/merged_audio.wav` | WAV | All audio files merged in sequence |
| `output/merged_audio.mp3` | MP3 | Same merge, compressed |
| `output/youtube_4k.mp4` | MP4 3840×2160 | `first.png` (3s) + video content + `last.png` (3s) + logo overlay, muxed with merged audio |
| `output/insta_reels.mp4` | MP4 1080×1920 | First 9s of YouTube video cropped to 9:16 + `insta-last.png` (2s) = 11s total |

## Pipeline Overview

```
audio/*.mp3|wav  ──►  merged_audio.wav / .mp3
                               │
images/ + video/*.mp4          │
       │                       ▼
       └──────────────►  youtube_4k.mp4  (3840×2160, 16:9)
                               │
                               └──►  insta_reels.mp4  (1080×1920, 9:16, 11s)
```
