"""
爆款饱和度评分引擎
5 维指标 + 增长趋势 → 加权饱和度总分 → 蓝海评级
"""
import math
import statistics
from typing import List, Optional

import pandas as pd

from models import Creator, CategoryAnalysis, OceanLevel
from trend import analyze_trend, TrendAnalysis
from config import get_config

# ── 权重配置（可调） ──────────────────────────────────────────────────
# 说明：已移除 engagement_decay 和 price_competition 两个维度
# 原因：FastMoss API 不提供 avg_views, avg_likes, avg_price 等字段
WEIGHTS = {
    "concentration":   0.40,  # 达人集中度（头部垄断风险）- 最重要
    "content_density": 0.35,  # 内容密度（供给侧过剩）- 第二重要
    "barrier":         0.25,  # 入门门槛（新人生存难度）- 第三重要
}

# 内容密度基准：月视频数超过此值认为极度饱和
CONTENT_DENSITY_SATURATION = 2000   # 50人×40条


def _normalize(value: float, lo: float, hi: float) -> float:
    """线性归一化到 [0, 1]，超出则截断"""
    if hi == lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _hhi(shares: List[float]) -> float:
    """
    Herfindahl-Hirschman Index（市场集中度）
    shares: 各玩家 GMV 份额列表（已归一化为百分比，0~1）
    返回 [0, 1]，越大越垄断
    """
    total = sum(shares)
    if total == 0:
        return 0.0
    normalized = [s / total for s in shares]
    return sum(x ** 2 for x in normalized)


