"""CSV 数据加载器，兼容 FastMoss / Kalodata 导出格式"""
import os
import sys
from pathlib import Path
from typing import Dict
import pandas as pd

# 字段别名映射（外部平台列名 → 内部标准列名）
COLUMN_ALIASES = {
    # FastMoss 风格
    "Influencer": "username",
    "Followers": "followers",
    "Avg Views": "avg_views",
    "Avg Likes": "avg_likes",
    "Avg Comments": "avg_comments",
    "Avg Shares": "avg_shares",
    "Videos (30d)": "video_count",
    "Avg Price (USD)": "avg_price",
    "Commission Rate": "commission_rate",
    "Est. GMV (30d)": "gmv_monthly",
    "First Video Date": "entry_date",
    "Refund Rate": "refund_rate",
    "Refund Rate (%)": "refund_rate",
    # Kalodata 风格
    "creator_name": "username",
    "fan_count": "followers",
    "video_avg_play": "avg_views",
    "video_avg_like": "avg_likes",
    "video_avg_comment": "avg_comments",
    "video_avg_share": "avg_shares",
    "video_count_30d": "video_count",
    "product_avg_price": "avg_price",
    "commission_pct": "commission_rate",
    "gmv_30d": "gmv_monthly",
    "earliest_video_date": "entry_date",
    "refund_rate": "refund_rate",
    "refund_rate_pct": "refund_rate",
}

REQUIRED_COLUMNS = [
    "username", "followers", "avg_views", "avg_likes",
    "avg_comments", "avg_shares", "video_count",
    "avg_price", "commission_rate", "gmv_monthly", "entry_date",
]


def _clean_numeric(series: pd.Series) -> pd.Series:
    """去除 $ % , 等符号，转为数值"""
    return (
        series.astype(str)
        .str.replace(r"[$,%K万]", "", regex=True)
        .str.strip()
        .apply(lambda x: float(x) * 1000 if x.endswith("K") else
               float(x) * 10000 if x.endswith("万") else
               float(x) if x not in ("", "nan", "None") else 0.0)
    )


def load_csv(filepath: str) -> pd.DataFrame:
    """加载单个 CSV 文件，自动处理列别名和数据清洗"""
    df = pd.read_csv(filepath)
    df.rename(columns=COLUMN_ALIASES, inplace=True)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"缺少必需列: {missing}（文件: {filepath}）")

    for col in ["followers", "avg_views", "avg_likes", "avg_comments",
                "avg_shares", "video_count", "avg_price",
                "commission_rate", "gmv_monthly"]:
        try:
            df[col] = _clean_numeric(df[col])
        except Exception:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "refund_rate" in df.columns:
        try:
            df["refund_rate"] = _clean_numeric(df["refund_rate"])
        except Exception:
            df["refund_rate"] = pd.to_numeric(df["refund_rate"], errors="coerce").fillna(0.0)
    else:
        df["refund_rate"] = 0.0

    df["entry_date"] = df["entry_date"].astype(str)
    df = df.dropna(subset=["username"])
    return df


def load_trend_csv(filepath: str) -> pd.DataFrame:
    """加载时序趋势 CSV (date, video_count)"""
    df = pd.read_csv(filepath)
    if "date" not in df.columns or "video_count" not in df.columns:
        raise ValueError(f"趋势 CSV 缺少 date/video_count 列: {filepath}")
    df["date"] = pd.to_datetime(df["date"])
    df["video_count"] = pd.to_numeric(df["video_count"], errors="coerce").fillna(0)
    return df.sort_values("date").reset_index(drop=True)


def load_directory(data_dir: str) -> Dict[str, pd.DataFrame]:
    """扫描目录，加载所有 CSV，文件名作为类目名（跳过 _trend.csv）"""
    result: Dict[str, pd.DataFrame] = {}
    for path in sorted(Path(data_dir).glob("*.csv")):
        if path.name.startswith("_") or path.name == "gen_sample.py":
            continue
        if path.name.endswith("_trend.csv"):
            continue   # 趋势文件单独加载
        try:
            df = load_csv(str(path))
            category = path.stem
            result[category] = df
            print(f"  ✅ {path.name}  ({len(df)} 条)", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠️  {path.name} 加载失败: {e}", file=sys.stderr)
    return result


def load_trend_directory(data_dir: str) -> Dict[str, pd.DataFrame]:
    """扫描目录中的 *_trend.csv，类目名=去掉 _trend 后缀"""
    result: Dict[str, pd.DataFrame] = {}
    for path in sorted(Path(data_dir).glob("*_trend.csv")):
        try:
            df = load_trend_csv(str(path))
            category = path.stem.replace("_trend", "")
            result[category] = df
            print(f"  📈 {path.name}  ({len(df)} 天)", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠️  {path.name} 趋势加载失败: {e}", file=sys.stderr)
    return result
