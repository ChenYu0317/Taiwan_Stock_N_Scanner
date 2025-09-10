#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析為什麼會有不同的K線根數
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

def analyze_bar_counts():
    """分析不同股票的K線根數差異"""
    
    pipeline = TaiwanStockPriceDataPipeline()
    conn = sqlite3.connect(pipeline.db_path)
    
    # 查詢每檔股票的詳細信息
    query = """
    SELECT 
        stock_id,
        COUNT(*) as total_bars,
        MIN(date) as earliest_date,
        MAX(date) as latest_date,
        source,
        market
    FROM daily_prices 
    GROUP BY stock_id, source, market
    ORDER BY stock_id
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    logger.info("📊 股票K線根數分析")
    logger.info("=" * 60)
    
    for _, row in df.iterrows():
        logger.info(f"📈 {row['stock_id']} ({row['market']})")
        logger.info(f"   根數: {row['total_bars']} 筆")
        logger.info(f"   期間: {row['earliest_date']} ~ {row['latest_date']}")
        logger.info(f"   來源: {row['source']}")
        
        # 計算交易日數量
        start_date = pd.to_datetime(row['earliest_date'])
        end_date = pd.to_datetime(row['latest_date'])
        total_days = (end_date - start_date).days + 1
        
        logger.info(f"   總天數: {total_days} 天")
        logger.info(f"   交易日比率: {row['total_bars']}/{total_days} = {row['total_bars']/total_days:.2%}")
        logger.info("")

def analyze_fetch_logic():
    """分析抓取邏輯"""
    
    logger.info("🔍 分析抓取邏輯差異")
    logger.info("=" * 60)
    
    # 我們的測試用不同的 target_bars 參數
    test_cases = [
        ("2330", "TWSE", 60),  # 台積電要求60根
        ("2454", "TWSE", 40),  # 聯發科要求40根  
        ("1101", "TWSE", 40),  # 台泥要求40根
        ("6488", "TPEx", 40),  # 環球晶要求40根
        ("3034", "TWSE", 40),  # 聯詠要求40根
    ]
    
    logger.info("測試參數設定:")
    for stock_id, market, target in test_cases:
        logger.info(f"  {stock_id} ({market}): 目標 {target} 根")
    
    logger.info("\n但是為什麼實際結果不同？")
    
    # 檢查新鮮度檢查的影響
    pipeline = TaiwanStockPriceDataPipeline()
    
    for stock_id, market, target in test_cases:
        is_fresh = pipeline.is_fresh_enough(stock_id, target, 7)
        logger.info(f"  {stock_id}: 新鮮度檢查 = {is_fresh}")
        
        if is_fresh:
            logger.info(f"    → 跳過抓取，使用現有數據")
        else:
            logger.info(f"    → 需要抓取 {target} 根")

def check_actual_test_calls():
    """檢查實際的測試調用"""
    
    logger.info("\n🔍 檢查測試腳本的實際調用")
    logger.info("=" * 60)
    
    # 檢查 test_batch_stocks.py 中的實際調用
    try:
        with open('test_batch_stocks.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 尋找 fetch_stock_historical_data 調用
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'fetch_stock_historical_data' in line:
                logger.info(f"第 {i+1} 行: {line.strip()}")
                
        # 尋找 target_bars 設定
        for i, line in enumerate(lines):
            if 'target_bars' in line or '60' in line or '40' in line:
                if 'fetch_stock_historical_data' in line:
                    logger.info(f"調用行 {i+1}: {line.strip()}")
                    
    except Exception as e:
        logger.error(f"無法讀取測試腳本: {e}")

def check_database_history():
    """檢查數據庫歷史"""
    
    logger.info("\n📚 檢查數據庫累積歷史")
    logger.info("=" * 60)
    
    pipeline = TaiwanStockPriceDataPipeline()
    conn = sqlite3.connect(pipeline.db_path)
    
    # 查詢每檔股票的所有記錄，按時間排序
    stocks = ['2330', '2454', '1101', '6488', '3034']
    
    for stock_id in stocks:
        query = """
        SELECT date, source, ingested_at 
        FROM daily_prices 
        WHERE stock_id = ? 
        ORDER BY date
        """
        
        df = pd.read_sql_query(query, conn, params=(stock_id,))
        
        if len(df) > 0:
            logger.info(f"📈 {stock_id}: 總共 {len(df)} 筆記錄")
            logger.info(f"   最早: {df.iloc[0]['date']} ({df.iloc[0]['source']})")
            logger.info(f"   最新: {df.iloc[-1]['date']} ({df.iloc[-1]['source']})")
            
            # 檢查是否有多次抓取
            sources = df['source'].value_counts()
            logger.info(f"   來源分布: {sources.to_dict()}")
            
            # 檢查時間間隔
            df['date'] = pd.to_datetime(df['date'])
            gaps = df['date'].diff().dt.days
            weekend_gaps = gaps[(gaps > 1) & (gaps <= 3)]  # 週末
            long_gaps = gaps[gaps > 3]  # 長期間隔
            
            if len(long_gaps) > 0:
                logger.info(f"   長間隔: {len(long_gaps)} 處，最大 {long_gaps.max()} 天")
            
        logger.info("")
    
    conn.close()

if __name__ == "__main__":
    analyze_bar_counts()
    analyze_fetch_logic() 
    check_actual_test_calls()
    check_database_history()