def score_category(df: pd.DataFrame, category: str,
                    trend_df: Optional[pd.DataFrame] = None) -> CategoryAnalysis:
    """对单个类目 DataFrame 进行饱和度建模，可选时序趋势数据"""

    creators: List[Creator] = []
    for _, row in df.iterrows():
        creators.append(Creator(
            username=str(row["username"]),
            followers=int(row["followers"]),
            avg_views=float(row["avg_views"]),
            avg_likes=float(row["avg_likes"]),
            avg_comments=float(row["avg_comments"]),
            avg_shares=float(row["avg_shares"]),
            video_count=int(row["video_count"]),
            avg_price=float(row["avg_price"]),
            commission_rate=float(row["commission_rate"]),
            gmv_monthly=float(row["gmv_monthly"]),
            entry_date=str(row["entry_date"]),
            refund_rate=float(row.get("refund_rate", 0.0)),
        ))

    n = len(creators)

    # ── 维度 1：达人集中度（HHI）────────────────────────────────────
    gmvs = [c.gmv_monthly for c in creators]
    hhi_raw = _hhi(gmvs)
    # HHI 理论范围 [1/n, 1]，归一化到 [0, 1]
    hhi_min = 1 / n
    concentration_norm = _normalize(hhi_raw, hhi_min, 1.0)

    # ── 维度 2：内容密度（近30天视频总量）──────────────────────────
    total_videos = sum(c.video_count for c in creators)
    density_norm = _normalize(total_videos, 0, CONTENT_DENSITY_SATURATION)

    # ── 维度 3：入门门槛（粉丝中位数）──────────────────────────────
    # 说明：已移除 engagement_decay 和 price_competition 两个维度
    # 原因：FastMoss API 不提供 avg_views, avg_likes, avg_price 等字段
    follower_list = sorted(c.followers for c in creators)
    median_followers = statistics.median(follower_list)
    # 对数归一化：中位数粉丝 5k→低门槛，500k→高门槛
    log_med = math.log10(max(1, median_followers))
    barrier_norm = _normalize(log_med, math.log10(5000), math.log10(500000))

    # ── 加权饱和度总分（0~100）──────────────────────────────────────
    # 说明：仅使用 3 个维度（concentration, content_density, barrier）
    saturation = (
        concentration_norm  * WEIGHTS["concentration"] +
        density_norm        * WEIGHTS["content_density"] +
        barrier_norm        * WEIGHTS["barrier"]
    ) * 100

    saturation = round(saturation, 1)

    # ── 退款率惩罚逻辑 ──────────────────────────────────────────────
    config = get_config()
    refund_config = config.refund_rate

    avg_refund_rate = 0.0
    refund_penalty_applied = False
    refund_penalty = 0.0

    if n > 0:
        avg_refund_rate = statistics.mean(c.refund_rate for c in creators)
        avg_refund_rate = round(avg_refund_rate, 2)

    if refund_config.enabled and avg_refund_rate > refund_config.threshold:
        refund_penalty = refund_config.penalty_score
        saturation = round(saturation + refund_penalty, 1)
        refund_penalty_applied = True

    blue_ocean = round(100 - saturation, 1)

    # ── 等级划定 ────────────────────────────────────────────────────
    if blue_ocean >= 60:
        level = OceanLevel.BLUE_OCEAN
    elif blue_ocean >= 40:
        level = OceanLevel.SHALLOW
    elif blue_ocean >= 20:
        level = OceanLevel.RED_OCEAN
    else:
        level = OceanLevel.BLOODY

    # ── 推荐文案 ────────────────────────────────────────────────────
    rec_map = {
        OceanLevel.BLUE_OCEAN: "供给稀缺，需求未被满足，建议优先入局",
        OceanLevel.SHALLOW:    "竞争适中，差异化切入有机会，需测款",
        OceanLevel.RED_OCEAN:  "头部效应明显，需强 IP 或低价策略突围",
        OceanLevel.BLOODY:     "极度内卷，利润薄，非强势供应链不建议",
    }

    top_creators = sorted(creators, key=lambda c: c.gmv_monthly, reverse=True)[:5]

    # ── 趋势分析（可选）──────────────────────────────────────────
    trend_phase = None
    trend_score = None
    daily_growth = None
    monthly_growth = None
    trend_momentum = None
    trend_peak_date = None
    trend_peak_volume = None
    trend_daily_avg = None

    if trend_df is not None and len(trend_df) >= 7:
        ta = analyze_trend(trend_df)
        trend_phase = ta.phase.value
        trend_score = ta.trend_score
        daily_growth = ta.daily_growth_rate
        monthly_growth = ta.monthly_growth_rate
        trend_momentum = ta.momentum
        trend_peak_date = ta.peak_date
        trend_peak_volume = ta.peak_volume
        trend_daily_avg = ta.daily_avg_recent

        # 趋势修正推荐文案
        phase_hint = {
            "上升期": " | 📈 市场正在扩张，先发优势明显",
            "巅峰期": " | 📊 接近饱和稳态，留意拐点",
            "衰退期": " | 📉 市场收缩中，谨慎入场",
            "沉寂期": " | 💤 市场近乎沉寂，高风险",
        }
        rec_map = {k: v + phase_hint.get(trend_phase, "")
                   for k, v in rec_map.items()}

    if refund_penalty_applied:
        refund_hint = f" | ⚠️ 退款率{avg_refund_rate}%超标，饱和度+{refund_penalty}分"
        rec_map = {k: v + refund_hint for k, v in rec_map.items()}

    return CategoryAnalysis(
        category=category,
        creator_count=n,
        concentration_score=round(concentration_norm * 100, 1),
        content_density_score=round(density_norm * 100, 1),
        engagement_decay_score=0.0,
        price_competition_score=0.0,
        barrier_score=round(barrier_norm * 100, 1),
        saturation_score=saturation,
        blue_ocean_score=blue_ocean,
        ocean_level=level,
        trend_phase=trend_phase,
        trend_score=trend_score,
        daily_growth_rate=daily_growth,
        monthly_growth_rate=monthly_growth,
        trend_momentum=trend_momentum,
        trend_peak_date=trend_peak_date,
        trend_peak_volume=trend_peak_volume,
        trend_daily_avg=trend_daily_avg,
        top_creators=top_creators,
        avg_price=0.0,
        price_cv=0.0,
        entry_barrier_followers=int(median_followers),
        recommendation=rec_map[level],
        avg_refund_rate=avg_refund_rate,
        refund_rate_penalty_applied=refund_penalty_applied,
        refund_rate_penalty=refund_penalty,
    )
