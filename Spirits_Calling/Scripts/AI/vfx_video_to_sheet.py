#!/usr/bin/env python3
"""
Convert a generated VFX video (mp4/webm/gif) into a UE-ready sprite sheet PNG.

Uses ffmpeg/ffprobe (ComfyUI bundles ffmpeg; usually on PATH). No Python image deps.
It samples ~cols*rows evenly-spaced frames and tiles them into one grid image.

Usage:
    python vfx_video_to_sheet.py --video "C:\\...\\ComfyUI\\output\\video\\LTX_2.3_ia2v_00001.mp4"
    python vfx_video_to_sheet.py --video in.webm --cols 4 --rows 4 --cell 256 --name slash_light
    python vfx_video_to_sheet.py --video in.mp4 --pingpong          # forward+reverse for seamless loops

Output: RawAssets/AI/VFX/sheets/<name>_sheet.png  (name defaults to the video's stem)
"""

import argparse
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(PROJECT_ROOT, "RawAssets", "AI", "VFX", "sheets")


def which(cmd):
    from shutil import which as _w
    return _w(cmd) or _w(cmd + ".exe")


def probe_frame_count(ffprobe, video):
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-count_frames", "-select_streams", "v:0",
             "-show_entries", "stream=nb_read_frames", "-of", "default=nokey=1:noprint_wrappers=1", video],
            capture_output=True, text=True, timeout=120)
        n = out.stdout.strip().splitlines()[0] if out.stdout.strip() else ""
        return int(n) if n.isdigit() else 0
    except Exception:
        return 0


def main():
    ap = argparse.ArgumentParser(description="VFX video -> sprite sheet")
    ap.add_argument("--video", required=True, help="Path to the generated video")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--rows", type=int, default=4)
    ap.add_argument("--cell", type=int, default=256, help="Cell size in px (square)")
    ap.add_argument("--name", default="", help="Output name (default: video filename stem)")
    ap.add_argument("--pingpong", action="store_true", help="Append reversed frames for a seamless loop")
    args = ap.parse_args()

    ffmpeg = which("ffmpeg")
    ffprobe = which("ffprobe")
    if not ffmpeg:
        print("[vfx] ERROR: ffmpeg not found on PATH. Install ffmpeg or add ComfyUI's ffmpeg to PATH.")
        sys.exit(1)
    if not os.path.isfile(args.video):
        print(f"[vfx] ERROR: video not found: {args.video}")
        sys.exit(1)

    os.makedirs(OUT_DIR, exist_ok=True)
    stem = args.name or os.path.splitext(os.path.basename(args.video))[0]
    out_path = os.path.join(OUT_DIR, f"{stem}_sheet.png")

    want = args.cols * args.rows
    total = probe_frame_count(ffprobe, args.video) if ffprobe else 0
    step = max(1, round(total / want)) if total >= want else 1
    print(f"[vfx] {os.path.basename(args.video)}: total frames={total or '?'}, want={want}, step={step}")

    # Build the frame-selection + tiling filter graph.
    cell = args.cell
    scale_pad = (f"scale={cell}:{cell}:force_original_aspect_ratio=decrease,"
                 f"pad={cell}:{cell}:(ow-iw)/2:(oh-ih)/2:color=black")
    if args.pingpong:
        # split -> forward + reversed -> concat -> tile
        vf = (f"select='not(mod(n\\,{step}))',setpts=N/TB,{scale_pad},"
              f"split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0[c];[c]tile={args.cols}x{args.rows}")
    else:
        vf = f"select='not(mod(n\\,{step}))',{scale_pad},tile={args.cols}x{args.rows}"

    cmd = [ffmpeg, "-y", "-i", args.video, "-vf", vf, "-frames:v", "1", out_path]
    print("[vfx] running ffmpeg ...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.isfile(out_path):
        print("[vfx] ffmpeg FAILED:")
        print(res.stderr[-1500:])
        sys.exit(1)

    print(f"[vfx] saved sprite sheet: {out_path}")
    print(f"[vfx] UE Niagara SubUV Sub Image Size = ({args.cols},{args.rows})")


if __name__ == "__main__":
    main()
