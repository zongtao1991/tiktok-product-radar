"""
视频增长趋势分析模块
日级(7天)和月级(30天)双周期，判定类目生命周期阶段

指标:
  - 日级: 近7天日均 vs 前7天日均 → 周环比增长率
  - 月级: 近30天总量 vs 前30天总量 → 月环比增长率
  - 动量: 综合方向和加速度
  - 阶段: 上升期 / 巅峰期 / 衰退期 / 沉寂期
"""
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd


class GrowthPhase(Enum):
    """增长阶段"""
    RISING   = "上升期"    # 月>+5% 且 周>0  — 市场扩张
    PEAK     = "巅峰期"    # 月±5% 之间      — 即将见顶或稳态
    DECLINING = "衰退期"   # 月<-5%           — 市场收缩
    DORMANT  = "沉寂期"    # 日均极低+持续负增长 — 几乎无人做


# ── 阶段图标 / 颜色 ───────────────────────────────────────────────────
PHASE_ICONS = {
    GrowthPhase.RISING:    "📈",
    GrowthPhase.PEAK:      "📊",
    GrowthPhase.DECLINING: "📉",
    GrowthPhase.DORMANT:   "💤",
}

PHASE_COLORS = {
    GrowthPhase.RISING:    "green",
    GrowthPhase.PEAK:      "cyan",
    GrowthPhase.DECLINING: "yellow",
    GrowthPhase.DORMANT:   "red",
}


@dataclass
class TrendAnalysis:
    """增长趋势分析结果"""
    # 日级 (7天周期)
    daily_avg_recent: float         # 近7天日均视频数
    daily_avg_prev: float           # 前7天日均视频数
    daily_growth_rate: float        # 周环比增长率 (%)

    # 月级 (30天周期)
    monthly_total_recent: float     # 近30天视频总量
    monthly_total_prev: float       # 前30天视频总量
    monthly_growth_rate: float      # 月环比增长率 (%)

    # 综合判定
    phase: GrowthPhase
    momentum: float                 # 动量 (-100~+100)
    trend_score: float              # 趋势得分 (0~100, 高=强势上升)

    # 辅助
    data_days: int                  # 数据天数
    peak_date: Optional[str]        # 峰值日期
    peak_volume: float              # 峰值日视频数


def analyze_trend(df: pd.DataFrame) -> TrendAnalysis:
    """
    对类目时序 DataFrame 进行增长趋势分析。
    df 需包含 date(datetime), video_count 列，建议 ≥60 天。
    """
    df = df.sort_values("date").reset_index(drop=True)
    n = len(df)
    vc = df["video_count"].values

    # ── 日级 (7天) ─────────────────────────────────────────────
    last_7 = vc[-7:]   if n >= 7  else vc
    prev_7 = vc[-14:-7] if n >= 14 else last_7

    daily_avg_recent = float(last_7.mean())
    daily_avg_prev   = float(prev_7.mean())
    daily_rate = _pct(daily_avg_recent, daily_avg_prev)

    # 周加速度 (本周增长率 - 上周增长率)
    if n >= 21:
        prev_prev_7 = vc[-21:-14]
        prev_prev_avg = float(prev_prev_7.mean())
        prev_rate = _pct(daily_avg_prev, prev_prev_avg)
        acceleration = daily_rate - prev_rate
    else:
        acceleration = 0.0

    # ── 月级 (30天) ────────────────────────────────────────────
    last_30 = vc[-30:]   if n >= 30 else vc
    prev_30 = vc[-60:-30] if n >= 60 else last_30

    monthly_total_recent = float(last_30.sum())
    monthly_total_prev   = float(prev_30.sum())
    monthly_rate = _pct(monthly_total_recent, monthly_total_prev)

    # ── 峰值 ──────────────────────────────────────────────────
    peak_idx = int(df["video_count"].idxmax())
    peak_date = df.loc[peak_idx, "date"]
    if hasattr(peak_date, "strftime"):
        peak_date = peak_date.strftime("%Y-%m-%d")
    else:
        peak_date = str(peak_date)[:10]
    peak_volume = float(df.loc[peak_idx, "video_count"])

    # ── 阶段判定 ──────────────────────────────────────────────
    phase = _determine_phase(monthly_rate, daily_rate, daily_avg_recent)

    # ── 动量 (-100 ~ +100) ───────────────────────────────────
    momentum = _clamp(
        monthly_rate * 0.5 + daily_rate * 0.3 + acceleration * 0.2,
        -100, 100
    )

    # ── 趋势得分 (0 ~ 100) ───────────────────────────────────
    trend_score = _calc_trend_score(monthly_rate, daily_rate, phase)

    return TrendAnalysis(
        daily_avg_recent=round(daily_avg_recent, 1),
        daily_avg_prev=round(daily_avg_prev, 1),
        daily_growth_rate=round(daily_rate, 1),
        monthly_total_recent=round(monthly_total_recent),
        monthly_total_prev=round(monthly_total_prev),
        monthly_growth_rate=round(monthly_rate, 1),
        phase=phase,
        momentum=round(momentum, 1),
        trend_score=round(trend_score, 1),
        data_days=n,
        peak_date=peak_date,
        peak_volume=round(peak_volume),
    )


# ── 内部工具 ─────────────────────────────────────────────────────────

def _pct(current: float, previous: float) -> float:
    """百分比变化"""
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _determine_phase(
    monthly_rate: float,
    daily_rate: float,
    daily_avg: float,
) -> GrowthPhase:
    """
    上升期:  月>+5%  且 日>0
    巅峰期:  月在 -5%~+5%
    衰退期:  月<-5%
    沉寂期:  日均<3 且 月<-15%
    """
    if daily_avg < 3 and monthly_rate < -15:
        return GrowthPhase.DORMANT
    if monthly_rate > 5 and daily_rate > 0:
        return GrowthPhase.RISING
    if monthly_rate < -5:
        return GrowthPhase.DECLINING
    return GrowthPhase.PEAK


def _calc_trend_score(
    monthly_rate: float,
    daily_rate: float,
    phase: GrowthPhase,
) -> float:
    """
    趋势得分 0~100。50=平稳, >50=上升, <50=下降。
    ±30% 月增长 映射到 ±40 分；日增长微调 ±10。
    """
    base = 50 + monthly_rate * (40 / 30)
    base += daily_rate * (10 / 20)

    bonus = {
        GrowthPhase.RISING: 5,
        GrowthPhase.PEAK: 0,
        GrowthPhase.DECLINING: -5,
        GrowthPhase.DORMANT: -10,
    }
    base += bonus[phase]

    return _clamp(base, 0, 100)
