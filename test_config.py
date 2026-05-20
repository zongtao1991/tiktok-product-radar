"""测试配置保存和读取"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "config.json"

print("=" * 60)
print("测试配置保存和读取")
print("=" * 60)

print(f"\n1. 检查配置文件是否存在: {CONFIG_FILE.exists()}")

if CONFIG_FILE.exists():
    print(f"\n2. 读取当前配置:")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    print(json.dumps(config, indent=2, ensure_ascii=False))
else:
    print(f"\n2. 配置文件不存在，需要先通过前端保存配置")

print(f"\n3. 测试 config.py 模块:")
try:
    from config import get_config, AppConfig, RefundRateConfig, DataSourceConfig
    config = get_config()
    print(f"   data_source.provider: {config.data_source.provider}")
    print(f"   data_source.api_key: {config.data_source.api_key}")
    print(f"   data_source.region: {config.data_source.region}")
    print(f"   refund_rate.threshold: {config.refund_rate.threshold}")
    print(f"   refund_rate.penalty_score: {config.refund_rate.penalty_score}")
except Exception as e:
    print(f"   错误: {e}")
    import traceback
    traceback.print_exc()

print(f"\n4. 测试保存新配置:")
try:
    new_config = AppConfig()
    new_config.data_source = DataSourceConfig(
        provider="fastmoss",
        api_key="test_token_12345",
        api_endpoint=None,
        cache_ttl_seconds=3600,
        rate_limit_per_minute=60,
        region="US",
        daily_cost_limit=10.0,
    )
    new_config.refund_rate = RefundRateConfig(
        threshold=15.0,
        penalty_score=15.0,
        enabled=True,
    )
    new_config.save()
    print(f"   保存成功！")
    
    print(f"\n5. 重新读取验证:")
    from config import reload_config
    reloaded = reload_config()
    print(f"   data_source.provider: {reloaded.data_source.provider}")
    print(f"   data_source.api_key: {reloaded.data_source.api_key}")
    print(f"   data_source.region: {reloaded.data_source.region}")
    print(f"   refund_rate.threshold: {reloaded.refund_rate.threshold}")
    
    print(f"\n6. 检查配置文件内容:")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        content = json.load(f)
    print(json.dumps(content, indent=2, ensure_ascii=False))
    
except Exception as e:
    print(f"   错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
