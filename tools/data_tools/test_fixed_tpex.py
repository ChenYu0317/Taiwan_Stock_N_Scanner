#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試修復後的 TPEx 功能
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

def test_fixed_tpex():
    """測試修復後的 TPEx 功能"""
    
    logger.info("🧪 測試修復後的 TPEx 功能")
    
    pipeline = TaiwanStockPriceDataPipeline()
    
    # 測試環球晶 6488
    stock_id = "6488"
    market = "TPEx"
    target_bars = 40
    
    logger.info(f"📊 測試 {stock_id} ({market}) - 目標: {target_bars} 根K線")
    
    success = pipeline.fetch_stock_historical_data(stock_id, market, target_bars)
    
    if success:
        # 查詢結果
        conn = sqlite3.connect(pipeline.db_path)
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
            logger.info(f"🏪 市場: {df['market'].unique()}")
            
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

if __name__ == "__main__":
    test_fixed_tpex()