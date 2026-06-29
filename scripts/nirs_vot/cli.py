"""NIRS-VOT 분석 CLI 실행기.

사용 예:
    # 파일 경로 + 조건을 지정해 한 파일의 두 세션(Baseline, Recovery2) 분석
    python -m scripts.nirs_vot.cli --file 참고자료/.../이찬민_NOR_Calf.txt --condition NOR

    # 3조건 6세션 전체 일괄 실행
    python -m scripts.nirs_vot.cli --all --data-dir "참고자료/NIRS_VOT(SmO2) 데이터" --out docs/결과-results

결과물:
    - 콘솔에 세션별 12 지표 테이블 출력
    - {out}/{condition}_{session}.png : 그래프
    - {out}/summary.csv : 전체 세션 지표 요약
    - {out}/{condition}_{session}.csv : 세션별 상세 지표
"""

from __future__ import annotations
import argparse
import sys
from dataclasses import asdict, fields
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # CLI/GUI-less 환경용

import pandas as pd

# Windows 기본 콘솔 코드페이지(cp949)가 유니코드 이모지/기호를 못 찍어
# UnicodeEncodeError를 내는 문제를 방지한다. 가능한 경우 UTF-8로 재설정,
# 불가능하면 인코딩 에러를 replace로 흘려 보낸다.
for _stream_name in ("stdout", "stderr"):
    _s = getattr(sys, _stream_name, None)
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# 패키지/스크립트 양쪽에서 실행 가능하게 양방향 import 지원
try:
    from .loader import load_calf_csv
    from .preprocess import preprocess
    from .anchors import SESSION_ANCHORS, get_anchors
    from .metrics import compute_metrics, MetricsResult
    from .plot import plot_session
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from nirs_vot.loader import load_calf_csv         # type: ignore
    from nirs_vot.preprocess import preprocess        # type: ignore
    from nirs_vot.anchors import SESSION_ANCHORS, get_anchors  # type: ignore
    from nirs_vot.metrics import compute_metrics, MetricsResult  # type: ignore
    from nirs_vot.plot import plot_session            # type: ignore


CONDITIONS = list(SESSION_ANCHORS.keys())
SESSIONS = list(next(iter(SESSION_ANCHORS.values())).keys())


def default_file_path(data_dir: Path, condition: str) -> Path:
    """`이찬민_{condition}_Calf.txt` 우선, 없으면 xlsx fallback."""
    txt = data_dir / f"이찬민_{condition}_Calf.txt"
    if txt.exists():
        return txt
    xlsx = data_dir / f"이찬민_{condition}_Calf.xlsx"
    if xlsx.exists():
        return xlsx
    raise FileNotFoundError(
        f"{condition} 데이터 파일을 찾지 못함: {txt} 또는 {xlsx}"
    )


