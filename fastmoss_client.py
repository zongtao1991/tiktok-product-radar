"""
FastMoss OpenAPI 客户端
基于官方文档: https://developers.fastmoss.com/

API 特点：
- Base URL: https://openapi.fastmoss.com
- 认证方式: Authorization: Bearer {client_secret}
- 所有接口都是 POST 请求
- 返回 JSON 格式，code=0 表示成功
- 参数使用: country 而不是 region

API 价格 (2026年)：
- Creator 相关: ¥0.14/次
- Product 相关: ¥0.07/次
- Shop 相关: ¥0.07/次

示例请求：
```python
import requests
import json

url = "https://openapi.fastmoss.com/creator/v1/categoryInfo"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer your_token_here"
}
payload = {
    "country": "US"
}
response = requests.post(url, headers=headers, data=json.dumps(payload))
print(response.json())
```
"""
import time
import hashlib
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import pandas as pd


API_COSTS = {
    "creator_category_info": 0.0,
    "creator_search": 0.14,
    "creator_top_ecommerce": 0.14,
    "creator_top_bluev_growth": 0.14,
    "creator_top_followers": 0.14,
    "creator_product_list": 0.14,
    "agency_sales_rank": 0.14,
    "product_search": 0.07,
    "product_sales_trend": 0.07,
    "product_rank_top_selling": 0.07,
    "shop_search": 0.07,
    "video_search": 0.07,
    "live_search": 0.07,
}


@dataclass
class APICallRecord:
    """API 调用记录"""
    endpoint: str
    cost: float
    timestamp: float
    success: bool
    response_time_ms: int
    error_msg: Optional[str] = None


