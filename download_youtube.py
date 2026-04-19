from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download a YouTube video to a local folder using yt-dlp."
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "-o",
        "--output-dir",
        default="downloads",
        help="Directory to save the downloaded file into (default: downloads)",
    )
    parser.add_argument(
        "-n",
        "--name",
        default="%(title)s.%(ext)s",
        help="Output filename template (default: %(title)s.%(ext)s)",
    )
    parser.add_argument(
        "-f",
        "--format",
        default="mp4/bestvideo+bestaudio/best",
        help="yt-dlp format selector (default prefers mp4)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        print(
            "yt-dlp is not installed. Install it with:\n"
            "  venv/bin/pip install yt-dlp",
            file=sys.stderr,
        )
        return 1

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "format": args.format,
        "outtmpl": str(output_dir / args.name),
        "noplaylist": True,
        "merge_output_format": "mp4",
    }

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([args.url])

    print(f"Downloaded into: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
