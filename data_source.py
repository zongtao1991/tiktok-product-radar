"""
数据源抽象接口层
定义统一的数据获取接口，支持多种数据源实现：
- CSV 文件（现有方式）
- FastMoss API（待实现）
- Kalodata API（待实现）
- 其他第三方平台
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import List, Optional, Dict, Any
import pandas as pd


class DataSourceType(Enum):
    """数据源类型"""
    CSV = "csv"
    FASTMOSS = "fastmoss"
    KALODATA = "kalodata"
    CUSTOM = "custom"


@dataclass
class CreatorData:
    """达人数据结构（与 Creator 模型对齐）"""
    username: str
    followers: int
    avg_views: float
    avg_likes: float
    avg_comments: float
    avg_shares: float
    video_count: int
    avg_price: float
    commission_rate: float
    gmv_monthly: float
    entry_date: str
    refund_rate: float = 0.0
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class ProductData:
    """商品数据结构"""
    product_id: str
    product_name: str
    category: str
    price: float
    original_price: Optional[float] = None
    sales_30d: int = 0
    gmv_30d: float = 0.0
    refund_rate: float = 0.0
    creator_count: int = 0
    first_online_date: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class TrendData:
    """趋势数据点"""
    date: date
    video_count: int
    sales_count: Optional[int] = None
    gmv: Optional[float] = None


class DataSource(ABC):
    """数据源抽象基类"""

    @property
    @abstractmethod
    def source_type(self) -> DataSourceType:
        """返回数据源类型"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """返回数据源名称"""
        pass

    @abstractmethod
    def connect(self) -> bool:
        """建立连接/初始化"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """断开连接/清理资源"""
        pass

    @abstractmethod
    def list_categories(self) -> List[str]:
        """获取可用类目列表"""
        pass

    @abstractmethod
    def fetch_creators(
        self,
        category: str,
        limit: int = 50,
        min_followers: Optional[int] = None,
        max_followers: Optional[int] = None,
    ) -> List[CreatorData]:
        """
        获取指定类目的达人数据

        Args:
            category: 类目名称
            limit: 返回数量限制
            min_followers: 最小粉丝数过滤
            max_followers: 最大粉丝数过滤

        Returns:
            达人数据列表
        """
        pass

    @abstractmethod
    def fetch_products(
        self,
        category: str,
        limit: int = 100,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> List[ProductData]:
        """
        获取指定类目的商品数据

        Args:
            category: 类目名称
            limit: 返回数量限制
            min_price: 最低价格过滤
            max_price: 最高价格过滤

        Returns:
            商品数据列表
        """
        pass

    @abstractmethod
    def fetch_trend(
        self,
        category: str,
        days: int = 60,
    ) -> List[TrendData]:
        """
        获取指定类目的趋势数据

        Args:
            category: 类目名称
            days: 获取天数

        Returns:
            趋势数据点列表，按日期排序
        """
        pass

    def fetch_creators_as_df(
        self,
        category: str,
        **kwargs,
    ) -> pd.DataFrame:
        """
        获取达人数据并返回 DataFrame（兼容现有接口）

        Returns:
            包含达人数据的 DataFrame
        """
        creators = self.fetch_creators(category, **kwargs)
        records = []
        for c in creators:
            records.append({
                "username": c.username,
                "followers": c.followers,
                "avg_views": c.avg_views,
                "avg_likes": c.avg_likes,
                "avg_comments": c.avg_comments,
                "avg_shares": c.avg_shares,
                "video_count": c.video_count,
                "avg_price": c.avg_price,
                "commission_rate": c.commission_rate,
                "gmv_monthly": c.gmv_monthly,
                "entry_date": c.entry_date,
                "refund_rate": c.refund_rate,
            })
        return pd.DataFrame(records)

    def fetch_trend_as_df(
        self,
        category: str,
        **kwargs,
    ) -> Optional[pd.DataFrame]:
        """
        获取趋势数据并返回 DataFrame（兼容现有接口）

        Returns:
            包含趋势数据的 DataFrame，或 None
        """
        trends = self.fetch_trend(category, **kwargs)
        if not trends:
            return None
        records = []
        for t in trends:
            records.append({
                "date": t.date.isoformat(),
                "video_count": t.video_count,
                "sales_count": t.sales_count,
                "gmv": t.gmv,
            })
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)


class CSVDataSource(DataSource):
    """CSV 文件数据源（现有方式的封装）"""

    def __init__(self, data_dir: str):
        from pathlib import Path
        self.data_dir = Path(data_dir)
        self._categories: List[str] = []

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.CSV

    @property
    def name(self) -> str:
        return f"CSV ({self.data_dir})"

    def connect(self) -> bool:
        from loader import load_directory
        try:
            datasets = load_directory(str(self.data_dir))
            self._categories = list(datasets.keys())
            return True
        except Exception:
            return False

    def disconnect(self) -> None:
        self._categories = []

    def list_categories(self) -> List[str]:
        return self._categories.copy()

    def fetch_creators(
        self,
        category: str,
        limit: int = 50,
        min_followers: Optional[int] = None,
        max_followers: Optional[int] = None,
    ) -> List[CreatorData]:
        from loader import load_csv
        from pathlib import Path

        csv_path = self.data_dir / f"{category}.csv"
        if not csv_path.exists():
            return []

        df = load_csv(str(csv_path))

        if min_followers is not None:
            df = df[df["followers"] >= min_followers]
        if max_followers is not None:
            df = df[df["followers"] <= max_followers]

        df = df.head(limit)

        creators = []
        for _, row in df.iterrows():
            creators.append(CreatorData(
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
                raw_data=row.to_dict(),
            ))
        return creators

    def fetch_products(
        self,
        category: str,
        limit: int = 100,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> List[ProductData]:
        return []

    def fetch_trend(
        self,
        category: str,
        days: int = 60,
    ) -> List[TrendData]:
        from loader import load_trend_csv
        from pathlib import Path

        csv_path = self.data_dir / f"{category}_trend.csv"
        if not csv_path.exists():
            return []

        try:
            df = load_trend_csv(str(csv_path))
            df = df.tail(days)

            trends = []
            for _, row in df.iterrows():
                dt = row["date"]
                if hasattr(dt, "date"):
                    d = dt.date()
                else:
                    d = datetime.strptime(str(dt), "%Y-%m-%d").date()
                trends.append(TrendData(
                    date=d,
                    video_count=int(row["video_count"]),
                ))
            return trends
        except Exception:
            return []


class DataSourceFactory:
    """数据源工厂"""

    _registry: Dict[DataSourceType, type] = {}

    @classmethod
    def register(cls, source_type: DataSourceType, source_class: type):
        """注册数据源类型"""
        cls._registry[source_type] = source_class

    @classmethod
    def create(
        cls,
        source_type: DataSourceType,
        **kwargs,
    ) -> DataSource:
        """创建数据源实例"""
        if source_type not in cls._registry:
            raise ValueError(f"Unknown data source type: {source_type}")
        return cls._registry[source_type](**kwargs)


DataSourceFactory.register(DataSourceType.CSV, CSVDataSource)


class FastMossDataSource(DataSource):
    """
    FastMoss API 数据源
    
    基于 FastMoss OpenAPI，需要 client_secret 进行认证
    API 文档: https://developers.fastmoss.com/
    
    重要提示：
    - 参数使用: country 而不是 region
    - Base URL 会自动规范化（即使用户输入了完整 URL）
    
    成本说明：
    - Creator 相关: ¥0.14/次
    - Product 相关: ¥0.07/次
    """

    def __init__(
        self,
        client_secret: str,
        base_url: Optional[str] = None,
        cache_ttl_seconds: int = 3600,
        daily_cost_limit: float = 5.0,
        country: str = "US",
        debug: bool = True,
    ):
        self.client_secret = client_secret
        self.base_url = base_url
        self.cache_ttl_seconds = cache_ttl_seconds
        self.daily_cost_limit = daily_cost_limit
        self.country = country
        self.debug = debug
        self._client: Optional["FastMossClient"] = None
        self._connected = False

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.FASTMOSS

    @property
    def name(self) -> str:
        return f"FastMoss API ({self.country})"

    def connect(self) -> bool:
        """建立连接（初始化客户端）"""
        try:
            from fastmoss_client import FastMossClient
            
            if self.debug:
                print(f"[FastMossDataSource] 初始化客户端:")
                print(f"  - client_secret: {'*' * (len(self.client_secret) - 4) + self.client_secret[-4:] if self.client_secret else 'None'}")
                print(f"  - base_url: {self.base_url or '默认'}")
                print(f"  - country: {self.country}")
                print(f"  - daily_cost_limit: ¥{self.daily_cost_limit}")
            
            self._client = FastMossClient(
                client_secret=self.client_secret,
                base_url=self.base_url,
                cache_ttl_seconds=self.cache_ttl_seconds,
                daily_cost_limit=self.daily_cost_limit,
                debug=self.debug,
            )
            self._connected = True
            
            if self.debug:
                print(f"[FastMossDataSource] 客户端初始化完成，Base URL: {self._client.base_url}")
            
            return True
        except Exception as e:
            print(f"[FastMossDataSource] 连接失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def disconnect(self) -> None:
        """断开连接"""
        if self._client:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import threading
                    t = threading.Thread(target=lambda: asyncio.run(self._client.close()))
                    t.start()
                    t.join(timeout=5)
                else:
                    asyncio.run(self._client.close())
            except Exception:
                pass
        self._connected = False
        self._client = None

    def list_categories(self) -> List[str]:
        """获取可用类目列表"""
        if not self._connected or not self._client:
            return []
        
        try:
            if self.debug:
                print(f"[FastMossDataSource] 获取类目列表...")
            
            data = self._run_async(
                self._client.get_category_info(
                    country=self.country,
                )
            )
            
            categories = []
            items = data.get("list", data.get("items", []))
            
            if self.debug:
                print(f"[FastMossDataSource] 类目列表响应: {str(data)[:300]}...")
            
            for item in items:
                if isinstance(item, dict):
                    cat_name = item.get("category_name") or item.get("name") or item.get("category")
                    if cat_name:
                        categories.append(str(cat_name))
                elif isinstance(item, str):
                    categories.append(item)
            
            if self.debug:
                print(f"[FastMossDataSource] 找到 {len(categories)} 个类目")
            
            return categories
            
        except Exception as e:
            if self.debug:
                print(f"[FastMossDataSource] 获取类目列表失败: {e}")
            return []

    def _run_async(self, coro):
        """同步运行异步协程（在 Web 服务器环境中安全处理）"""
        import asyncio
        import threading
        
        result = [None]
        exception = [None]
        
        def run_coro():
            try:
                result[0] = asyncio.run(coro)
            except Exception as e:
                exception[0] = e
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                t = threading.Thread(target=run_coro)
                t.start()
                t.join(timeout=60)
                if exception[0] is not None:
                    raise exception[0]
                return result[0]
            else:
                return asyncio.run(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def fetch_creators(
        self,
        category: str,
        limit: int = 50,
        min_followers: Optional[int] = None,
        max_followers: Optional[int] = None,
    ) -> List[CreatorData]:
        """
        从 FastMoss 获取达人数据
        
        策略：优先使用带货达人榜单 (/creator/v1/rank/topEcommerce)，
             备选使用搜索接口 (/creator/v1/search)
        
        成本：¥0.14/次
        """
        if not self._connected or not self._client:
            raise RuntimeError("FastMoss 数据源未连接，请先调用 connect()")

        try:
            if self.debug:
                print(f"[FastMossDataSource] 获取达人数据: category={category}, limit={limit}, country={self.country}")
            
            data = self._run_async(
                self._client.get_top_ecommerce_creators(
                    country=self.country,
                    category=category if category else None,
                    page_size=limit,
                )
            )
            
            if self.debug:
                print(f"[FastMossDataSource] API 响应数据: {str(data)[:500]}...")
            
            creators = []
            items = data.get("list", data.get("items", []))
            
            if self.debug:
                print(f"[FastMossDataSource] 找到 {len(items)} 个达人")
            
            for item in items:
                creator = self._parse_creator_data(item, category)
                if creator:
                    creators.append(creator)
            
            if self.debug:
                print(f"[FastMossDataSource] 成功解析 {len(creators)} 个达人")
            
            return creators

        except Exception as e:
            print(f"[FastMossDataSource] 获取达人数据失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_creator_data(self, item: Dict[str, Any], category: str) -> Optional[CreatorData]:
        """
        解析 FastMoss 返回的达人数据
        
        根据官方文档，带货达人榜返回的字段可能在：
        - 根级别: uid, follower_count, creator_usd_gmv, video_count, product_count 等
        - creator 嵌套字段: nickname, unique_id, follower_count, video_count 等
        """
        try:
            creator = item.get("creator", {})
            
            username = (
                item.get("username") or 
                item.get("creator_name") or 
                item.get("nickname") or
                creator.get("nickname") or
                creator.get("unique_id") or
                ""
            )
            if not username:
                return None

            followers = int(
                item.get("followers") or 
                item.get("fan_count") or 
                item.get("follower_count") or
                creator.get("follower_count") or
                0
            )
            
            avg_views = float(item.get("avg_views", item.get("video_avg_play", 0)))
            avg_likes = float(item.get("avg_likes", item.get("video_avg_like", 0)))
            avg_comments = float(item.get("avg_comments", item.get("video_avg_comment", 0)))
            avg_shares = float(item.get("avg_shares", item.get("video_avg_share", 0)))
            
            video_count = int(
                item.get("video_count") or 
                item.get("video_count_30d") or
                creator.get("video_count") or
                0
            )
            
            avg_price = float(item.get("avg_price", item.get("product_avg_price", 0)))
            commission_rate = float(item.get("commission_rate", item.get("commission_pct", 0)))
            
            gmv_monthly = float(
                item.get("gmv_monthly") or 
                item.get("gmv_30d") or 
                item.get("creator_usd_gmv") or
                item.get("video_usd_gmv") or
                item.get("live_usd_gmv") or
                0
            )
            
            entry_date = item.get("entry_date", item.get("earliest_video_date", ""))
            refund_rate = float(item.get("refund_rate", 0.0))

            return CreatorData(
                username=username,
                followers=followers,
                avg_views=avg_views,
                avg_likes=avg_likes,
                avg_comments=avg_comments,
                avg_shares=avg_shares,
                video_count=video_count,
                avg_price=avg_price,
                commission_rate=commission_rate,
                gmv_monthly=gmv_monthly,
                entry_date=entry_date or "",
                refund_rate=refund_rate,
                raw_data=item,
            )
        except Exception as e:
            print(f"解析达人数据失败: {e}")
            return None

    def fetch_products(
        self,
        category: str,
        limit: int = 100,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> List[ProductData]:
        """
        从 FastMoss 获取商品数据
        
        成本：¥0.07/次
        """
        if not self._connected or not self._client:
            raise RuntimeError("FastMoss 数据源未连接")

        try:
            if self.debug:
                print(f"[FastMossDataSource] 获取商品数据: category={category}, limit={limit}, country={self.country}")
            
            data = self._run_async(
                self._client.get_top_selling_products(
                    country=self.country,
                    category=category if category else None,
                    page_size=limit,
                )
            )
            
            products = []
            items = data.get("list", data.get("items", []))
            
            for item in items:
                product = self._parse_product_data(item, category)
                if product:
                    products.append(product)
            
            return products

        except Exception as e:
            print(f"[FastMossDataSource] 获取商品数据失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_product_data(self, item: Dict[str, Any], category: str) -> Optional[ProductData]:
        """解析 FastMoss 返回的商品数据"""
        try:
            product_id = item.get("product_id") or item.get("id")
            product_name = item.get("product_name") or item.get("title", "")
            
            if not product_id and not product_name:
                return None

            price = float(item.get("price", item.get("current_price", 0)))
            original_price = float(item.get("original_price", price))
            sales_30d = int(item.get("sales_30d", item.get("sales_count", 0)))
            gmv_30d = float(item.get("gmv_30d", 0))
            refund_rate = float(item.get("refund_rate", 0.0))
            creator_count = int(item.get("creator_count", 0))

            return ProductData(
                product_id=str(product_id) if product_id else "",
                product_name=product_name,
                category=category or "",
                price=price,
                original_price=original_price,
                sales_30d=sales_30d,
                gmv_30d=gmv_30d,
                refund_rate=refund_rate,
                creator_count=creator_count,
                raw_data=item,
            )
        except Exception as e:
            print(f"解析商品数据失败: {e}")
            return None

    def fetch_trend(
        self,
        category: str,
        days: int = 60,
    ) -> List[TrendData]:
        """
        从 FastMoss 获取趋势数据
        
        FastMoss 没有直接的类目趋势接口，
        这里返回空列表，需要通过商品销量趋势来间接获取
        """
        return []

    def get_cost_summary(self) -> Optional[Dict[str, Any]]:
        """获取成本统计"""
        if self._client:
            return self._client.get_cost_summary()
        return None


DataSourceFactory.register(DataSourceType.FASTMOSS, FastMossDataSource)


def create_data_source(
    source_type: str = "csv",
    **kwargs,
) -> DataSource:
    """
    创建数据源实例的便捷函数

    Args:
        source_type: 数据源类型 ('csv', 'fastmoss', 'kalodata')
        **kwargs: 传递给数据源构造函数的参数

    Returns:
        数据源实例
    """
    type_map = {
        "csv": DataSourceType.CSV,
        "fastmoss": DataSourceType.FASTMOSS,
        "kalodata": DataSourceType.KALODATA,
    }

    st = type_map.get(source_type.lower())
    if st is None:
        raise ValueError(f"Unsupported data source: {source_type}")

    return DataSourceFactory.create(st, **kwargs)
