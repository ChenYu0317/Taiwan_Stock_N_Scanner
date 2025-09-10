#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試放寬參數的N字掃描，看能否找到更多形態
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

def test_relaxed_scan():
    """測試放寬參數的N字掃描"""
    
    # 使用更寬鬆的參數來增加找到形態的機會
    scanner = NPatternScanner(
        lookback_bars=60,
        min_change_pct=0.05,  # 降低到5%
        retr_min=0.20,        # 回撤最小20%
        retr_max=0.80,        # 回撤最大80%
        c_tolerance=0.02      # C點容差2%
    )
    
    db_path = 'data/cleaned/taiwan_stocks_cleaned.db'
    
    # 檢查可用的股票表
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'stock_%' AND name != 'stock_universe'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    logger.info(f"開始掃描 {len(tables)} 檔股票 (放寬參數)")
    
    found_patterns = []
    scanned_count = 0
    
    for table in tables[:50]:  # 掃描前50檔
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
        
        if len(df) < 60:
            continue
            
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
                found_patterns.append(result)
                logger.info(f"🎯 找到N字形態! {stock_id} ({stock_name})")
                logger.info(f"  評分: {result['total_score']}")
                logger.info(f"  上漲: {result['rise_pct']:.1%}")
                logger.info(f"  回撤: {result['retracement_pct']:.1%}")
                logger.info(f"  A: {result['A_date']} = {result['A_price']:.2f}")
                logger.info(f"  B: {result['B_date']} = {result['B_price']:.2f}")
                logger.info(f"  C: {result['C_date']} = {result['C_price']:.2f}")
        except Exception as e:
            logger.error(f"掃描 {stock_id} 失敗: {e}")
        
        # 每10檔報告一次進度
        if scanned_count % 10 == 0:
            logger.info(f"已掃描: {scanned_count}, 找到: {len(found_patterns)} 個形態")
    
    logger.info(f"\n最終結果: 掃描 {scanned_count} 檔股票, 找到 {len(found_patterns)} 個N字形態")
    
    if found_patterns:
        logger.info(f"\n找到的形態:")
        for i, pattern in enumerate(found_patterns, 1):
            logger.info(f"{i}. {pattern['stock_id']} ({pattern['stock_name']}) - 評分: {pattern['total_score']}")

if __name__ == "__main__":
    test_relaxed_scan()