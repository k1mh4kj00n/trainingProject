"""디자인 토큰 — 색·타이포·간격·반경 단일 출처.

v2 의료/연구 톤 (2026-05-10 리디자인):
- 기본 테마 = **Light** (의료·연구 소프트웨어 표준)
- 주 색 = **의료 블루** #0284C7 (병원/임상 신뢰감)
- 시맨틱 색 = 임상 의미 기반 (정상=녹색 / 주의=황색 / 위급=적색)
- 배경 = 거의 흰색 + 미세 음영 (Prism / JMP / MATLAB / Stripe Dashboard 영감)

다크 테마는 옵션으로 보존 (장시간 분석 시 / 야간 / 사용자 선호).

사용:
    from v2.theme.tokens import COLOR, SPACE, FONT, RADIUS
    label.setStyleSheet(f"color: {COLOR.text_0}; padding: {SPACE.md}px;")
"""

from __future__ import annotations

from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────
#  색 — Light 기본 (GraphPad Prism / JMP / MATLAB / Stripe 영감)
# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class _Palette:
    # 배경 — 단계적
    bg_0: str        # 페이지 가장 깊은 배경
    bg_1: str        # 카드 배경
    bg_2: str        # 카드 hover
    bg_3: str        # nav active / 선택
    # 라인
    border: str
    border_strong: str
    # 텍스트
    text_0: str      # 제목·KPI 큰 값
    text_1: str      # 본문
    text_2: str      # muted / legend / placeholder
    # 의미색
    accent: str      # primary (의료 블루)
    accent_2: str    # secondary (teal)
    warn: str        # 주의 (amber)
    error: str       # 위급/이상 (red)
    success: str     # 정상 (green)
    # 임상 의미 색 — 강조 박스/뱃지 용
    clinical_normal: str   # 정상 범위
    clinical_warning: str  # 경계 / 주의 관찰
    clinical_critical: str # 즉각 조치
    # 데이터 시각화 팔레트 — 의료 차트 표준 (구분 명확 + 색맹 친화)
    data: tuple[str, ...]


# Light — 기본 (의료·연구실 표준)
COLOR_LIGHT = _Palette(
    bg_0="#F7F9FB",        # 페이지 (아주 옅은 cool gray)
    bg_1="#FFFFFF",        # 카드 (순백)
    bg_2="#F1F5F9",        # hover
    bg_3="#E2E8F0",        # 선택
    border="#E5E7EB",
    border_strong="#CBD5E1",
    text_0="#0F172A",      # 진한 slate (가독성 최우선)
    text_1="#475569",
    text_2="#94A3B8",
    accent="#0284C7",      # 의료 블루 (sky-600)
    accent_2="#14B8A6",    # teal (보조 강조)
    warn="#D97706",        # amber-600
    error="#DC2626",       # red-600
    success="#16A34A",     # green-600
    clinical_normal="#16A34A",
    clinical_warning="#D97706",
    clinical_critical="#DC2626",
    data=(
        "#0284C7",  # blue   — 1차 색 (Baseline / 정상)
        "#14B8A6",  # teal
        "#7C3AED",  # violet
        "#EA580C",  # orange
        "#DB2777",  # pink
        "#65A30D",  # lime green
        "#0891B2",  # cyan
        "#CA8A04",  # yellow-600
        "#059669",  # emerald
        "#9333EA",  # purple
    ),
)


# Dark — 옵션 (야간/장시간 분석)
COLOR_DARK = _Palette(
    bg_0="#0F172A",
    bg_1="#1E293B",
    bg_2="#293548",
    bg_3="#334155",
    border="#334155",
    border_strong="#475569",
    text_0="#F1F5F9",
    text_1="#CBD5E1",
    text_2="#94A3B8",
    accent="#38BDF8",       # 다크 모드의 의료 블루는 한 톤 밝게
    accent_2="#5EEAD4",
    warn="#FBBF24",
    error="#F87171",
    success="#4ADE80",
    clinical_normal="#4ADE80",
    clinical_warning="#FBBF24",
    clinical_critical="#F87171",
    data=(
        "#38BDF8", "#5EEAD4", "#A78BFA", "#FB923C", "#F472B6",
        "#A3E635", "#67E8F9", "#FCD34D", "#34D399", "#C084FC",
    ),
)

# 기본은 Light (의료/연구 톤) — set_theme(...) 으로 런타임 전환
COLOR: _Palette = COLOR_LIGHT


def set_theme(mode: str) -> None:
    """'light' (기본) / 'dark' 로 색 팔레트 전환. 호출 후 위젯 재렌더 필요."""
    global COLOR
    if mode == "dark":
        COLOR = COLOR_DARK
    else:
        COLOR = COLOR_LIGHT


# ─────────────────────────────────────────────────────────────
#  간격 — 4 step grid (의료 SW 는 약간 여유있게 — Prism / Stripe 영감)
# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class _Space:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32
    xxxl: int = 48
    # 컴포넌트 별 권장
    card_padding: int = 18      # 라이트 + 의료톤 → 약간 여유
    card_gap: int = 12
    grid_gap: int = 12
    nav_padding_v: int = 8
    nav_padding_h: int = 12


SPACE = _Space()


# ─────────────────────────────────────────────────────────────
#  타이포 — 임상/연구 가독성 우선 (조금 더 큼)
# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class _Font:
    # family fallback (한국어 임상 차트는 Pretendard 가 가장 잘 맞음)
    family_ui: str = "'Pretendard', 'Inter', 'Segoe UI', 'Malgun Gothic', system-ui, sans-serif"
    family_mono: str = "'JetBrains Mono', 'D2Coding', Consolas, 'Courier New', monospace"

    # 사이즈 (px) — 임상 데이터 가독성 위해 조금 더 큼
    kpi_value: int = 26       # KPI 큰 값 (의료 데이터는 또렷이)
    kpi_value_lg: int = 34    # 헤로 KPI
    title: int = 14           # 카드 제목 (조금 더 큼)
    title_lg: int = 18        # 페이지 제목
    body: int = 14            # 본문
    ui: int = 13              # UI 라벨
    caption: int = 12         # 캡션·muted
    micro: int = 11           # 차트 축 라벨

    # weight
    w_regular: int = 400
    w_medium: int = 500
    w_semibold: int = 600
    w_bold: int = 700


FONT = _Font()


# ─────────────────────────────────────────────────────────────
#  반경·shadow
# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class _Radius:
    sm: int = 4
    md: int = 6
    lg: int = 8
    xl: int = 12
    pill: int = 9999


RADIUS = _Radius()


@dataclass(frozen=True)
class _Shadow:
    # Light 톤 — 미세한 elevation (Stripe / Linear light 영감)
    none: str = "none"
    card_subtle: tuple = (0, 1, 3, "rgba(15, 23, 42, 0.06)")  # x, y, blur, color
    hover: tuple = (0, 2, 6, "rgba(15, 23, 42, 0.10)")
    modal: tuple = (0, 12, 32, "rgba(15, 23, 42, 0.15)")


SHADOW = _Shadow()


# ─────────────────────────────────────────────────────────────
#  대시보드 그리드
# ─────────────────────────────────────────────────────────────
GRID_COLUMNS = 12        # 메인 대시보드 컬럼 수
GRID_ROW_HEIGHT = 88     # 한 row 단위 높이 (px) — 라이트 톤은 약간 여유
