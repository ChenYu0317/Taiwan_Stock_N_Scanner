#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次股票測試 - 測試多檔股票和 TPEx 功能
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

def test_batch_stocks():
    """測試批次股票抓取"""
    
    # 測試股票清單 (混合上市/上櫃)
    test_stocks = [
        ("2330", "台積電", "TWSE"),
        ("2454", "聯發科", "TWSE"), 
        ("1101", "台泥", "TWSE"),
        ("6488", "環球晶", "TPEx"),  # 上櫃測試
        ("3034", "聯詠", "TWSE"),
    ]
    
    logger.info(f"🧪 批次測試 {len(test_stocks)} 檔股票")
    
    pipeline = TaiwanStockPriceDataPipeline()
    results = []
    
    for stock_id, name, market in test_stocks:
        logger.info(f"\n📊 測試 {stock_id} ({name}) - {market}")
        
        try:
            success = pipeline.fetch_stock_historical_data(stock_id, market, 40)
            
            if success:
                # 查詢結果
                conn = sqlite3.connect(pipeline.db_path)
                df = pd.read_sql_query("""
                    SELECT COUNT(*) as count, MIN(date) as min_date, MAX(date) as max_date, 
                           source, market
                    FROM daily_prices 
                    WHERE stock_id = ?
                    GROUP BY source, market
                """, conn, params=(stock_id,))
                conn.close()
                
                if not df.empty:
                    total_records = df['count'].sum()
                    logger.info(f"✅ {stock_id}: {total_records} 筆 ({df.iloc[0]['min_date']} ~ {df.iloc[0]['max_date']})")
                    logger.info(f"   來源: {df.iloc[0]['source']}, 市場: {df.iloc[0]['market']}")
                    
                    results.append({
                        'stock_id': stock_id,
                        'name': name,
                        'market': market,
                        'records': total_records,
                        'success': True,
                        'source': df.iloc[0]['source']
                    })
                else:
                    logger.warning(f"❌ {stock_id}: 無數據")
                    results.append({
                        'stock_id': stock_id, 'name': name, 'market': market,
                        'records': 0, 'success': False, 'source': None
                    })
            else:
                logger.error(f"❌ {stock_id}: 抓取失敗")
                results.append({
                    'stock_id': stock_id, 'name': name, 'market': market, 
                    'records': 0, 'success': False, 'source': None
                })
                
        except Exception as e:
            logger.error(f"❌ {stock_id}: 異常 - {e}")
            results.append({
                'stock_id': stock_id, 'name': name, 'market': market,
                'records': 0, 'success': False, 'source': None
            })
    
    # 測試結果總結
    logger.info("\n" + "="*60)
    logger.info("📊 批次測試結果總結")
    logger.info("="*60)
    
    success_count = sum(1 for r in results if r['success'])
    total_records = sum(r['records'] for r in results)
    
    logger.info(f"✅ 成功率: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
    logger.info(f"📊 總數據: {total_records} 筆記錄")
    
    # 按市場分組
    twse_results = [r for r in results if r['market'] == 'TWSE']
    tpex_results = [r for r in results if r['market'] == 'TPEx']
    
    logger.info(f"🏢 TWSE: {sum(1 for r in twse_results if r['success'])}/{len(twse_results)} 成功")
    logger.info(f"🏪 TPEx: {sum(1 for r in tpex_results if r['success'])}/{len(tpex_results)} 成功")
    
    # 詳細結果
    for r in results:
        status = "✅" if r['success'] else "❌"
        logger.info(f"{status} {r['stock_id']} ({r['name']}) - {r['market']}: {r['records']} 筆, 來源: {r['source']}")

def test_freshness_check():
    """測試新鮮度檢查功能"""
    logger.info("\n" + "="*60)
    logger.info("🔍 測試新鮮度檢查功能")
    logger.info("="*60)
    
    pipeline = TaiwanStockPriceDataPipeline()
    
    # 測試已存在的股票 (2330應該已經抓取過)
    is_fresh = pipeline.is_fresh_enough("2330", 60, 7)
    logger.info(f"💾 2330 新鮮度檢查: {'夠新' if is_fresh else '需更新'}")
    
    # 測試不存在的股票
    is_fresh = pipeline.is_fresh_enough("9999", 60, 7)
    logger.info(f"💾 9999 新鮮度檢查: {'夠新' if is_fresh else '需更新'}")

def test_database_summary():
    """測試資料庫統計總結"""
    logger.info("\n" + "="*60)
    logger.info("💾 資料庫統計總結")
    logger.info("="*60)
    
    pipeline = TaiwanStockPriceDataPipeline()
    conn = sqlite3.connect(pipeline.db_path)
    
    # 總體統計
    stats = conn.execute("""
        SELECT 
            COUNT(DISTINCT stock_id) as unique_stocks,
            COUNT(*) as total_records,
            MIN(date) as earliest_date,
            MAX(date) as latest_date,
            COUNT(DISTINCT market) as markets,
            COUNT(DISTINCT source) as sources
        FROM daily_prices
    """).fetchone()
    
    logger.info(f"📊 總覽: {stats[0]} 檔股票, {stats[1]} 筆記錄")
    logger.info(f"📅 時間跨度: {stats[2]} ~ {stats[3]}")
    logger.info(f"🏢 市場數: {stats[4]}, 來源數: {stats[5]}")
    
    # 按市場統計
    market_stats = conn.execute("""
        SELECT market, COUNT(DISTINCT stock_id) as stocks, COUNT(*) as records
        FROM daily_prices
        GROUP BY market
        ORDER BY records DESC
    """).fetchall()
    
    for market, stocks, records in market_stats:
        logger.info(f"📈 {market}: {stocks} 檔股票, {records} 筆記錄")
    
    # 按來源統計
    source_stats = conn.execute("""
        SELECT source, COUNT(*) as records
        FROM daily_prices
        GROUP BY source
        ORDER BY records DESC
    """).fetchall()
    
    for source, records in source_stats:
        logger.info(f"🔗 {source}: {records} 筆記錄")
    
    conn.close()

if __name__ == "__main__":
    test_batch_stocks()
    test_freshness_check()
    test_database_summary()