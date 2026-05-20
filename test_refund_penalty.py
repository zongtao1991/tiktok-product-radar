"""测试退款率惩罚功能"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from loader import load_directory, load_trend_directory
from scorer import score_category
from config import get_config, AppConfig


def test_refund_rate_penalty():
    """测试退款率惩罚逻辑"""
    print("=" * 60)
    print("测试退款率惩罚功能")
    print("=" * 60)
    
    config = get_config()
    print(f"\n当前配置:")
    print(f"  退款率阈值: {config.refund_rate.threshold}%")
    print(f"  惩罚分数: +{config.refund_rate.penalty_score} 分")
    print(f"  惩罚功能: {'启用' if config.refund_rate.enabled else '禁用'}")
    
    datasets = load_directory("sample_data")
    trend_data = load_trend_directory("sample_data")
    
    print(f"\n分析结果（按平均退款率排序）:")
    print("-" * 60)
    
    results = []
    for cat, df in datasets.items():
        t_df = trend_data.get(cat)
        r = score_category(df, cat, trend_df=t_df)
        results.append(r)
    
    results.sort(key=lambda x: x.avg_refund_rate, reverse=True)
    
    for r in results:
        status = "⚠️ 已惩罚" if r.refund_rate_penalty_applied else "✅ 正常"
        penalty_info = f" (饱和度+{r.refund_rate_penalty})" if r.refund_rate_penalty_applied else ""
        
        print(f"\n【{r.category}】")
        print(f"  平均退款率: {r.avg_refund_rate}%")
        print(f"  状态: {status}{penalty_info}")
        print(f"  饱和度总分: {r.saturation_score}")
        print(f"  蓝海分: {r.blue_ocean_score}")
        print(f"  推荐: {r.recommendation}")
    
    print("\n" + "=" * 60)
    print("测试说明:")
    print("  - beauty_skincare (平均 ~25%): 应该触发惩罚")
    print("  - phone_cases (平均 ~23%): 应该触发惩罚")
    print("  - home_decor (平均 ~13%): 不应该触发惩罚")
    print("  - kitchen_gadgets (平均 ~8.5%): 不应该触发惩罚")
    print("  - pet_accessories (平均 ~6.5%): 不应该触发惩罚")
    print("=" * 60)


def test_custom_threshold():
    """测试自定义阈值"""
    print("\n\n" + "=" * 60)
    print("测试自定义配置 (阈值=15%, 惩罚=15分)")
    print("=" * 60)
    
    custom_config = AppConfig()
    custom_config.refund_rate.threshold = 15.0
    custom_config.refund_rate.penalty_score = 15.0
    
    datasets = load_directory("sample_data")
    
    from scorer import score_category
    
    results = []
    for cat, df in datasets.items():
        r = score_category(df, cat)
        results.append((cat, r))
    
    print(f"\n按当前默认配置 (阈值=20%) 分析:")
    for cat, r in results:
        status = "⚠️ 惩罚" if r.refund_rate_penalty_applied else "正常"
        print(f"  {cat}: 退款率={r.avg_refund_rate}%, {status}")


if __name__ == "__main__":
    test_refund_rate_penalty()
    test_custom_threshold()
