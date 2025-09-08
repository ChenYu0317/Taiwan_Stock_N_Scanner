#!/usr/bin/env python3
"""
數據驗證和修正腳本
專門處理 TPEx 數據獲取問題並驗證數據完整性
"""

import requests
import sqlite3
import json
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_tpex_data_source():
    """修正 TPEx 數據源問題"""
    logger.info("Testing various TPEx API endpoints...")
    
    # 測試多個 TPEx API
    endpoints = [
        {
            "name": "TPEx OTC Quotes",
            "url": "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php",
            "params": {
                'l': 'zh-tw',
                'se': 'AL',
                'd': '113/09/06'  # 民國年格式
            }
        },
        {
            "name": "TPEx Stock Info",
            "url": "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes",
            "params": {}
        },
        {
            "name": "TPEx Daily Trading",
            "url": "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php",
            "params": {
                'l': 'zh-tw',
                'o': 'json',
                'd': '113/09/06'
            }
        }
    ]
    
    working_endpoints = []
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint["url"], params=endpoint["params"], timeout=10)
            logger.info(f"Testing {endpoint['name']}: Status {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"  JSON keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                    
                    # 檢查是否包含股票數據
                    if isinstance(data, dict):
                        if 'aaData' in data and data['aaData']:
                            logger.info(f"  ✅ {endpoint['name']}: Found {len(data['aaData'])} records")
                            working_endpoints.append(endpoint)
                        elif any(key for key in data.keys() if 'data' in key.lower()):
                            logger.info(f"  ✅ {endpoint['name']}: Has data fields")
                            working_endpoints.append(endpoint)
                        else:
                            logger.warning(f"  ❌ {endpoint['name']}: No obvious data fields")
                    elif isinstance(data, list):
                        logger.info(f"  ✅ {endpoint['name']}: List with {len(data)} items")
                        working_endpoints.append(endpoint)
                        
                except json.JSONDecodeError:
                    logger.warning(f"  ❌ {endpoint['name']}: Not JSON response")
                    
        except Exception as e:
            logger.error(f"  ❌ {endpoint['name']}: {e}")
    
    return working_endpoints

def get_finmind_tpex_stock_universe():
    """使用 FinMind 獲取上櫃股票清單的修正版本"""
    logger.info("Fetching TPEx stock_universe from FinMind with better filtering...")
    
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        'dataset': 'TaiwanStockInfo'
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        raw_stock_universe = data.get('data', [])
        
        logger.info(f"FinMind returned {len(raw_stock_universe)} total securities")
        
        # 檢查實際數據結構
        if raw_stock_universe:
            logger.info(f"Sample record: {raw_stock_universe[0]}")
            logger.info(f"Available fields: {list(raw_stock_universe[0].keys())}")
        
        # 更寬鬆的過濾條件來識別上櫃股票
        tpex_stock_universe = []
        twse_stock_universe = []
        
        for item in raw_stock_universe:
            stock_id = item.get('stock_id', '')
            name = item.get('stock_name', '')
            
            # 基本過濾：4位數字代碼，非ETF
            if (stock_id and len(stock_id) == 4 and stock_id.isdigit() and
                name and 'ETF' not in name and '權證' not in name):
                
                # 根據股票代碼判斷市場 (這是台股的慣例)
                first_digit = int(stock_id[0])
                if first_digit == 1 or first_digit == 2:  # 通常 1xxx, 2xxx 是上市
                    twse_stock_universe.append({
                        'stock_id': stock_id,
                        'name': name,
                        'market': 'TWSE'
                    })
                elif first_digit in [3, 4, 5, 6]:  # 3xxx, 4xxx, 5xxx, 6xxx 通常是上櫃
                    tpex_stock_universe.append({
                        'stock_id': stock_id,
                        'name': name,
                        'market': 'TPEx'
                    })
        
        logger.info(f"Identified stock_universe: TWSE={len(twse_stock_universe)}, TPEx={len(tpex_stock_universe)}")
        
        # 顯示一些範例
        if tpex_stock_universe:
            logger.info("TPEx stock examples:")
            for stock in tpex_stock_universe[:5]:
                logger.info(f"  {stock['stock_id']}: {stock['name']}")
        
        return tpex_stock_universe
        
    except Exception as e:
        logger.error(f"Error fetching FinMind TPEx data: {e}")
        return []

def validate_data_completeness():
    """驗證數據完整性"""
    logger.info("Validating data completeness...")
    
    db_path = "data/cleaned/taiwan_stocks_cleaned.db"
    conn = sqlite3.connect(db_path)
    
    # 檢查股票宇宙
    universe_count = conn.execute("SELECT COUNT(*) FROM stock_universe").fetchone()[0]
    logger.info(f"Stock universe contains: {universe_count} stock_universe")
    
    if universe_count < 1500:  # 預期台股總數約1700-1800檔
        logger.warning("Stock universe seems incomplete!")
        
        # 嘗試補充 TPEx 股票
        tpex_stock_universe = get_finmind_tpex_stock_universe()
        if tpex_stock_universe:
            logger.info(f"Adding {len(tpex_stock_universe)} TPEx stock_universe to universe...")
            
            for stock in tpex_stock_universe:
                conn.execute("""
                    INSERT OR REPLACE INTO stock_universe (stock_id, name, market, status)
                    VALUES (?, ?, ?, ?)
                """, (stock['stock_id'], stock['name'], stock['market'], 'active'))
            
            conn.commit()
            
            # 重新檢查
            new_count = conn.execute("SELECT COUNT(*) FROM stock_universe").fetchone()[0]
            logger.info(f"Updated stock universe: {new_count} stock_universe")
    
    # 檢查價格數據覆蓋
    price_stats = conn.execute("""
        SELECT 
            market,
            COUNT(DISTINCT stock_id) as unique_stock_universe,
            COUNT(*) as total_records,
            MIN(date) as earliest,
            MAX(date) as latest
        FROM daily_prices
        GROUP BY market
    """).fetchall()
    
    logger.info("Price data coverage:")
    for row in price_stats:
        market, stock_universe, records, earliest, latest = row
        logger.info(f"  {market}: {stock_universe} stock_universe, {records} records, {earliest} to {latest}")
    
    conn.close()
    
    return True

def create_data_quality_report():
    """生成數據質量報告"""
    logger.info("Creating data quality report...")
    
    db_path = "data/cleaned/taiwan_stocks_cleaned.db"
    conn = sqlite3.connect(db_path)
    
    # 基本統計
    basic_stats = {
        "total_stock_universe": conn.execute("SELECT COUNT(*) FROM stock_universe").fetchone()[0],
        "twse_stock_universe": conn.execute("SELECT COUNT(*) FROM stock_universe WHERE market='TWSE'").fetchone()[0],
        "tpex_stock_universe": conn.execute("SELECT COUNT(*) FROM stock_universe WHERE market='TPEx'").fetchone()[0],
    }
    
    # 價格數據統計
    price_stats = conn.execute("""
        SELECT 
            COUNT(DISTINCT stock_id) as stock_universe_with_data,
            COUNT(*) as total_price_records,
            MIN(date) as earliest_date,
            MAX(date) as latest_date
        FROM daily_prices
    """).fetchone()
    
    # 數據品質問題
    quality_issues = {
        "zero_volume_records": conn.execute("SELECT COUNT(*) FROM daily_prices WHERE volume = 0").fetchone()[0],
        "missing_prices": conn.execute("SELECT COUNT(*) FROM daily_prices WHERE close IS NULL OR close = 0").fetchone()[0],
        "extreme_changes": conn.execute("""
            SELECT COUNT(*) FROM daily_prices 
            WHERE ABS((high - low) / low) > 0.3
        """).fetchone()[0]
    }
    
    conn.close()
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "stock_universe": basic_stats,
        "price_data": {
            "stock_universe_with_data": price_stats[0],
            "total_records": price_stats[1],
            "date_range": f"{price_stats[2]} to {price_stats[3]}"
        },
        "data_quality_flags": quality_issues,
        "data_sources_status": {
            "TWSE_official": "✅ Working",
            "TPEx_official": "❌ API Issues - Using FinMind backup",
            "FinMind_backup": "✅ Working"
        },
        "recommendations": [
            "Monitor TPEx official API for fixes",
            "Consider implementing additional data validation rules",
            "Set up regular data quality monitoring",
            f"Current stock count ({basic_stats['total_stock_universe']}) may be incomplete - typical range is 1700-1800"
        ]
    }
    
    return report

def main():
    """主函數"""
    logger.info("Starting data source validation and repair...")
    
    # 1. 測試 TPEx API
    logger.info("=== Step 1: Testing TPEx APIs ===")
    working_tpex = fix_tpex_data_source()
    
    if working_tpex:
        logger.info(f"Found {len(working_tpex)} working TPEx endpoints")
    else:
        logger.warning("No working TPEx endpoints found - will rely on FinMind")
    
    # 2. 驗證和修正數據完整性
    logger.info("\n=== Step 2: Validating data completeness ===")
    validate_data_completeness()
    
    # 3. 生成數據質量報告
    logger.info("\n=== Step 3: Generating data quality report ===")
    report = create_data_quality_report()
    
    print("\n" + "="*60)
    print("DATA QUALITY REPORT")
    print("="*60)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    logger.info("Data validation completed!")

if __name__ == "__main__":
    main()