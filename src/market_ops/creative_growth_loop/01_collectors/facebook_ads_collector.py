"""Facebook Ads Performance Collector - V15素材增长闭环"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

import duckdb


@dataclass
class CreativePerformance:
    creative_id: str
    campaign_id: str
    adset_id: str
    spend: float
    impression: int
    click: int
    install: int
    ctr: float
    ipm: float
    cpi: float
    roas_d1: float
    roas_d7: float
    date: str
    project: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "campaign_id": self.campaign_id,
            "adset_id": self.adset_id,
            "spend": self.spend,
            "impression": self.impression,
            "click": self.click,
            "install": self.install,
            "ctr": self.ctr,
            "ipm": self.ipm,
            "cpi": self.cpi,
            "roas_d1": self.roas_d1,
            "roas_d7": self.roas_d7,
            "date": self.date,
            "project": self.project,
        }


class FacebookAdsCollector:
    DB_PATH = "db/facebook_performance.duckdb"
    
    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path or self.DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        conn = duckdb.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS creative_performance (
                creative_id VARCHAR,
                campaign_id VARCHAR,
                adset_id VARCHAR,
                spend DOUBLE,
                impression INTEGER,
                click INTEGER,
                install INTEGER,
                ctr DOUBLE,
                ipm DOUBLE,
                cpi DOUBLE,
                roas_d1 DOUBLE,
                roas_d7 DOUBLE,
                date VARCHAR,
                project VARCHAR,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_creative_date 
            ON creative_performance(creative_id, date)
        """)
        conn.close()
    
    def collect_from_api(self, project: str, date_range: tuple = None) -> List[CreativePerformance]:
        """从Facebook API采集数据"""
        from market_ops.clients.meta_ads import MetaAdsClient
        
        client = MetaAdsClient()
        performances = []
        
        start_date, end_date = date_range or (
            (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
            datetime.now().strftime("%Y-%m-%d")
        )
        
        try:
            data = client.get_creative_performance(project, start_date, end_date)
            for item in data:
                perf = self._parse_api_response(item, project)
                performances.append(perf)
        except Exception as e:
            print(f"API采集失败: {e}")
        
        return performances
    
    def collect_from_csv(self, csv_path: str, project: str) -> List[CreativePerformance]:
        """从CSV文件采集数据"""
        performances = []
        
        import csv
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                perf = CreativePerformance(
                    creative_id=row.get("creative_id", row.get("ad_id", "")),
                    campaign_id=row.get("campaign_id", ""),
                    adset_id=row.get("adset_id", ""),
                    spend=float(row.get("spend", 0)),
                    impression=int(float(row.get("impression", row.get("impressions", 0)))),
                    click=int(float(row.get("click", row.get("clicks", 0)))),
                    install=int(float(row.get("install", row.get("installs", 0)))),
                    ctr=float(row.get("ctr", 0)),
                    ipm=float(row.get("ipm", 0)),
                    cpi=float(row.get("cpi", 0)),
                    roas_d1=float(row.get("roas_d1", row.get("roas", 0))),
                    roas_d7=float(row.get("roas_d7", 0)),
                    date=row.get("date", datetime.now().strftime("%Y-%m-%d")),
                    project=project,
                )
                performances.append(perf)
        
        return performances
    
    def save_performances(self, performances: List[CreativePerformance]) -> int:
        """保存到DuckDB"""
        if not performances:
            return 0
        
        conn = duckdb.connect(str(self.db_path))
        
        for perf in performances:
            conn.execute("""
                INSERT INTO creative_performance 
                (creative_id, campaign_id, adset_id, spend, impression, click, 
                 install, ctr, ipm, cpi, roas_d1, roas_d7, date, project)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                perf.creative_id, perf.campaign_id, perf.adset_id,
                perf.spend, perf.impression, perf.click, perf.install,
                perf.ctr, perf.ipm, perf.cpi, perf.roas_d1, perf.roas_d7,
                perf.date, perf.project
            ])
        
        conn.close()
        return len(performances)
    
    def get_top_performers(self, metric: str = "ctr", top_pct: float = 0.1, 
                           days: int = 7) -> List[CreativePerformance]:
        """获取Top表现素材"""
        conn = duckdb.connect(str(self.db_path))
        
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        results = conn.execute("""
            SELECT * FROM creative_performance 
            WHERE date >= ?
            ORDER BY {} DESC
        """.format(metric), [start_date]).fetchall()
        
        top_count = int(len(results) * top_pct)
        top_results = results[:top_count]
        
        performances = []
        for row in top_results:
            perf = CreativePerformance(
                creative_id=row[0],
                campaign_id=row[1],
                adset_id=row[2],
                spend=row[3],
                impression=row[4],
                click=row[5],
                install=row[6],
                ctr=row[7],
                ipm=row[8],
                cpi=row[9],
                roas_d1=row[10],
                roas_d7=row[11],
                date=row[12],
                project=row[13],
            )
            performances.append(perf)
        
        conn.close()
        return performances
    
    def _parse_api_response(self, item: Dict[str, Any], project: str) -> CreativePerformance:
        """解析API响应"""
        impression = int(item.get("impressions", 0))
        click = int(item.get("clicks", 0))
        spend = float(item.get("spend", 0))
        install = int(item.get("actions", {}).get("install", 0))
        
        ctr = click / impression if impression > 0 else 0
        ipm = install * 1000 / impression if impression > 0 else 0
        cpi = spend / install if install > 0 else 0
        
        return CreativePerformance(
            creative_id=item.get("creative_id", ""),
            campaign_id=item.get("campaign_id", ""),
            adset_id=item.get("adset_id", ""),
            spend=spend,
            impression=impression,
            click=click,
            install=install,
            ctr=ctr,
            ipm=ipm,
            cpi=cpi,
            roas_d1=float(item.get("roas_d1", 0)),
            roas_d7=float(item.get("roas_d7", 0)),
            date=item.get("date", datetime.now().strftime("%Y-%m-%d")),
            project=project,
        )
    
    def get_performance_summary(self, days: int = 7) -> Dict[str, Any]:
        """获取表现汇总"""
        conn = duckdb.connect(str(self.db_path))
        
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        summary = conn.execute("""
            SELECT 
                COUNT(DISTINCT creative_id) as total_creatives,
                SUM(spend) as total_spend,
                SUM(impression) as total_impressions,
                SUM(click) as total_clicks,
                SUM(install) as total_installs,
                AVG(ctr) as avg_ctr,
                AVG(ipm) as avg_ipm,
                AVG(cpi) as avg_cpi,
                AVG(roas_d1) as avg_roas_d1
            FROM creative_performance 
            WHERE date >= ?
        """, [start_date]).fetchone()
        
        conn.close()
        
        return {
            "total_creatives": summary[0],
            "total_spend": summary[1],
            "total_impressions": summary[2],
            "total_clicks": summary[3],
            "total_installs": summary[4],
            "avg_ctr": summary[5],
            "avg_ipm": summary[6],
            "avg_cpi": summary[7],
            "avg_roas_d1": summary[8],
        }