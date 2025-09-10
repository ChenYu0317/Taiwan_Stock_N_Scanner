#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
單檔股票價格數據抓取測試
"""

import sys
import os
sys.path.insert(0, 'src/data')

from price_data_pipeline import TaiwanStockPriceDataPipeline
import sqlite3
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_single_stock(stock_id="2330", market="TWSE", target_bars=60):
    """測試單一股票抓取"""
    
    logger.info(f"🧪 測試 {stock_id} ({market}) - 目標: {target_bars} 根K線")
    
    # 創建管線實例
    pipeline = TaiwanStockPriceDataPipeline()
    
    # 測試抓取
    success = pipeline.fetch_stock_historical_data(stock_id, market, target_bars)
    
    if success:
        # 驗證結果
        conn = sqlite3.connect(pipeline.db_path)
        
        # 查詢數據
        df = pd.read_sql_query("""
            SELECT * FROM daily_prices 
            WHERE stock_id = ? 
            ORDER BY date DESC 
            LIMIT ?
        """, conn, params=(stock_id, target_bars + 10))
        
        conn.close()
        
        if len(df) > 0:
            logger.info(f"✅ 成功！獲取 {len(df)} 筆資料")
            logger.info(f"📅 日期範圍: {df.iloc[-1]['date']} ~ {df.iloc[0]['date']}")
            logger.info(f"💰 價格範圍: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
            logger.info(f"📊 來源分布: {df['source'].value_counts().to_dict()}")
            
            # 顯示最近5筆
            logger.info("📋 最近5筆資料:")
            recent = df.head(5)[['date', 'open', 'high', 'low', 'close', 'volume', 'source']]
            for _, row in recent.iterrows():
                logger.info(f"  {row['date']}: {row['open']:.2f}→{row['close']:.2f} vol:{row['volume']:,} ({row['source']})")
            
            return True
        else:
            logger.error("❌ 資料庫中無數據")
            return False
    else:
        logger.error("❌ 抓取失敗")
        return False

def test_data_quality(stock_id="2330"):
    """測試數據品質"""
    logger.info(f"🔍 檢查 {stock_id} 數據品質...")
    
    pipeline = TaiwanStockPriceDataPipeline()
    conn = sqlite3.connect(pipeline.db_path)
    
    # 基本統計
    stats = conn.execute("""
        SELECT 
            COUNT(*) as total_records,
            MIN(date) as earliest_date,
            MAX(date) as latest_date,
            COUNT(DISTINCT source) as source_count,
            AVG(close) as avg_close,
            MIN(close) as min_close,
            MAX(close) as max_close
        FROM daily_prices WHERE stock_id = ?
    """, (stock_id,)).fetchone()
    
    logger.info(f"📊 總記錄數: {stats[0]}")
    if stats[0] > 0:
        logger.info(f"📅 時間跨度: {stats[1]} ~ {stats[2]}")
        logger.info(f"🔗 來源類型: {stats[3]} 種")
        logger.info(f"💰 價格統計: 均價 {stats[4]:.2f}, 範圍 {stats[5]:.2f}~{stats[6]:.2f}")
    else:
        logger.warning("❌ 無數據記錄")
    
    # 檢查異常
    anomalies = conn.execute("""
        SELECT COUNT(*) FROM daily_prices 
        WHERE stock_id = ? AND (
            close <= 0 OR high < close OR low > close OR 
            high < open OR low > open OR volume < 0
        )
    """, (stock_id,)).fetchone()[0]
    
    if anomalies > 0:
        logger.warning(f"⚠️ 發現 {anomalies} 筆異常數據")
    else:
        logger.info("✅ 數據品質良好")
    
    # 檢查連續性（缺漏交易日）
    gaps = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT date, 
                   LAG(date) OVER (ORDER BY date) as prev_date,
                   julianday(date) - julianday(LAG(date) OVER (ORDER BY date)) as day_gap
            FROM daily_prices 
            WHERE stock_id = ?
        ) WHERE day_gap > 7
    """, (stock_id,)).fetchone()[0]
    
    if gaps > 0:
        logger.warning(f"⚠️ 發現 {gaps} 處可能的數據缺漏（超過7天間隔）")
    else:
        logger.info("✅ 數據連續性良好")
    
    conn.close()

if __name__ == "__main__":
    # 測試台積電 (上市)
    print("=" * 60)
    print("🧪 測試 1: 台積電 (2330, TWSE)")
    print("=" * 60)
    test_single_stock("2330", "TWSE", 60)
    test_data_quality("2330")
    
    print("\n" + "=" * 60)
    print("🧪 測試 2: 聯發科 (2454, TWSE) - 小量測試")
    print("=" * 60)
    test_single_stock("2454", "TWSE", 30)
    
    print("\n" + "=" * 60)
    print("🧪 測試 3: TPEx 股票測試 (建議選個上櫃股)")
    print("=" * 60)
    # 選一檔上櫃股測試 - 如果你知道股號可以改這裡
    # test_single_stock("6488", "TPEx", 40)  # 例：環球晶
    logger.info("💡 如需測試TPEx，請提供上櫃股票代號")