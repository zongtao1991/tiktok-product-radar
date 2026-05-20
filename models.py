"""数据模型定义"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class OceanLevel(Enum):
    """蓝海等级"""
    BLUE_OCEAN = "蓝海"       # 60-100: 竞争低，值得入局
    SHALLOW = "浅水"          # 40-59:  中等竞争，谨慎入局
    RED_OCEAN = "红海"        # 20-39:  高竞争，需差异化
    BLOODY = "血海"           # 0-19:   极度饱和，不建议


@dataclass
class Creator:
    """单个达人数据"""
    username: str
    followers: int
    avg_views: float
    avg_likes: float
    avg_comments: float
    avg_shares: float
    video_count: int          # 类目视频数量（近30天）
    avg_price: float          # 主推商品均价（USD）
    commission_rate: float    # 平均佣金率（%）
    gmv_monthly: float        # 月 GMV 估算（USD）
    entry_date: str           # 最早发布该类目的日期 YYYY-MM-DD
    refund_rate: float = 0.0  # 退款率（%），可选字段


@dataclass
class CategoryAnalysis:
    """类目竞争度分析结果"""
    category: str
    creator_count: int

    # 5 维原始指标
    concentration_score: float    # 达人集中度（HHI 指数，越高越集中）
    content_density_score: float  # 内容密度（近30天视频总量饱和度）
    engagement_decay_score: float # 互动衰减（头部 vs 腰部互动率差）
    price_competition_score: float# 价格内卷（价格标准差/均值）
    barrier_score: float          # 入门门槛（粉丝中位数对数归一化）

    # 最终得分
    saturation_score: float       # 饱和度总分（0-100，越高越饱和）
    blue_ocean_score: float       # 蓝海分 = 100 - saturation
    ocean_level: OceanLevel

    # 增长趋势（可选，有时序数据时填充）
    trend_phase: Optional[str] = None          # 上升期/巅峰期/衰退期/沉寂期
    trend_score: Optional[float] = None        # 趋势得分 0~100
    daily_growth_rate: Optional[float] = None  # 周环比增长率 %
    monthly_growth_rate: Optional[float] = None # 月环比增长率 %
    trend_momentum: Optional[float] = None     # 动量 -100~+100
    trend_peak_date: Optional[str] = None      # 峰值日期
    trend_peak_volume: Optional[float] = None  # 峰值日视频数
    trend_daily_avg: Optional[float] = None    # 近7天日均

    # 附加洞察
    top_creators: list = field(default_factory=list)
    avg_price: float = 0.0
    price_cv: float = 0.0        # 价格变异系数（内卷程度）
    entry_barrier_followers: int = 0  # 进入门槛粉丝数（中位数）
    recommendation: str = ""

    # 退款率惩罚相关
    avg_refund_rate: float = 0.0       # 类目平均退款率（%）
    refund_rate_penalty_applied: bool = False  # 是否应用了退款率惩罚
    refund_rate_penalty: float = 0.0    # 实际应用的惩罚分数
