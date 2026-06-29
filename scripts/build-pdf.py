#!/usr/bin/env python3
"""마크다운 → HTML → PDF 변환 (한글 폰트, 표, 코드 블록 대응)

사용법:
    python3 scripts/build-pdf.py <입력.md> [출력.pdf]

예:
    python3 scripts/build-pdf.py docs/mvp-prd.md
    python3 scripts/build-pdf.py docs/린캔버스-lean-canvas.md docs/out.pdf

의존성:
    pip install markdown2 weasyprint
    sudo apt-get install fonts-noto-cjk (Ubuntu/WSL)
"""

import sys
from pathlib import Path

import markdown2

CSS = """
@page {
    size: A4;
    margin: 20mm 18mm 22mm 18mm;
    @bottom-center {
        content: counter(page) " / " counter(pages);
        font-size: 9px;
        color: #999;
        font-family: 'Pretendard', 'Noto Sans KR', sans-serif;
    }
}

@font-face {
    font-family: 'Pretendard';
    src: local('Pretendard'), local('Noto Sans KR'), local('Malgun Gothic');
}

* { box-sizing: border-box; }

body {
    font-family: 'Pretendard', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
    font-size: 10.5pt;
    line-height: 1.7;
    color: #1a1a1a;
}

h1 {
    font-size: 22pt;
    font-weight: 800;
    color: #1a1a2e;
    border-bottom: 3px solid #e94560;
    padding-bottom: 12px;
    margin-top: 0;
    margin-bottom: 20px;
    letter-spacing: -0.5px;
}

h2 {
    font-size: 15pt;
    font-weight: 700;
    color: #16213e;
    margin-top: 32px;
    margin-bottom: 14px;
    padding: 8px 14px;
    background: linear-gradient(135deg, #f0f4ff 0%, #e8ecf5 100%);
    border-left: 4px solid #e94560;
    border-radius: 0 6px 6px 0;
    page-break-after: avoid;
}

h3 {
    font-size: 12.5pt;
    font-weight: 700;
    color: #0f3460;
    margin-top: 22px;
    margin-bottom: 10px;
    padding-bottom: 4px;
    border-bottom: 1.5px solid #dde;
    page-break-after: avoid;
}

h4 {
    font-size: 11pt;
    font-weight: 600;
    color: #533483;
    margin-top: 16px;
    margin-bottom: 8px;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 14px 0 18px 0;
    font-size: 9.5pt;
}

thead { display: table-header-group; }
tr { page-break-inside: avoid; }

th {
    background: #16213e;
    color: #fff;
    font-weight: 600;
    padding: 8px 10px;
    text-align: left;
    font-size: 9pt;
}

td {
    padding: 7px 10px;
    border-bottom: 1px solid #e0e0e0;
    vertical-align: top;
}

tr:nth-child(even) td { background: #f8f9fc; }

blockquote {
    margin: 12px 0;
    padding: 10px 16px;
    background: #fff8f0;
    border-left: 4px solid #e94560;
    border-radius: 0 6px 6px 0;
    color: #333;
    font-size: 10pt;
}

pre {
    background: #f5f6fa;
    border: 1px solid #dde;
    border-radius: 8px;
    padding: 14px 18px;
    font-size: 9pt;
    line-height: 1.5;
    overflow-x: auto;
    font-family: 'D2Coding', 'Consolas', 'Courier New', monospace;
    page-break-inside: avoid;
}

code {
    font-family: 'D2Coding', 'Consolas', 'Courier New', monospace;
    font-size: 9pt;
    background: #f0f1f5;
    padding: 1px 5px;
    border-radius: 3px;
}

pre code { background: none; padding: 0; }

ul, ol { margin: 8px 0; padding-left: 22px; }
li { margin-bottom: 4px; }
strong { color: #16213e; }
em { font-style: italic; color: #555; }
hr { border: none; border-top: 1.5px solid #e0e0e0; margin: 28px 0; }
a { color: #e94560; text-decoration: none; }

h2, h3, h4 { page-break-after: avoid; }
table, pre, blockquote { page-break-inside: avoid; }
"""


def build(md_path: Path, pdf_path: Path) -> None:
    md_text = md_path.read_text(encoding="utf-8")
    body = markdown2.markdown(
        md_text,
        extras=["tables", "fenced-code-blocks", "header-ids", "break-on-newline"],
    )

    html_path = pdf_path.with_suffix(".html")
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{md_path.stem}</title>
<style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>
"""
    html_path.write_text(html, encoding="utf-8")
    print(f"HTML 생성: {html_path}")

    from weasyprint import HTML as WHTML
    WHTML(filename=str(html_path)).write_pdf(str(pdf_path))
    print(f"PDF 생성: {pdf_path}")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    md_path = Path(sys.argv[1]).resolve()
    if not md_path.exists():
        print(f"파일 없음: {md_path}")
        return 2

    if len(sys.argv) >= 3:
        pdf_path = Path(sys.argv[2]).resolve()
    else:
        pdf_path = md_path.with_suffix(".pdf")

    build(md_path, pdf_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
