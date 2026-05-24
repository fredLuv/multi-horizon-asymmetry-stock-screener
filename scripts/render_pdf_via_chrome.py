from __future__ import annotations

import argparse
import html
import subprocess
import tempfile
from pathlib import Path


CHROME_CANDIDATES = [
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
]

DEFAULT_FONT_STACK = (
    '"Songti SC", "STSong", "Noto Serif CJK SC", "Source Han Serif SC", '
    '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", serif'
)


def _find_chrome(explicit_path: str | None) -> Path:
    if explicit_path:
        path = Path(explicit_path)
        if path.exists():
            return path
        raise FileNotFoundError(f"Chrome binary not found at: {path}")

    for candidate in CHROME_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Chrome/Chromium binary not found. Pass --chrome-path explicitly."
    )


def _render_html(title: str, text: str, font_stack: str) -> str:
    escaped_title = html.escape(title)
    escaped_text = html.escape(text)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{escaped_title}</title>
<style>
  @page {{ size: A4; margin: 20mm 16mm; }}
  body {{
    margin: 0;
    color: #111;
    font-size: 14px;
    line-height: 1.68;
    font-family: {font_stack};
    -webkit-font-smoothing: antialiased;
  }}
  .content {{
    white-space: pre-wrap;
    word-break: break-word;
  }}
</style>
</head>
<body>
<div class="content">{escaped_text}</div>
</body>
</html>
"""


def render_pdf(
    input_path: Path, output_path: Path, chrome_path: Path, title: str, font_stack: str
) -> None:
    source = input_path.read_text(encoding="utf-8")
    html_text = _render_html(title=title, text=source, font_stack=font_stack)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", encoding="utf-8", delete=False) as tmp:
        tmp.write(html_text)
        tmp_path = Path(tmp.name)

    try:
        cmd = [
            str(chrome_path),
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--no-pdf-header-footer",
            f"--print-to-pdf={output_path}",
            tmp_path.as_uri(),
        ]
        subprocess.run(cmd, check=True)
    finally:
        tmp_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render UTF-8 plain text to PDF via headless Chrome with a simple CJK-safe layout."
    )
    parser.add_argument("--input", required=True, help="Input UTF-8 text file path.")
    parser.add_argument("--output", required=True, help="Output PDF path.")
    parser.add_argument("--title", default="Document", help="Document title.")
    parser.add_argument("--chrome-path", default=None, help="Optional path to Chrome/Chromium binary.")
    parser.add_argument(
        "--font-family",
        default=DEFAULT_FONT_STACK,
        help="CSS font-family stack for body text.",
    )
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    chrome_path = _find_chrome(args.chrome_path)

    render_pdf(
        input_path=input_path,
        output_path=output_path,
        chrome_path=chrome_path,
        title=args.title,
        font_stack=args.font_family,
    )
    print(output_path)


if __name__ == "__main__":
    main()
