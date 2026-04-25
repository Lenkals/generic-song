#!/usr/bin/env python3
"""Generic Song Video Builder
  Step 1 — Merge all audio files → merged_audio.wav + .mp3
  Step 2 — YouTube 4K video (first.png 3s + video content + last.png 3s + logo)
  Step 3 — Insta Reels 11s (9s from YouTube start, cropped 9:16 + 2s insta-last.png)
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

BASE       = Path(__file__).parent
AUDIO_DIR  = BASE / "audio"
IMAGES_DIR = BASE / "images"
VIDEO_DIR  = BASE / "video"
OUTPUT_DIR = BASE / "output"

SCALE_4K    = ("scale=3840:2160:force_original_aspect_ratio=decrease,"
               "pad=3840:2160:(ow-iw)/2:(oh-ih)/2:black")
SCALE_REELS = ("scale=1080:1920:force_original_aspect_ratio=increase,"
               "crop=1080:1920")
FPS         = "fps=30"

# ── helpers ──────────────────────────────────────────────────────────────────

def find_image(stem: str) -> Path | None:
    for ext in (".png", ".jpg", ".jpeg"):
        for d in (IMAGES_DIR, AUDIO_DIR):
            p = d / f"{stem}{ext}"
            if p.exists():
                return p
    return None


def find_audio_files() -> list[Path]:
    skip = {"first", "last", "logo", "insta-last"}
    files = [
        f for ext in (".mp3", ".wav")
        for f in AUDIO_DIR.glob(f"*{ext}")
        if f.stem.lower() not in skip
    ]
    return sorted(files)


def find_video_files() -> list[Path]:
    return sorted(VIDEO_DIR.glob("*.mp4"))


def get_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(r.stdout)["format"]["duration"])


def ff(*args, desc: str = "") -> None:
    if desc:
        print(f"  ► {desc}")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print("  ✗ ffmpeg failed — see above for details")
        sys.exit(1)


def write_concat_list(paths: list[Path], out: Path) -> None:
    out.write_text("\n".join(f"file '{p.resolve()}'" for p in paths),
                   encoding="utf-8")


def menu(prompt: str, options: list[tuple[str, str]]) -> str:
    print(f"\n{prompt}")
    for i, (label, _) in enumerate(options, 1):
        print(f"  {i}. {label}")
    while True:
        try:
            c = int(input("  Choice: "))
            if 1 <= c <= len(options):
                return options[c - 1][1]
        except (ValueError, KeyboardInterrupt):
            pass
        print("  Invalid — try again.")


def make_image_seg(img: Path, duration: float, scale: str, out: Path) -> None:
    ff("-loop", "1", "-i", str(img),
       "-t", str(duration),
       "-vf", f"{scale},{FPS}",
       "-c:v", "libx264", "-pix_fmt", "yuv420p",
       str(out),
       desc=f"Image seg  {out.name}  ({duration}s)")


def make_video_seg(src: Path, duration: float, scale: str, out: Path,
                   loop: bool = False) -> None:
    args = []
    if loop:
        args += ["-stream_loop", "-1"]
    args += ["-i", str(src),
             "-t", str(duration),
             "-vf", f"{scale},{FPS}",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
             str(out)]
    ff(*args, desc=f"Video seg  {out.name}  ({duration:.1f}s)"
                   + ("  [looped]" if loop else ""))


# ── step 1 ───────────────────────────────────────────────────────────────────

def step1_merge_audio(audio_files: list[Path]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(exist_ok=True)
    lst = OUTPUT_DIR / "_audio_list.txt"
    write_concat_list(audio_files, lst)

    wav = OUTPUT_DIR / "merged_audio.wav"
    mp3 = OUTPUT_DIR / "merged_audio.mp3"

    ff("-f", "concat", "-safe", "0", "-i", str(lst),
       str(wav), desc="Merging audio → WAV")

    ff("-i", str(wav),
       "-codec:a", "libmp3lame", "-qscale:a", "2",
       str(mp3), desc="Converting → MP3")

    lst.unlink(missing_ok=True)
    return wav, mp3


# ── step 2 ───────────────────────────────────────────────────────────────────

def step2_youtube(audio_wav: Path, video_files: list[Path], mode: str,
                  first_img: Path, last_img: Path, logo_img: Path) -> Path:
    tmp = OUTPUT_DIR / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    audio_dur   = get_duration(audio_wav)
    content_dur = max(audio_dur - 6, 1.0)   # 3s first + 3s last
    print(f"\n  Song duration: {audio_dur:.1f}s | Video content slot: {content_dur:.1f}s")

    # image bookends
    first_seg = tmp / "seg_000_first.mp4"
    last_seg  = tmp / "seg_999_last.mp4"
    make_image_seg(first_img, 3, SCALE_4K, first_seg)
    make_image_seg(last_img,  3, SCALE_4K, last_seg)

    video_segs: list[Path] = []
    n = len(video_files)

    if mode == "roundrobin":
        # cycle through videos in order; each plays its full length;
        # repeat the cycle until content_dur is filled
        total, cycle_i, seg_i = 0.0, 0, 1
        while total < content_dur - 0.05:
            v         = video_files[cycle_i % n]
            v_dur     = get_duration(v)
            seg_dur   = min(v_dur, content_dur - total)
            out       = tmp / f"seg_{seg_i:03d}.mp4"
            make_video_seg(v, seg_dur, SCALE_4K, out)
            video_segs.append(out)
            total  += seg_dur
            cycle_i += 1
            seg_i  += 1

    else:   # static — equal time slots, each video loops its slot
        slot = content_dur / n
        for i, v in enumerate(video_files):
            out = tmp / f"seg_{i+1:03d}.mp4"
            make_video_seg(v, slot, SCALE_4K, out, loop=True)
            video_segs.append(out)

    # concat all video-only segments
    all_segs = [first_seg, *video_segs, last_seg]
    lst = tmp / "_video_list.txt"
    write_concat_list(all_segs, lst)

    raw_vid = tmp / "_raw_video.mp4"
    ff("-f", "concat", "-safe", "0", "-i", str(lst),
       "-c", "copy", str(raw_vid), desc="Concatenating segments")

    # logo overlay + audio mux → final 4K output
    logo_filter = (
        "[1:v]scale=200:-1[logo];"
        "[0:v][logo]overlay=W-w-30:H-h-30[outv]"
    )
    youtube_out = OUTPUT_DIR / "youtube_4k.mp4"
    ff("-i", str(raw_vid),
       "-i", str(logo_img),
       "-i", str(audio_wav),
       "-filter_complex", logo_filter,
       "-map", "[outv]", "-map", "2:a",
       "-c:v", "libx264", "-crf", "18", "-preset", "slow",
       "-c:a", "aac", "-b:a", "320k",
       "-shortest",
       str(youtube_out),
       desc="Logo overlay + audio → youtube_4k.mp4")

    _cleanup_tmp(tmp)
    return youtube_out


# ── step 3 ───────────────────────────────────────────────────────────────────

def step3_insta(youtube_vid: Path, insta_last_img: Path,
                audio_wav: Path) -> Path:
    tmp = OUTPUT_DIR / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    # 9-sec clip from start of YouTube video, center-cropped to 9:16
    clip = tmp / "insta_clip.mp4"
    ff("-i", str(youtube_vid),
       "-t", "9",
       "-vf", f"{SCALE_REELS},{FPS}",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
       str(clip),
       desc="Extracting 9-sec 9:16 clip from YouTube video")

    # 2-sec insta-last.png at 9:16
    last_seg = tmp / "insta_last.mp4"
    make_image_seg(insta_last_img, 2, SCALE_REELS, last_seg)

    lst = tmp / "_insta_list.txt"
    write_concat_list([clip, last_seg], lst)

    insta_out = OUTPUT_DIR / "insta_reels.mp4"
    ff("-f", "concat", "-safe", "0", "-i", str(lst),
       "-i", str(audio_wav),
       "-map", "0:v", "-map", "1:a",
       "-c:v", "libx264", "-crf", "23", "-preset", "fast",
       "-c:a", "aac", "-b:a", "192k",
       "-t", "11",
       str(insta_out),
       desc="Creating insta_reels.mp4  (9:16, 11s)")

    _cleanup_tmp(tmp)
    return insta_out


def _cleanup_tmp(tmp: Path) -> None:
    shutil.rmtree(tmp, ignore_errors=True)


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 52)
    print("  Generic Song Video Builder")
    print("=" * 52)

    audio_files  = find_audio_files()
    video_files  = list(find_video_files())
    first_img    = find_image("first")
    last_img     = find_image("last")
    logo_img     = find_image("logo")
    insta_last   = find_image("insta-last")

    # validate
    errors: list[str] = []
    if not audio_files:
        errors.append("No audio (.mp3/.wav) found in audio/")
    if not video_files:
        errors.append("No .mp4 files found in video/")
    for name, img in (("first", first_img), ("last", last_img),
                      ("logo", logo_img), ("insta-last", insta_last)):
        if img is None:
            errors.append(f"Required image not found: {name}.png / .jpg")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)

    print(f"\nAudio  : {[f.name for f in audio_files]}")
    print(f"Videos : {[f.name for f in video_files]}")
    print(f"Images : first={first_img.name}  last={last_img.name}  "
          f"logo={logo_img.name}  insta-last={insta_last.name}")

    mode = menu("Video playback mode:", [
        ("Round Robin — videos cycle in order, each plays fully, repeat to fill song", "roundrobin"),
        ("Static      — song time split equally; each video loops its own time slot",  "static"),
    ])

    steps = menu("Steps to run:", [
        ("All  (Step 1 + 2 + 3)",                                "123"),
        ("Step 1 only  — Merge audio",                           "1"),
        ("Step 2 only  — YouTube 4K  (needs merged_audio.wav)",  "2"),
        ("Step 3 only  — Insta Reels (needs youtube_4k.mp4)",    "3"),
        ("Steps 1 + 2  — Audio + YouTube",                       "12"),
        ("Steps 2 + 3  — YouTube + Insta (needs merged_audio.wav)", "23"),
    ])

    OUTPUT_DIR.mkdir(exist_ok=True)
    wav = OUTPUT_DIR / "merged_audio.wav"

    if "1" in steps:
        print("\n─── Step 1 : Merge Audio ───────────────────────────")
        wav, mp3 = step1_merge_audio(audio_files)
        print(f"  ✓ {wav.name}")
        print(f"  ✓ {mp3.name}")

    if "2" in steps:
        print("\n─── Step 2 : YouTube 4K ────────────────────────────")
        yt = step2_youtube(wav, video_files, mode,
                           first_img, last_img, logo_img)
        print(f"  ✓ {yt}")

    if "3" in steps:
        print("\n─── Step 3 : Insta Reels ───────────────────────────")
        yt_vid = OUTPUT_DIR / "youtube_4k.mp4"
        insta  = step3_insta(yt_vid, insta_last, wav)
        print(f"  ✓ {insta}")

    print(f"\n{'=' * 52}")
    print(f"  Done!  Outputs in: {OUTPUT_DIR}")
    print(f"{'=' * 52}")


if __name__ == "__main__":
    main()