@dataclass
class CostTracker:
    """成本追踪器"""
    total_spent: float = 0.0
    daily_spent: float = 0.0
    daily_limit: float = 5.0
    call_count: int = 0
    daily_calls: int = 0
    last_reset_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    call_history: List[APICallRecord] = field(default_factory=list)

    def add_call(
        self,
        endpoint: str,
        cost: float,
        success: bool,
        response_time_ms: int,
        error_msg: Optional[str] = None,
    ):
        """记录一次 API 调用"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if self.last_reset_date != today:
            self.daily_spent = 0.0
            self.daily_calls = 0
            self.last_reset_date = today
        
        if success:
            self.total_spent += cost
            self.daily_spent += cost
        
        self.call_count += 1
        self.daily_calls += 1
        
        self.call_history.append(APICallRecord(
            endpoint=endpoint,
            cost=cost if success else 0.0,
            timestamp=time.time(),
            success=success,
            response_time_ms=response_time_ms,
            error_msg=error_msg,
        ))
        
        if len(self.call_history) > 1000:
            self.call_history = self.call_history[-500:]

    def can_call(self, cost: float) -> bool:
        """检查是否可以调用（不超过每日限额）"""
        return self.daily_spent + cost <= self.daily_limit


@dataclass
class CacheEntry:
    """缓存条目"""
    data: Any
    timestamp: float
    ttl_seconds: int


def _normalize_base_url(url: Optional[str]) -> str:
    """
    规范化 Base URL
    
    处理用户可能输入的各种格式：
    - https://openapi.fastmoss.com (正确)
    - https://openapi.fastmoss.com/ (有末尾斜杠)
    - https://openapi.fastmoss.com/creator/v1/categoryInfo (包含了 endpoint)
    - openapi.fastmoss.com (没有协议)
    """
    if not url:
        return "https://openapi.fastmoss.com"
    
    url = url.strip()
    
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    parsed = urlparse(url)
    
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    return base_url


class FastMossClient:
    """FastMoss OpenAPI 客户端"""

    DEFAULT_BASE_URL = "https://openapi.fastmoss.com"

    def __init__(
        self,
        client_secret: str,
        base_url: Optional[str] = None,
        cache_ttl_seconds: int = 3600,
        daily_cost_limit: float = 5.0,
        debug: bool = False,
    ):
        self.client_secret = client_secret
        self.base_url = _normalize_base_url(base_url)
        self.cache_ttl_seconds = cache_ttl_seconds
        self.debug = debug
        
        self.cache: Dict[str, CacheEntry] = {}
        self.cost_tracker = CostTracker(daily_limit=daily_cost_limit)
        self.session: Optional[aiohttp.ClientSession] = None

    def _debug(self, msg: str):
        """调试日志"""
        if self.debug:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[FastMoss {timestamp}] {msg}")

    async def _ensure_session(self):
        """确保 HTTP 会话存在"""
        if self.session is None or self.session.closed:
            self._debug(f"创建新的 HTTP 会话，Base URL: {self.base_url}")
            self.session = aiohttp.ClientSession(
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.client_secret}",
                }
            )

    async def close(self):
        """关闭 HTTP 会话"""
        if self.session and not self.session.closed:
            self._debug("关闭 HTTP 会话")
            await self.session.close()

    def _get_cache_key(self, endpoint: str, params: dict) -> str:
        """生成缓存键"""
        params_str = json.dumps(params, sort_keys=True, ensure_ascii=False)
        return f"{endpoint}:{params_str}"

    def _get_cached(self, endpoint: str, params: dict) -> Optional[Any]:
        """获取缓存数据"""
        key = self._get_cache_key(endpoint, params)
        entry = self.cache.get(key)
        
        if entry is None:
            self._debug(f"缓存未命中: {endpoint}")
            return None
        
        if time.time() - entry.timestamp > entry.ttl_seconds:
            self._debug(f"缓存已过期: {endpoint}")
            del self.cache[key]
            return None
        
        self._debug(f"缓存命中: {endpoint}")
        return entry.data

    def _set_cache(self, endpoint: str, params: dict, data: Any, ttl_seconds: Optional[int] = None):
        """设置缓存数据"""
        key = self._get_cache_key(endpoint, params)
        self.cache[key] = CacheEntry(
            data=data,
            timestamp=time.time(),
            ttl_seconds=ttl_seconds or self.cache_ttl_seconds,
        )
        self._debug(f"缓存已设置: {endpoint}")

    async def _api_call(
        self,
        endpoint: str,
        params: dict,
        cost: float,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        调用 FastMoss API

        Args:
            endpoint: API 端点路径（不含 base_url），如 "/creator/v1/categoryInfo"
            params: 请求参数
            cost: 本次调用成本
            use_cache: 是否使用缓存

        Returns:
            API 响应数据
        """
        self._debug(f"调用 API: {endpoint}")
        self._debug(f"  参数: {json.dumps(params, ensure_ascii=False)}")
        
        if use_cache:
            cached = self._get_cached(endpoint, params)
            if cached is not None:
                return cached

        if not self.cost_tracker.can_call(cost):
            raise ValueError(
                f"API 调用成本 ¥{cost} 将超出每日限额 ¥{self.cost_tracker.daily_limit}，"
                f"当前已消费 ¥{self.cost_tracker.daily_spent}"
            )

        await self._ensure_session()
        start_time = time.time()

        try:
            url = f"{self.base_url}{endpoint}"
            self._debug(f"  完整 URL: {url}")
            self._debug(f"  请求 payload: {json.dumps(params, ensure_ascii=False)}")
            
            async with self.session.post(url, data=json.dumps(params)) as response:
                response_time_ms = int((time.time() - start_time) * 1000)
                self._debug(f"  HTTP 状态码: {response.status}")
                
                if response.status != 200:
                    error_text = await response.text()
                    self._debug(f"  错误响应: {error_text[:500]}")
                    self.cost_tracker.add_call(
                        endpoint, cost, False, response_time_ms,
                        f"HTTP {response.status}: {error_text[:200]}"
                    )
                    raise ValueError(f"API 调用失败，HTTP 状态码: {response.status}, 响应: {error_text[:500]}")

                result = await response.json()
                self._debug(f"  响应: {json.dumps(result, ensure_ascii=False)[:500]}")
                
                if result.get("code") != 0:
                    msg = result.get("msg", result.get("message", "Unknown error"))
                    code = result.get("code")
                    self.cost_tracker.add_call(
                        endpoint, cost, False, response_time_ms,
                        f"code={code}: {msg}"
                    )
                    raise ValueError(f"API 错误 (code={code}): {msg}")

                self.cost_tracker.add_call(endpoint, cost, True, response_time_ms)
                
                data = result.get("data", {})
                self._set_cache(endpoint, params, data)
                
                self._debug(f"  调用成功，耗时: {response_time_ms}ms, 成本: ¥{cost}")
                return data

        except aiohttp.ClientError as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"网络请求失败: {e}"
            self._debug(f"  {error_msg}")
            self.cost_tracker.add_call(endpoint, cost, False, response_time_ms, error_msg)
            raise ValueError(error_msg)

    async def get_category_info(
        self,
        country: str = "US",
        category_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取类目信息 (/creator/v1/categoryInfo)
        
        这是用户测试通过的接口，用于获取类目列表
        测试代码示例: payload = {"country": "US", "category_name": "beauty"}
        
        成本: ¥0.0/次 (可能免费或未知价格)
        """
        params = {
            "country": country,
        }
        if category_name:
            params["category_name"] = category_name

        return await self._api_call(
            "/creator/v1/categoryInfo",
            params,
            cost=API_COSTS["creator_category_info"],
        )

    async def search_creators(
        self,
        keyword: Optional[str] = None,
        country: Optional[str] = None,
        min_followers: Optional[int] = None,
        max_followers: Optional[int] = None,
        min_avg_views: Optional[int] = None,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        筛选达人 (/creator/v1/search)
        
        成本: ¥0.14/次
        """
        params = {
            "page": page,
            "page_size": page_size,
        }
        
        if keyword:
            params["keyword"] = keyword
        if country:
            params["country"] = country
        if min_followers is not None:
            params["min_followers"] = min_followers
        if max_followers is not None:
            params["max_followers"] = max_followers
        if min_avg_views is not None:
            params["min_avg_views"] = min_avg_views
        if category:
            params["category"] = category

        return await self._api_call(
            "/creator/v1/search",
            params,
            cost=API_COSTS["creator_search"],
        )

    async def get_top_ecommerce_creators(
        self,
        region: Optional[str] = None,
        country: Optional[str] = None,
        category: Optional[str] = None,
        creator_category_id: Optional[int] = None,
        product_category_id: Optional[int] = None,
        ecommerce_type: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        获取带货能力最强的达人榜单 (/creator/v1/rank/topEcommerce)
        截图中显示为"带货达人榜"
        
        参数说明（支持多种格式，便于测试和向后兼容）：
        
        根据官方文档的标准格式：
        - region: 国家/区域，如 'US', 'GB', 'MX' 等
        - creator_category_id: 达人类目 ID（integer）
        - product_category_id: 商品类目 ID（integer）
        - ecommerce_type: 带货类型 (1=视频, 2=直播)
        
        向后兼容格式（用于测试）：
        - country: 与 region 相同
        - category: 类目名称（string）
        
        成本: ¥0.14/次
        """
        params = {
            "page": page,
            "pagesize": page_size,
        }
        
        actual_region = region or country
        
        if actual_region and not creator_category_id and not category:
            params["country"] = actual_region
        elif actual_region or creator_category_id or product_category_id:
            filter_params = {}
            if actual_region:
                filter_params["region"] = actual_region
            if creator_category_id is not None:
                filter_params["creator_category_id"] = creator_category_id
            if product_category_id is not None:
                filter_params["product_category_id"] = product_category_id
            if filter_params:
                params["filter"] = filter_params
        
        if category:
            params["category"] = category
        
        if ecommerce_type is not None:
            params["ecommerce_type"] = ecommerce_type

        return await self._api_call(
            "/creator/v1/rank/topEcommerce",
            params,
            cost=API_COSTS["creator_top_ecommerce"],
        )

    async def get_top_bluev_growth_creators(
        self,
        country: Optional[str] = None,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        获取蓝v达人榜 (/creator/v1/rank/topBlueVGrowth)
        截图中显示为"蓝v达人榜"
        
        成本: ¥0.14/次
        """
        params = {
            "page": page,
            "page_size": page_size,
        }
        
        if country:
            params["country"] = country
        if category:
            params["category"] = category

        return await self._api_call(
            "/creator/v1/rank/topBlueVGrowth",
            params,
            cost=API_COSTS["creator_top_bluev_growth"],
        )

    async def get_top_followers_creators(
        self,
        country: Optional[str] = None,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        获取热门达人榜 (/creator/v1/rank/topFollowers)
        截图中显示为"热门达人榜"
        
        成本: ¥0.14/次
        """
        params = {
            "page": page,
            "page_size": page_size,
        }
        
        if country:
            params["country"] = country
        if category:
            params["category"] = category

        return await self._api_call(
            "/creator/v1/rank/topFollowers",
            params,
            cost=API_COSTS["creator_top_followers"],
        )

    async def get_agency_sales_rank(
        self,
        country: Optional[str] = None,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        获取机构销售榜 (/agency/v1/rank/salesRank)
        截图中显示为"机构销售榜"
        
        成本: ¥0.14/次
        """
        params = {
            "page": page,
            "page_size": page_size,
        }
        
        if country:
            params["country"] = country
        if category:
            params["category"] = category

        return await self._api_call(
            "/agency/v1/rank/salesRank",
            params,
            cost=API_COSTS["agency_sales_rank"],
        )

    async def get_creator_product_list(
        self,
        creator_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        获取达人带货商品列表 (/creator/v1/productList)
        
        成本: ¥0.14/次
        """
        params = {
            "creator_id": creator_id,
            "page": page,
            "page_size": page_size,
        }

        return await self._api_call(
            "/creator/v1/productList",
            params,
            cost=API_COSTS["creator_product_list"],
        )

    async def search_products(
        self,
        keyword: Optional[str] = None,
        country: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_sales: Optional[int] = None,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        筛选商品 (/product/v1/search)
        
        成本: ¥0.07/次
        """
        params = {
            "page": page,
            "page_size": page_size,
        }
        
        if keyword:
            params["keyword"] = keyword
        if country:
            params["country"] = country
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price
        if min_sales is not None:
            params["min_sales"] = min_sales
        if category:
            params["category"] = category

        return await self._api_call(
            "/product/v1/search",
            params,
            cost=API_COSTS["product_search"],
        )

    async def get_product_sales_trend(
        self,
        product_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        获取商品历史销量数据 (/product/v1/salesTrend)
        
        成本: ¥0.07/次
        """
        params = {
            "product_id": product_id,
            "days": days,
        }

        return await self._api_call(
            "/product/v1/salesTrend",
            params,
            cost=API_COSTS["product_sales_trend"],
        )

    async def get_top_selling_products(
        self,
        country: Optional[str] = None,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        获取商品销量榜单 (/product/v1/rank/topSelling)
        
        成本: ¥0.07/次
        """
        params = {
            "page": page,
            "page_size": page_size,
        }
        
        if country:
            params["country"] = country
        if category:
            params["category"] = category

        return await self._api_call(
            "/product/v1/rank/topSelling",
            params,
            cost=API_COSTS["product_rank_top_selling"],
        )

    def get_cost_summary(self) -> Dict[str, Any]:
        """获取成本统计"""
        return {
            "total_spent": round(self.cost_tracker.total_spent, 2),
            "daily_spent": round(self.cost_tracker.daily_spent, 2),
            "daily_limit": self.cost_tracker.daily_limit,
            "remaining_budget": round(self.cost_tracker.daily_limit - self.cost_tracker.daily_spent, 2),
            "total_calls": self.cost_tracker.call_count,
            "daily_calls": self.cost_tracker.daily_calls,
            "last_reset_date": self.cost_tracker.last_reset_date,
            "base_url": self.base_url,
        }

    def clear_cache(self):
        """清空缓存"""
        self._debug("清空缓存")
        self.cache.clear()