def _load_any(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".txt":
        return load_calf_csv(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        # xlsx도 같은 CSV 구조를 가지지만 openpyxl로 읽고 재구성
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        header_row_idx = next(i for i, r in enumerate(rows) if r and r[0] == "mm-dd")
        header = [c for c in rows[header_row_idx] if c is not None]
        data = [r[: len(header)] for r in rows[header_row_idx + 1 :] if r and r[0]]
        df = pd.DataFrame(data, columns=header)
        # loader와 동일한 후처리
        df = df.rename(columns={
            "mm-dd": "mm_dd",
            "hh:mm:ss": "time_str",
            "SmO2 Live": "SmO2_live",
            "SmO2 Averaged": "SmO2_avg",
            "THb": "THb",
            "Lap": "Lap",
            "Session Ct": "Session_Ct",
        })
        df = df.dropna(subset=["mm_dd", "time_str", "SmO2_live"])
        datetime_str = "2025-" + df["mm_dd"].astype(str).str.strip() + " " + df["time_str"].astype(str).str.strip()
        df["datetime_raw"] = pd.to_datetime(datetime_str, format="%Y-%m-%d %H:%M:%S")
        df["datetime_raw"] = df["datetime_raw"].dt.tz_localize("Asia/Seoul")
        for col in ("SmO2_live", "SmO2_avg", "THb"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["SmO2_live"]).reset_index(drop=True)
        return df[["datetime_raw", "SmO2_live", "SmO2_avg", "THb", "Lap", "Session_Ct"]]
    raise ValueError(f"지원하지 않는 확장자: {path.suffix}")


def result_to_row(r: MetricsResult) -> dict:
    skip = {"anchors_abs", "min_time", "peak_time"}
    row = {k: v for k, v in asdict(r).items() if k not in skip}
    # anchors_abs 요약 컬럼
    row["start"] = r.anchors_abs["s"].strftime("%H:%M:%S")
    row["inflate"] = r.anchors_abs["i"].strftime("%H:%M:%S")
    row["deflate"] = r.anchors_abs["d"].strftime("%H:%M:%S")
    row["end"] = r.anchors_abs["e"].strftime("%H:%M:%S")
    return row


def analyze_file(
    path: Path,
    condition: str,
    out_dir: Path,
    sessions: list[str] | None = None,
) -> list[MetricsResult]:
    """한 파일에서 지정 세션들(기본: 전체)을 분석."""
    if sessions is None:
        sessions = SESSIONS
    print(f"\n▶ 파일: {path.name}  (condition={condition})")
    raw = _load_any(path)
    sm = preprocess(raw)
    print(f"  rows {len(raw)} → {len(sm)} | 샘플링 {sm.attrs['sampling_interval_sec']:.3f}s"
          f" | window {sm.attrs['smooth_window_samples']}")

    results: list[MetricsResult] = []
    for sess in sessions:
        anchor = get_anchors(condition, sess)
        try:
            r = compute_metrics(sm, anchor, condition, sess)
        except ValueError as exc:
            print(f"  [!] {sess}: {exc}")
            continue
        results.append(r)

        print(f"\n── {condition} / {sess} ──")
        print(r.as_table().to_string(index=False))

        out_dir.mkdir(parents=True, exist_ok=True)
        png = out_dir / f"{condition}_{sess}.png"
        plot_session(sm, r, save_path=png)
        print(f"  saved: {png}")

        csv_path = out_dir / f"{condition}_{sess}.csv"
        r.as_table().to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"  saved: {csv_path}")

    return results


def write_summary(results: list[MetricsResult], out_dir: Path) -> Path:
    df = pd.DataFrame([result_to_row(r) for r in results])
    path = out_dir / "summary.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\n✅ 전체 요약 저장: {path}")
    return path


def cmd_single(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    results = analyze_file(Path(args.file), args.condition, out_dir, args.sessions)
    write_summary(results, out_dir)
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out)
    all_results: list[MetricsResult] = []
    for cond in CONDITIONS:
        try:
            path = default_file_path(data_dir, cond)
        except FileNotFoundError as exc:
            print(f"[!] {cond}: {exc}")
            continue
        all_results.extend(analyze_file(path, cond, out_dir))
    if all_results:
        write_summary(all_results, out_dir)
    return 0 if all_results else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nirs_vot",
        description="NIRS-VOT 분석 CLI (Kubios 스타일 탭 기반 분석의 첫 엔진)",
    )
    p.add_argument("--out", default="docs/결과-results",
                   help="결과 저장 디렉토리 (기본: docs/결과-results)")
    sub = p.add_subparsers(dest="mode")

    sp = sub.add_parser("single", help="파일 하나 분석")
    sp.add_argument("--file", required=True, help="Calf.txt/xlsx 경로")
    sp.add_argument("--condition", required=True, choices=CONDITIONS)
    sp.add_argument("--sessions", nargs="+", choices=SESSIONS, default=None,
                    help="지정하지 않으면 Baseline + Recovery2 전체")
    sp.set_defaults(func=cmd_single)

    ap = sub.add_parser("all", help="3조건 × 2세션 전부 실행")
    ap.add_argument("--data-dir", default="참고자료/NIRS_VOT(SmO2) 데이터")
    ap.set_defaults(func=cmd_all)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "mode", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
