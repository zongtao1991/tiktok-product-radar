"""
测试 FastMoss API 连接
使用您自己的 Token 测试 API 是否正常工作
"""
import sys
import io
import json
import asyncio

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

print("=" * 70)
print("FastMoss API 测试工具")
print("=" * 70)

from config import get_config, AppConfig, DataSourceConfig, RefundRateConfig

config = get_config()

print(f"\n当前配置:")
print(f"  - provider: {config.data_source.provider}")
print(f"  - api_key: {'*' * (len(config.data_source.api_key) - 4) + config.data_source.api_key[-4:] if config.data_source.api_key else 'None'}")
print(f"  - api_endpoint: {config.data_source.api_endpoint or '默认'}")
print(f"  - region: {config.data_source.region}")
print(f"  - daily_cost_limit: ¥{config.data_source.daily_cost_limit}")

if not config.data_source.api_key:
    print("\n⚠️  错误: 未设置 API Key")
    print("\n请在前端界面点击「⚙ 配置」按钮，填写 API Key 后保存。")
    print("或直接编辑 config.json 文件。")
    sys.exit(1)

print("\n" + "=" * 70)
print("测试 1: 测试 Base URL 规范化")
print("=" * 70)

from fastmoss_client import _normalize_base_url

test_urls = [
    "https://openapi.fastmoss.com",
    "https://openapi.fastmoss.com/",
    "https://openapi.fastmoss.com/creator/v1/categoryInfo",
    "openapi.fastmoss.com",
    "openapi.fastmoss.com/creator/v1/categoryInfo",
    None,
    "",
]

print("\nURL 规范化测试:")
for url in test_urls:
    normalized = _normalize_base_url(url)
    print(f"  输入: {repr(url)}")
    print(f"  输出: {normalized}")
    print()

print("\n" + "=" * 70)
print("测试 2: 测试 categoryInfo 接口（获取类目列表）")
print("=" * 70)
print(f"\n这是您之前测试成功的接口: /creator/v1/categoryInfo")
print(f"您的测试代码使用了参数: country={config.data_source.region}, category_name='beauty'")

async def test_category_info():
    from fastmoss_client import FastMossClient
    
    client = FastMossClient(
        client_secret=config.data_source.api_key,
        base_url=config.data_source.api_endpoint,
        debug=True,
    )
    
    print(f"\n客户端 Base URL: {client.base_url}")
    
    try:
        print(f"\n测试 A: 不带 category_name 参数调用...")
        data1 = await client.get_category_info(
            country=config.data_source.region,
        )
        
        print(f"\n✅ 不带 category_name 调用成功!")
        print(f"响应数据预览:")
        print(json.dumps(data1, indent=2, ensure_ascii=False)[:1000])
        
        print(f"\n测试 B: 带 category_name='beauty' 参数调用（与您的测试代码一致）...")
        data2 = await client.get_category_info(
            country=config.data_source.region,
            category_name="beauty",
        )
        
        print(f"\n✅ 带 category_name 调用成功!")
        print(f"响应数据预览:")
        print(json.dumps(data2, indent=2, ensure_ascii=False)[:1000])
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"\n❌ 调用失败: {e}")
        import traceback
        traceback.print_exc()
        await client.close()
        return False

result = asyncio.run(test_category_info())

if result:
    print("\n" + "=" * 70)
    print("✅ categoryInfo 接口测试成功!")
    print("=" * 70)
else:
    print("\n" + "=" * 70)
    print("❌ categoryInfo 接口测试失败")
    print("=" * 70)

print("\n" + "=" * 70)
print("测试 3: 测试新增的榜单接口")
print("=" * 70)
print(f"\n截图中显示的接口:")
print(f"  - 蓝v达人榜: /creator/v1/rank/topBlueVGrowth")
print(f"  - 热门达人榜: /creator/v1/rank/topFollowers")
print(f"  - 机构销售榜: /agency/v1/rank/salesRank")

