"""
CLI 入口：命令行直接跑分析，输出 Rich 表格
用法：
  python main.py                          # 分析 sample_data/ 目录
  python main.py --dir /path/to/data      # 指定目录
  python main.py --file data.csv --cat 美妆  # 单文件
  python main.py --trend trend.csv        # 附加时序数据
  python main.py --json                   # 输出 JSON
  python main.py --web                    # 启动 Web 面板
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import print as rprint
    RICH = True
except ImportError:
    RICH = False

from loader import load_csv, load_directory, load_trend_csv, load_trend_directory
from scorer import score_category
from models import CategoryAnalysis, OceanLevel
from trend import GrowthPhase, PHASE_ICONS

console = Console() if RICH else None

LEVEL_COLORS = {
    OceanLevel.BLUE_OCEAN: "cyan",
    OceanLevel.SHALLOW:    "green",
    OceanLevel.RED_OCEAN:  "yellow",
    OceanLevel.BLOODY:     "red",
}

LEVEL_ICONS = {
    OceanLevel.BLUE_OCEAN: "🌊",
    OceanLevel.SHALLOW:    "🌿",
    OceanLevel.RED_OCEAN:  "🔥",
    OceanLevel.BLOODY:     "💀",
}

PHASE_ICON_MAP = {
    "上升期": "📈",
    "巅峰期": "📊",
    "衰退期": "📉",
    "沉寂期": "💤",
}

PHASE_COLOR_MAP = {
    "上升期": "green",
    "巅峰期": "cyan",
    "衰退期": "yellow",
    "沉寂期": "red",
}


def print_table(results: list[CategoryAnalysis]):
    if not RICH:
        for r in results:
            trend_str = f" {r.trend_phase}" if r.trend_phase else ""
            print(f"{r.category}: 蓝海分={r.blue_ocean_score} 等级={r.ocean_level.value}{trend_str}")
        return

    has_trend = any(r.trend_phase for r in results)

    table = Table(
        title="🎯 TikTok 选品竞争度分析",
        show_header=True, header_style="bold dim",
        border_style="dim", row_styles=["", "dim"],
        show_lines=False,
    )
    table.add_column("类目", style="bold", no_wrap=True)
    table.add_column("蓝海分", justify="right")
    table.add_column("等级", justify="center")
    if has_trend:
        table.add_column("趋势", justify="center")
        table.add_column("日增长", justify="right")
        table.add_column("月增长", justify="right")
    table.add_column("饱和度", justify="right")
    table.add_column("集中度", justify="right")
    table.add_column("密度", justify="right")
    table.add_column("衰减", justify="right")
    table.add_column("内卷", justify="right")
    table.add_column("门槛", justify="right")
    table.add_column("均价", justify="right")

    for r in sorted(results, key=lambda x: x.blue_ocean_score, reverse=True):
        color = LEVEL_COLORS[r.ocean_level]
        icon = LEVEL_ICONS[r.ocean_level]

        row = [
            r.category,
            f"[bold {color}]{r.blue_ocean_score}[/]",
            f"{icon} [{color}]{r.ocean_level.value}[/]",
        ]
        if has_trend:
            if r.trend_phase:
                picon = PHASE_ICON_MAP.get(r.trend_phase, "")
                pcolor = PHASE_COLOR_MAP.get(r.trend_phase, "dim")
                row.append(f"{picon} [{pcolor}]{r.trend_phase}[/]")
                # 日增长率
                dg = r.daily_growth_rate or 0
                dg_color = "green" if dg > 0 else "red" if dg < 0 else "dim"
                row.append(f"[{dg_color}]{dg:+.1f}%[/]")
                # 月增长率
                mg = r.monthly_growth_rate or 0
                mg_color = "green" if mg > 0 else "red" if mg < 0 else "dim"
                row.append(f"[{mg_color}]{mg:+.1f}%[/]")
            else:
                row.extend(["[dim]—[/]", "[dim]—[/]", "[dim]—[/]"])

        row.extend([
            str(r.saturation_score),
            str(r.concentration_score),
            str(r.content_density_score),
            str(r.engagement_decay_score),
            str(r.price_competition_score),
            str(r.barrier_score),
            f"${r.avg_price}",
        ])
        table.add_row(*row)

    console.print(table)

    # 蓝海类目详情
    blue = [r for r in results if r.ocean_level == OceanLevel.BLUE_OCEAN]
    if blue:
        console.print()
        lines = []
        for r in sorted(blue, key=lambda x: x.blue_ocean_score, reverse=True):
            trend_str = ""
            if r.trend_phase:
                picon = PHASE_ICON_MAP.get(r.trend_phase, "")
                trend_str = f"  {picon}{r.trend_phase}(月{r.monthly_growth_rate:+.1f}%)"
            lines.append(
                f"  [cyan]{r.category}[/]  蓝海分 [bold]{r.blue_ocean_score}[/]  "
                f"均价 ${r.avg_price}  入门粉丝 {r.entry_barrier_followers:,}{trend_str}"
            )
        console.print(Panel("\n".join(lines), title="🌊 蓝海机会", border_style="cyan"))

    # 趋势总览
    if has_trend:
        rising = [r for r in results if r.trend_phase == "上升期"]
        declining = [r for r in results if r.trend_phase in ("衰退期", "沉寂期")]
        console.print()
        lines = []
        if rising:
            lines.append("[green]📈 上升期:[/] " + ", ".join(
                f"[bold]{r.category}[/](月{r.monthly_growth_rate:+.1f}%)" for r in rising))
        if declining:
            lines.append("[yellow]📉 衰退期:[/] " + ", ".join(
                f"[bold]{r.category}[/](月{r.monthly_growth_rate:+.1f}%)" for r in declining))
        peak = [r for r in results if r.trend_phase == "巅峰期"]
        if peak:
            lines.append("[cyan]📊 巅峰期:[/] " + ", ".join(
                f"[bold]{r.category}[/](月{r.monthly_growth_rate:+.1f}%)" for r in peak))
        if lines:
            console.print(Panel("\n".join(lines), title="📊 增长趋势总览", border_style="dim"))


def main():
    parser = argparse.ArgumentParser(description="TikTok 选品竞争度建模")
    parser.add_argument("--dir",   default="sample_data", help="数据目录（默认 sample_data/）")
    parser.add_argument("--file",  default=None, help="单个 CSV 文件")
    parser.add_argument("--cat",   default=None, help="单文件时的类目名")
    parser.add_argument("--trend", default=None, help="单个趋势 CSV（配合 --file 使用）")
    parser.add_argument("--min-price", type=float, default=None, help="最低均价过滤（USD）")
    parser.add_argument("--max-price", type=float, default=None, help="最高均价过滤（USD）")
    parser.add_argument("--json",  action="store_true", help="输出 JSON")
    parser.add_argument("--web",   action="store_true", help="启动 Web 面板（端口 8765）")
    args = parser.parse_args()

    if args.web:
        import uvicorn
        from app import app
        print("🌐 Web 面板: http://localhost:8765")
        uvicorn.run(app, host="0.0.0.0", port=8765)
        return

    # 加载数据
    trend_data = {}
    if args.file:
        df = load_csv(args.file)
        cat = args.cat or Path(args.file).stem
        datasets = {cat: df}
        if args.trend:
            trend_data[cat] = load_trend_csv(args.trend)
    else:
        print(f"📂 扫描 {args.dir}/", file=sys.stderr)
        datasets = load_directory(args.dir)
        trend_data = load_trend_directory(args.dir)

    if not datasets:
        print("❌ 未找到任何数据，请先运行: python sample_data/gen_sample.py")
        sys.exit(1)

    results = []
    for cat, df in datasets.items():
        t_df = trend_data.get(cat)
        results.append(score_category(df, cat, trend_df=t_df))

    # 金额筛选
    if args.min_price is not None:
        before = len(results)
        results = [r for r in results if r.avg_price >= args.min_price]
        filtered = before - len(results)
        if filtered:
            print(f"  💰 均价 < ${args.min_price} 过滤掉 {filtered} 个类目", file=sys.stderr)
    if args.max_price is not None:
        before = len(results)
        results = [r for r in results if r.avg_price <= args.max_price]
        filtered = before - len(results)
        if filtered:
            print(f"  💰 均价 > ${args.max_price} 过滤掉 {filtered} 个类目", file=sys.stderr)

    if not results:
        print("❌ 筛选后无类目，请调整价格范围")
        sys.exit(1)

    if getattr(args, "json"):
        output = []
        for r in results:
            item = {
                "category": r.category,
                "blue_ocean_score": r.blue_ocean_score,
                "saturation_score": r.saturation_score,
                "ocean_level": r.ocean_level.value,
                "scores": {
                    "concentration": r.concentration_score,
                    "content_density": r.content_density_score,
                    "engagement_decay": r.engagement_decay_score,
                    "price_competition": r.price_competition_score,
                    "barrier": r.barrier_score,
                },
                "avg_price": r.avg_price,
                "entry_barrier_followers": r.entry_barrier_followers,
                "recommendation": r.recommendation,
                "refund_rate": {
                    "avg_refund_rate": r.avg_refund_rate,
                    "penalty_applied": r.refund_rate_penalty_applied,
                    "penalty_score": r.refund_rate_penalty,
                },
            }
            if r.trend_phase:
                item["trend"] = {
                    "phase": r.trend_phase,
                    "trend_score": r.trend_score,
                    "daily_growth_rate": r.daily_growth_rate,
                    "monthly_growth_rate": r.monthly_growth_rate,
                    "momentum": r.trend_momentum,
                    "peak_date": r.trend_peak_date,
                    "peak_volume": r.trend_peak_volume,
                    "daily_avg_7d": r.trend_daily_avg,
                }
            output.append(item)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_table(results)


if __name__ == "__main__":
    main()
