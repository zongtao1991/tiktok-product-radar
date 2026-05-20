"""生成 Demo 样本数据（模拟 FastMoss 导出格式）+ 日级时序数据"""
import csv, random, os, json, sys
from datetime import datetime, timedelta
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

random.seed(42)

CATEGORIES = {
    "beauty_skincare": {       # 美妆护肤 - 衰退期（过度饱和）+ 高退款率
        "n": 50, "follower_range": (50000, 5000000),
        "price_range": (8, 45), "gmv_range": (5000, 200000),
        "video_range": (15, 60), "concentration": "high",
        "trend": "declining",       # 月增长 -8%~-18%
        "refund_rate_range": (15, 35),  # 平均退款率高，用于测试惩罚
    },
    "kitchen_gadgets": {       # 厨房小工具 - 巅峰期
        "n": 50, "follower_range": (10000, 800000),
        "price_range": (12, 60), "gmv_range": (2000, 80000),
        "video_range": (8, 35), "concentration": "medium",
        "trend": "peak",            # 月增长 ±3%
        "refund_rate_range": (5, 12),  # 退款率正常
    },
    "pet_accessories": {       # 宠物用品 - 上升期（蓝海扩张）
        "n": 50, "follower_range": (5000, 300000),
        "price_range": (15, 80), "gmv_range": (500, 30000),
        "video_range": (3, 18), "concentration": "low",
        "trend": "rising",          # 月增长 +12%~+25%
        "refund_rate_range": (3, 10),  # 退款率低
    },
    "phone_cases": {           # 手机壳 - 衰退期（极度内卷）+ 高退款率
        "n": 50, "follower_range": (80000, 8000000),
        "price_range": (5, 20), "gmv_range": (8000, 500000),
        "video_range": (20, 80), "concentration": "very_high",
        "trend": "declining",       # 月增长 -10%~-20%
        "refund_rate_range": (18, 28),  # 退款率高，边界测试
    },
    "home_decor": {            # 家居装饰 - 上升期
        "n": 50, "follower_range": (8000, 600000),
        "price_range": (20, 120), "gmv_range": (1000, 60000),
        "video_range": (5, 25), "concentration": "medium_low",
        "trend": "rising",          # 月增长 +8%~+15%
        "refund_rate_range": (8, 18),  # 退款率中等，部分接近阈值
    },
}

# 时序趋势配置：基准日均 → 每日乘数曲线
TREND_CURVES = {
    "rising": {
        # 60天前=0.6x → 今天=1.2x, 近7天加速
        "base_mult_start": 0.6,
        "base_mult_end":   1.2,
        "week_boost":      1.08,   # 近7天再 ×1.08
        "noise":           0.15,
    },
    "peak": {
        # 平稳波动
        "base_mult_start": 0.95,
        "base_mult_end":   1.0,
        "week_boost":      1.0,
        "noise":           0.18,
    },
    "declining": {
        # 60天前=1.3x → 今天=0.7x, 近7天继续下滑
        "base_mult_start": 1.3,
        "base_mult_end":   0.75,
        "week_boost":      0.93,
        "noise":           0.2,
    },
    "dormant": {
        "base_mult_start": 0.8,
        "base_mult_end":   0.2,
        "week_boost":      0.85,
        "noise":           0.3,
    },
}

DAYS = 60  # 时序天数


def gen_entry_date(concentration: str) -> str:
    """老玩家越多 = 越早入场"""
    days_map = {
        "very_high": (180, 720),
        "high": (90, 540),
        "medium": (30, 360),
        "medium_low": (20, 180),
        "low": (7, 90),
    }
    lo, hi = days_map[concentration]
    delta = random.randint(lo, hi)
    return (datetime.today() - timedelta(days=delta)).strftime("%Y-%m-%d")


def gen_daily_series(base_daily: float, trend: str) -> list:
    """
    生成60天日级时序: [{date, video_count}, ...]
    base_daily = 该达人30天视频数 / 30
    """
    curve = TREND_CURVES[trend]
    series = []
    today = datetime.today().date()

    for day_offset in range(DAYS):
        # day 0 = 60天前, day 59 = 今天
        t = day_offset / (DAYS - 1)  # 0→1 线性插值
        mult = curve["base_mult_start"] + (curve["base_mult_end"] - curve["base_mult_start"]) * t

        # 近7天额外 boost
        if day_offset >= DAYS - 7:
            mult *= curve["week_boost"]

        # 周末略高
        d = today - timedelta(days=DAYS - 1 - day_offset)
        if d.weekday() >= 5:
            mult *= 1.12

        # 随机噪声
        noise = 1.0 + random.uniform(-curve["noise"], curve["noise"])
        count = max(0, round(base_daily * mult * noise))

        series.append({
            "date": d.isoformat(),
            "video_count": count,
        })
    return series


out_dir = os.path.dirname(__file__)

for cat, cfg in CATEGORIES.items():
    rows = []
    all_series = []  # 类目级聚合时序
    flo, fhi = cfg["follower_range"]
    plo, phi = cfg["price_range"]
    glo, ghi = cfg["gmv_range"]
    vlo, vhi = cfg["video_range"]
    trend_type = cfg["trend"]

    for i in range(cfg["n"]):
        followers = random.randint(flo, fhi)
        avg_views = followers * random.uniform(0.03, 0.25)
        eng_rate = random.uniform(0.01, 0.08)
        avg_likes = avg_views * eng_rate
        avg_comments = avg_likes * random.uniform(0.02, 0.1)
        avg_shares = avg_likes * random.uniform(0.05, 0.2)
        price = round(random.uniform(plo, phi), 2)
        commission = round(random.uniform(5, 30), 1)
        gmv = random.randint(glo, ghi)
        videos = random.randint(vlo, vhi)

        rflo, rfhi = cfg.get("refund_rate_range", (5, 15))
        refund_rate = round(random.uniform(rflo, rfhi), 1)

        rows.append({
            "username": f"creator_{cat[:4]}_{i+1:03d}",
            "followers": followers,
            "avg_views": round(avg_views),
            "avg_likes": round(avg_likes),
            "avg_comments": round(avg_comments),
            "avg_shares": round(avg_shares),
            "video_count": videos,
            "avg_price": price,
            "commission_rate": commission,
            "gmv_monthly": gmv,
            "entry_date": gen_entry_date(cfg["concentration"]),
            "refund_rate": refund_rate,
        })

        # 每个达人的日级时序
        base_daily = videos / 30.0
        creator_series = gen_daily_series(base_daily, trend_type)
        all_series.append(creator_series)

    # 写达人 CSV (不变)
    filepath = os.path.join(out_dir, f"{cat}.csv")
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    # 聚合类目级日时序 → {cat}_trend.csv
    # 所有达人按日聚合: date, video_count(全类目当日总量)
    agg = {}
    for creator_series in all_series:
        for point in creator_series:
            d = point["date"]
            agg[d] = agg.get(d, 0) + point["video_count"]

    trend_rows = [{"date": d, "video_count": v} for d, v in sorted(agg.items())]
    trend_path = os.path.join(out_dir, f"{cat}_trend.csv")
    with open(trend_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "video_count"])
        writer.writeheader()
        writer.writerows(trend_rows)

    msg = f"OK: {cat}.csv  ({cfg['n']} creators) + {cat}_trend.csv  ({len(trend_rows)} days, {trend_type})"
    try:
        print("✅ " + msg)
    except UnicodeEncodeError:
        print("[OK] " + msg)

print("\n样本数据生成完毕！")
