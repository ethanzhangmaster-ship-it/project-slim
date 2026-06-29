"""AppsFlyer Performance Collector - V15素材增长闭环"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

import duckdb


@dataclass
class AppsFlyerPerformance:
    creative_id: str
    campaign_id: str
    media_source: str
    installs: int
    d1_retention: float
    d7_retention: float
    d30_retention: float
    revenue_d1: float
    revenue_d7: float
    revenue_d30: float
    arpu_d7: float
    date: str
    project: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "campaign_id": self.campaign_id,
            "media_source": self.media_source,
            "installs": self.installs,
            "d1_retention": self.d1_retention,
            "d7_retention": self.d7_retention,
            "d30_retention": self.d30_retention,
            "revenue_d1": self.revenue_d1,
            "revenue_d7": self.revenue_d7,
            "revenue_d30": self.revenue_d30,
            "arpu_d7": self.arpu_d7,
            "date": self.date,
            "project": self.project,
        }


class AppsFlyerCollector:
    DB_PATH = "db/appsflyer_performance.duckdb"
    
    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path or self.DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        conn = duckdb.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appsflyer_performance (
                creative_id VARCHAR,
                campaign_id VARCHAR,
                media_source VARCHAR,
                installs INTEGER,
                d1_retention DOUBLE,
                d7_retention DOUBLE,
                d30_retention DOUBLE,
                revenue_d1 DOUBLE,
                revenue_d7 DOUBLE,
                revenue_d30 DOUBLE,
                arpu_d7 DOUBLE,
                date VARCHAR,
                project VARCHAR,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.close()
    
    def collect_from_api(self, project: str, date_range: tuple = None) -> List[AppsFlyerPerformance]:
        """从AppsFlyer API采集数据"""
        from market_ops.clients.adjust import AdjustClient
        
        client = AdjustClient()
        performances = []
        
        start_date, end_date = date_range or (
            (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
            datetime.now().strftime("%Y-%m-%d")
        )
        
        try:
            data = client.get_creative_retention(project, start_date, end_date)
            for item in data:
                perf = self._parse_api_response(item, project)
                performances.append(perf)
        except Exception as e:
            print(f"AppsFlyer API采集失败: {e}")
        
        return performances
    
    def save_performances(self, performances: List[AppsFlyerPerformance]) -> int:
        """保存到DuckDB"""
        if not performances:
            return 0
        
        conn = duckdb.connect(str(self.db_path))
        
        for perf in performances:
            conn.execute("""
                INSERT INTO appsflyer_performance 
                (creative_id, campaign_id, media_source, installs, 
                 d1_retention, d7_retention, d30_retention,
                 revenue_d1, revenue_d7, revenue_d30, arpu_d7, date, project)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                perf.creative_id, perf.campaign_id, perf.media_source,
                perf.installs, perf.d1_retention, perf.d7_retention,
                perf.d30_retention, perf.revenue_d1, perf.revenue_d7,
                perf.revenue_d30, perf.arpu_d7, perf.date, perf.project
            ])
        
        conn.close()
        return len(performances)
    
    def get_retention_winners(self, metric: str = "d7_retention", 
                              threshold: float = 0.15, days: int = 7) -> List[AppsFlyerPerformance]:
        """获取留存赢家"""
        conn = duckdb.connect(str(self.db_path))
        
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        results = conn.execute("""
            SELECT * FROM appsflyer_performance 
            WHERE date >= ? AND {} >= ?
            ORDER BY {} DESC
        """.format(metric, metric), [start_date, threshold]).fetchall()
        
        performances = []
        for row in results:
            perf = AppsFlyerPerformance(
                creative_id=row[0],
                campaign_id=row[1],
                media_source=row[2],
                installs=row[3],
                d1_retention=row[4],
                d7_retention=row[5],
                d30_retention=row[6],
                revenue_d1=row[7],
                revenue_d7=row[8],
                revenue_d30=row[9],
                arpu_d7=row[10],
                date=row[11],
                project=row[12],
            )
            performances.append(perf)
        
        conn.close()
        return performances
    
    def _parse_api_response(self, item: Dict[str, Any], project: str) -> AppsFlyerPerformance:
        """解析API响应"""
        installs = int(item.get("installs", 0))
        
        return AppsFlyerPerformance(
            creative_id=item.get("creative_id", ""),
            campaign_id=item.get("campaign_id", ""),
            media_source=item.get("media_source", "Facebook"),
            installs=installs,
            d1_retention=float(item.get("retention_day_1", 0)),
            d7_retention=float(item.get("retention_day_7", 0)),
            d30_retention=float(item.get("retention_day_30", 0)),
            revenue_d1=float(item.get("revenue_day_1", 0)),
            revenue_d7=float(item.get("revenue_day_7", 0)),
            revenue_d30=float(item.get("revenue_day_30", 0)),
            arpu_d7=float(item.get("arpu_d7", 0)),
            date=item.get("date", datetime.now().strftime("%Y-%m-%d")),
            project=project,
        )