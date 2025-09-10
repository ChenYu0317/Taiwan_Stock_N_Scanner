#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試真實數據的N字掃描
"""

import sys
import os
sys.path.insert(0, 'src/data')

from n_pattern_scanner import NPatternScanner
import sqlite3
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_real_data_scan():
    """測試真實數據掃描"""
    
    # 使用60根K線適應當前約3個月數據量
    scanner = NPatternScanner(lookback_bars=60)
    db_path = 'data/cleaned/taiwan_stocks_cleaned.db'
    
    # 檢查可用的股票表
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'stock_%' AND name != 'stock_universe'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    logger.info(f"可用股票表數量: {len(tables)}")
    
    found_patterns = 0
    scanned_count = 0
    
    for table in tables[:10]:  # 測試前10個
        stock_id = table.replace('stock_', '')
        
        # 直接從數據庫獲取數據
        conn = sqlite3.connect(db_path)
        query = f"""
        SELECT date, open, high, low, close, volume
        FROM {table}
        ORDER BY date ASC
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        logger.info(f"\n股票 {stock_id}:")
        logger.info(f"  記錄數: {len(df)}")
        if len(df) > 0:
            logger.info(f"  日期範圍: {df.iloc[0]['date']} ~ {df.iloc[-1]['date']}")
            logger.info(f"  價格範圍: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
            
            # 準備數據
            df['date'] = pd.to_datetime(df['date'])
            
            # 獲取股票名稱
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM stock_universe WHERE stock_id=?", (stock_id,))
            result = cursor.fetchone()
            stock_name = result[0] if result else "未知"
            conn.close()
            
            # 測試掃描
            try:
                result = scanner.scan_single_stock(df, stock_id, stock_name)
                scanned_count += 1
                if result:
                    found_patterns += 1
                    logger.info(f"🎯 找到N字形態!")
                    logger.info(f"  評分: {result['total_score']}")
                    logger.info(f"  上漲: {result['rise_pct']:.1%}")
                    logger.info(f"  回撤: {result['retracement_pct']:.1%}")
                    logger.info(f"  A: {result['A_date']} = {result['A_price']:.2f}")
                    logger.info(f"  B: {result['B_date']} = {result['B_price']:.2f}")
                    logger.info(f"  C: {result['C_date']} = {result['C_price']:.2f}")
                else:
                    logger.info("❌ 未找到N字形態")
            except Exception as e:
                logger.error(f"掃描失敗: {e}")
    
    logger.info(f"\n掃描結果總計: 掃描 {scanned_count} 檔股票, 找到 {found_patterns} 個N字形態")

if __name__ == "__main__":
    test_real_data_scan()