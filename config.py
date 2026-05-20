"""配置管理模块"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import json

CONFIG_FILE = Path(__file__).parent / "config.json"


@dataclass
class RefundRateConfig:
    """退款率惩罚配置"""
    threshold: float = 20.0
    penalty_score: float = 10.0
    enabled: bool = True


@dataclass
class DataSourceConfig:
    """数据源配置"""
    provider: str = "csv"
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    cache_ttl_seconds: int = 3600
    rate_limit_per_minute: int = 60
    region: str = "US"
    daily_cost_limit: float = 5.0


@dataclass
class ScoringConfig:
    """评分配置"""
    weights: Dict[str, float] = field(default_factory=lambda: {
        "concentration": 0.40,
        "content_density": 0.35,
        "barrier": 0.25,
    })
    content_density_saturation: int = 2000


@dataclass
class AppConfig:
    """应用主配置"""
    refund_rate: RefundRateConfig = field(default_factory=RefundRateConfig)
    data_source: DataSourceConfig = field(default_factory=DataSourceConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)

    @classmethod
    def load(cls) -> "AppConfig":
        """从配置文件加载配置"""
        if not CONFIG_FILE.exists():
            return cls()
        
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            refund_data = data.get("refund_rate", {})
            ds_data = data.get("data_source", {})
            scoring_data = data.get("scoring", {})
            
            return cls(
                refund_rate=RefundRateConfig(
                    threshold=refund_data.get("threshold", 20.0),
                    penalty_score=refund_data.get("penalty_score", 10.0),
                    enabled=refund_data.get("enabled", True),
                ),
                data_source=DataSourceConfig(
                    provider=ds_data.get("provider", "csv"),
                    api_key=ds_data.get("api_key"),
                    api_endpoint=ds_data.get("api_endpoint"),
                    cache_ttl_seconds=ds_data.get("cache_ttl_seconds", 3600),
                    rate_limit_per_minute=ds_data.get("rate_limit_per_minute", 60),
                    region=ds_data.get("region", "US"),
                    daily_cost_limit=ds_data.get("daily_cost_limit", 5.0),
                ),
                scoring=ScoringConfig(
                    weights=scoring_data.get("weights", {
                        "concentration": 0.30,
                        "content_density": 0.25,
                        "engagement_decay": 0.20,
                        "price_competition": 0.15,
                        "barrier": 0.10,
                    }),
                    content_density_saturation=scoring_data.get("content_density_saturation", 2000),
                ),
            )
        except Exception:
            return cls()

    def save(self) -> None:
        """保存配置到文件"""
        data = {
            "refund_rate": {
                "threshold": self.refund_rate.threshold,
                "penalty_score": self.refund_rate.penalty_score,
                "enabled": self.refund_rate.enabled,
            },
            "data_source": {
                "provider": self.data_source.provider,
                "api_key": self.data_source.api_key,
                "api_endpoint": self.data_source.api_endpoint,
                "cache_ttl_seconds": self.data_source.cache_ttl_seconds,
                "rate_limit_per_minute": self.data_source.rate_limit_per_minute,
                "region": self.data_source.region,
                "daily_cost_limit": self.data_source.daily_cost_limit,
            },
            "scoring": {
                "weights": self.scoring.weights,
                "content_density_saturation": self.scoring.content_density_saturation,
            },
        }
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = AppConfig.load()
    return _config


def reload_config() -> AppConfig:
    """重新加载配置"""
    global _config
    _config = AppConfig.load()
    return _config