async def test_new_apis():
    from fastmoss_client import FastMossClient
    
    client = FastMossClient(
        client_secret=config.data_source.api_key,
        base_url=config.data_source.api_endpoint,
        debug=True,
        daily_cost_limit=config.data_source.daily_cost_limit,
    )
    
    tests_passed = 0
    tests_total = 3
    
    print(f"\n测试 A: 蓝v达人榜 (/creator/v1/rank/topBlueVGrowth)...")
    try:
        data = await client.get_top_bluev_growth_creators(
            country=config.data_source.region,
            page_size=5,
        )
        print(f"✅ 蓝v达人榜调用成功!")
        print(f"   响应数据: {json.dumps(data, ensure_ascii=False)[:500]}")
        tests_passed += 1
    except Exception as e:
        print(f"❌ 蓝v达人榜调用失败: {e}")
    
    print(f"\n测试 B: 热门达人榜 (/creator/v1/rank/topFollowers)...")
    try:
        data = await client.get_top_followers_creators(
            country=config.data_source.region,
            page_size=5,
        )
        print(f"✅ 热门达人榜调用成功!")
        print(f"   响应数据: {json.dumps(data, ensure_ascii=False)[:500]}")
        tests_passed += 1
    except Exception as e:
        print(f"❌ 热门达人榜调用失败: {e}")
    
    print(f"\n测试 C: 机构销售榜 (/agency/v1/rank/salesRank)...")
    try:
        data = await client.get_agency_sales_rank(
            country=config.data_source.region,
            page_size=5,
        )
        print(f"✅ 机构销售榜调用成功!")
        print(f"   响应数据: {json.dumps(data, ensure_ascii=False)[:500]}")
        tests_passed += 1
    except Exception as e:
        print(f"❌ 机构销售榜调用失败: {e}")
    
    print(f"\n成本统计: {client.get_cost_summary()}")
    await client.close()
    
    return tests_passed, tests_total

tests_passed, tests_total = asyncio.run(test_new_apis())

print(f"\n" + "=" * 70)
print(f"新增榜单接口测试结果: {tests_passed}/{tests_total}")
print("=" * 70)

print("\n" + "=" * 70)
print("测试 4: 测试 FastMossDataSource 完整流程")
print("=" * 70)

async def test_data_source():
    from data_source import FastMossDataSource
    
    print(f"\n创建 FastMossDataSource...")
    
    ds = FastMossDataSource(
        client_secret=config.data_source.api_key,
        base_url=config.data_source.api_endpoint,
        cache_ttl_seconds=config.data_source.cache_ttl_seconds,
        daily_cost_limit=config.data_source.daily_cost_limit,
        country=config.data_source.region,
        debug=True,
    )
    
    print(f"\n连接到 FastMoss...")
    if not ds.connect():
        print("❌ 连接失败")
        return False
    
    print("✅ 连接成功")
    
    print(f"\n尝试获取达人数据（使用 topEcommerce 榜单）...")
    print(f"参数: country={config.data_source.region}, page_size=10")
    
    try:
        creators = ds.fetch_creators(
            category="",
            limit=10,
        )
        
        print(f"\n获取到 {len(creators)} 个达人")
        
        if creators:
            print("\n前 3 个达人:")
            for i, c in enumerate(creators[:3]):
                print(f"  {i+1}. {c.username}")
                print(f"      粉丝: {c.followers:,}")
                print(f"      月 GMV: ${c.gmv_monthly:,.2f}")
        
        cost_summary = ds.get_cost_summary()
        print(f"\n成本统计: {cost_summary}")
        
        ds.disconnect()
        return len(creators) > 0
        
    except Exception as e:
        print(f"\n❌ 获取达人数据失败: {e}")
        import traceback
        traceback.print_exc()
        ds.disconnect()
        return False

result2 = asyncio.run(test_data_source())

if result2:
    print("\n" + "=" * 70)
    print("✅ FastMossDataSource 完整流程测试成功!")
    print("=" * 70)
else:
    print("\n" + "=" * 70)
    print("ℹ️  FastMossDataSource 测试说明")
    print("=" * 70)
    print("\n如果 topEcommerce 接口失败，可能的原因:")
    print("  1. 该接口需要特定参数")
    print("  2. 您的 API 配额不足")
    print("  3. 该接口需要特定权限")
    print("\n建议:")
    print("  - 先使用 /creator/v1/search 接口搜索特定关键词")
    print("  - 或查看 FastMoss 官方文档确认接口参数")

print("\n" + "=" * 70)
print("测试完成")
print("=" * 70)
