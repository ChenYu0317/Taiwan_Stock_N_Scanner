#!/usr/bin/env python3
"""
台股數據管道 - 完整的數據獲取和處理
基於測試結果建立穩定的數據獲取機制
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import re
import sqlite3
from pathlib import Path
import logging

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TaiwanStockDataPipeline:
    """台股數據管道"""
    
    def __init__(self, db_path="taiwan_stocks.db"):
        self.db_path = db_path
        self.init_database()
        
    def init_database(self):
        """初始化資料庫"""
        conn = sqlite3.connect(self.db_path)
        
        # 股票基本資料表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_universe (
                stock_id TEXT PRIMARY KEY,
                name TEXT,
                market TEXT,  -- TWSE/TPEx
                industry TEXT,
                listing_date DATE,
                status TEXT,  -- active/suspended/delisted
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 日K線數據表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_prices (
                stock_id TEXT,
                date DATE,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                turnover INTEGER,
                market TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (stock_id, date)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")

    def fetch_twse_stock_universe(self):
        """獲取上市股票清單"""
        logger.info("Fetching TWSE stock universe...")
        
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Fetched {len(data)} TWSE securities")
            
            # 過濾純股票
            stocks = []
            etf_keywords = ['ETF', 'ETN', '受益憑證', '權證', 'DR', '特別股', '基金']
            
            for item in data:
                code = item.get('Code', '')
                name = item.get('Name', '')
                
                # 排除規則
                is_etf = any(keyword in name for keyword in etf_keywords)
                is_warrant = code.startswith('0')  # 權證
                is_bond = code.startswith('8')     # 公司債
                
                if not (is_etf or is_warrant or is_bond) and len(code) == 4:
                    stocks.append({
                        'stock_id': code,
                        'name': name,
                        'market': 'TWSE',
                        'status': 'active'
                    })
            
            logger.info(f"Filtered to {len(stocks)} TWSE stocks")
            return stocks
            
        except Exception as e:
            logger.error(f"Error fetching TWSE universe: {e}")
            return []

    def fetch_tpex_stock_universe(self):
        """獲取上櫃股票清單"""
        logger.info("Fetching TPEx stock universe...")
        
        # 使用股票資訊API
        url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
        
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"TPEx API response keys: {list(data.keys())}")
            
            stocks = []
            if data:
                # 假設返回的是股票列表
                for item in data:
                    if isinstance(item, dict):
                        code = item.get('Code') or item.get('SecuritiesCode')
                        name = item.get('Name') or item.get('SecuritiesName')
                        
                        if code and name:
                            stocks.append({
                                'stock_id': code,
                                'name': name,
                                'market': 'TPEx',
                                'status': 'active'
                            })
                
            logger.info(f"Fetched {len(stocks)} TPEx stocks")
            return stocks
            
        except Exception as e:
            logger.error(f"Error fetching TPEx universe: {e}")
            
            # 備用：使用 FinMind 獲取上櫃股票
            logger.info("Trying FinMind as backup for TPEx stocks...")
            return self.fetch_finmind_stock_universe(market='TPEx')

    def fetch_finmind_stock_universe(self, market=None):
        """使用 FinMind 獲取股票清單"""
        logger.info(f"Fetching stock universe from FinMind (market={market})...")
        
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            'dataset': 'TaiwanStockInfo'
        }
        
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            raw_stocks = data.get('data', [])
            logger.info(f"FinMind returned {len(raw_stocks)} securities")
            
            stocks = []
            for item in raw_stocks:
                stock_id = item.get('stock_id', '')
                name = item.get('stock_name', '')
                industry = item.get('industry_category', '')
                market_type = item.get('market', '')
                
                # 只保留股票（排除 ETF 等）
                if (stock_id and name and 
                    len(stock_id) == 4 and 
                    stock_id.isdigit() and 
                    'ETF' not in name and
                    '權證' not in name):
                    
                    # 判斷市場
                    if market_type in ['TWSE', 'TPEx'] or market is None:
                        target_market = market_type if market_type else market
                        
                        stocks.append({
                            'stock_id': stock_id,
                            'name': name,
                            'market': target_market or 'TWSE',
                            'industry': industry,
                            'status': 'active'
                        })
            
            if market:
                stocks = [s for s in stocks if s['market'] == market]
            
            logger.info(f"Filtered to {len(stocks)} stocks for market {market}")
            return stocks
            
        except Exception as e:
            logger.error(f"Error fetching FinMind universe: {e}")
            return []

    def update_stock_universe(self):
        """更新股票宇宙"""
        logger.info("Updating stock universe...")
        
        # 獲取上市股票
        twse_stocks = self.fetch_twse_stock_universe()
        time.sleep(1)
        
        # 獲取上櫃股票  
        tpex_stocks = self.fetch_tpex_stock_universe()
        time.sleep(1)
        
        # 如果 TPEx API 失敗，使用 FinMind 補充
        if not tpex_stocks:
            logger.warning("TPEx API failed, using FinMind backup...")
            tpex_stocks = self.fetch_finmind_stock_universe(market='TPEx')
        
        # 合併數據
        all_stocks = twse_stocks + tpex_stocks
        
        if not all_stocks:
            logger.error("No stocks fetched from any source!")
            return False
        
        # 更新資料庫
        conn = sqlite3.connect(self.db_path)
        
        try:
            # 清空舊數據
            conn.execute("DELETE FROM stock_universe")
            
            # 插入新數據
            for stock in all_stocks:
                conn.execute("""
                    INSERT INTO stock_universe (stock_id, name, market, industry, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    stock['stock_id'],
                    stock['name'],
                    stock['market'],
                    stock.get('industry', ''),
                    stock['status']
                ))
            
            conn.commit()
            logger.info(f"Updated stock universe: {len(all_stocks)} stocks")
            
            # 統計
            stats = conn.execute("""
                SELECT market, COUNT(*) 
                FROM stock_universe 
                GROUP BY market
            """).fetchall()
            
            for market, count in stats:
                logger.info(f"  {market}: {count} stocks")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating database: {e}")
            return False
        finally:
            conn.close()

    def fetch_stock_daily_data(self, stock_id, start_date, end_date):
        """獲取個股日K數據（使用FinMind）"""
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            'dataset': 'TaiwanStockPrice',
            'data_id': stock_id,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            records = data.get('data', [])
            
            processed = []
            for record in records:
                processed.append({
                    'stock_id': stock_id,
                    'date': record['date'],
                    'open': float(record['open']),
                    'high': float(record['max']),
                    'low': float(record['min']),
                    'close': float(record['close']),
                    'volume': int(record['Trading_Volume']),
                    'turnover': int(record.get('Trading_turnover', 0))
                })
            
            return processed
            
        except Exception as e:
            logger.error(f"Error fetching data for {stock_id}: {e}")
            return []

    def backfill_historical_data(self, days_back=1095):  # 3年
        """回補歷史數據"""
        logger.info(f"Starting historical data backfill ({days_back} days)...")
        
        # 獲取股票清單
        conn = sqlite3.connect(self.db_path)
        stocks = conn.execute("SELECT stock_id, market FROM stock_universe").fetchall()
        conn.close()
        
        if not stocks:
            logger.error("No stocks in universe!")
            return False
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"Backfilling from {start_date} to {end_date} for {len(stocks)} stocks")
        
        success_count = 0
        conn = sqlite3.connect(self.db_path)
        
        for i, (stock_id, market) in enumerate(stocks):
            if i % 50 == 0:
                logger.info(f"Progress: {i}/{len(stocks)} stocks")
            
            # 獲取數據
            records = self.fetch_stock_daily_data(stock_id, start_date, end_date)
            
            if records:
                try:
                    # 插入數據
                    for record in records:
                        conn.execute("""
                            INSERT OR REPLACE INTO daily_prices 
                            (stock_id, date, open, high, low, close, volume, turnover, market)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            record['stock_id'], record['date'], record['open'],
                            record['high'], record['low'], record['close'],
                            record['volume'], record['turnover'], market
                        ))
                    
                    success_count += 1
                    
                    if success_count % 10 == 0:
                        conn.commit()  # 定期提交
                        
                except Exception as e:
                    logger.error(f"Error inserting data for {stock_id}: {e}")
            
            # 避免請求過快
            time.sleep(0.2)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Backfill completed: {success_count}/{len(stocks)} stocks successful")
        return success_count > len(stocks) * 0.8  # 80% 成功率

    def get_data_summary(self):
        """獲取數據摘要"""
        conn = sqlite3.connect(self.db_path)
        
        # 股票宇宙統計
        universe_stats = conn.execute("""
            SELECT market, COUNT(*) as count
            FROM stock_universe
            GROUP BY market
        """).fetchall()
        
        # 數據覆蓋統計
        price_stats = conn.execute("""
            SELECT 
                market,
                COUNT(DISTINCT stock_id) as stocks_with_data,
                COUNT(*) as total_records,
                MIN(date) as earliest_date,
                MAX(date) as latest_date
            FROM daily_prices
            GROUP BY market
        """).fetchall()
        
        conn.close()
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "stock_universe": dict(universe_stats),
            "price_data_coverage": {
                row[0]: {
                    "stocks": row[1],
                    "records": row[2], 
                    "date_range": f"{row[3]} to {row[4]}"
                }
                for row in price_stats
            }
        }
        
        return summary

def main():
    """主函數 - 數據管道測試"""
    logger.info("Starting Taiwan Stock Data Pipeline...")
    
    pipeline = TaiwanStockDataPipeline()
    
    # 1. 更新股票宇宙
    logger.info("Step 1: Updating stock universe...")
    if not pipeline.update_stock_universe():
        logger.error("Failed to update stock universe!")
        return
    
    # 2. 測試少量股票的歷史數據
    logger.info("Step 2: Testing historical data for sample stocks...")
    test_stocks = ['2330', '2317', '2454']  # 台積電、鴻海、聯發科
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)  # 測試一個月
    
    conn = sqlite3.connect(pipeline.db_path)
    for stock_id in test_stocks:
        records = pipeline.fetch_stock_daily_data(stock_id, start_date, end_date)
        if records:
            logger.info(f"✅ {stock_id}: {len(records)} records")
            
            # 插入測試數據
            for record in records:
                conn.execute("""
                    INSERT OR REPLACE INTO daily_prices 
                    (stock_id, date, open, high, low, close, volume, turnover, market)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record['stock_id'], record['date'], record['open'],
                    record['high'], record['low'], record['close'],
                    record['volume'], record['turnover'], 'TEST'
                ))
        else:
            logger.error(f"❌ {stock_id}: No data")
    
    conn.commit()
    conn.close()
    
    # 3. 顯示數據摘要
    logger.info("Step 3: Data summary...")
    summary = pipeline.get_data_summary()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    
    logger.info("Taiwan Stock Data Pipeline test completed!")

if __name__ == "__main__":
    main()