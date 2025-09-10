#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試平衡版演算法參數
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import pandas as pd
import sqlite3
from n_pattern_detector import NPatternDetector

def test_balanced_algorithm():
    """測試平衡版參數"""
    print("🎯 測試平衡版N字檢測演算法")
    print("="*50)
    
    # 平衡版參數：保持一定彈性，但過濾掉過於極端的情況
    detector = NPatternDetector(
        lookback_bars=60,
        use_dynamic_zigzag=True,      # 動態ZigZag門檻
        zigzag_change_pct=0.020,      # 備用固定門檻 2%
        min_leg_pct=0.05,             # 5%最小波段（比6%寬鬆）
        retr_min=0.20,
        retr_max=0.80,
        c_tolerance=0.00,
        min_bars_ab=1,                # AB段最少1天（允許快速上漲）
        max_bars_ab=40,               # AB段最多40天
        min_bars_bc=1,                # BC段最少1天（允許快速回撤）
        max_bars_bc=25,               # BC段最多25天
        max_bars_from_c=15,           # C到今天最多15天（稍嚴格一些）
        volume_threshold=1.0
    )
    
    # 測試代表性股票
    test_stocks = ['2330', '2317', '2454', '1101', '2033']
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    print(f"開始測試 {len(test_stocks)} 檔股票...")
    
    signals_found = 0
    
    for stock_id in test_stocks:
        print(f"\n🔍 測試 {stock_id}...")
        try:
            query = """
            SELECT date, open, high, low, close, volume
            FROM daily_prices 
            WHERE stock_id = ?
            ORDER BY date
            """
            df = pd.read_sql_query(query, conn, params=(stock_id,))
            
            if len(df) < 60:
                print(f"  ❌ 資料不足: {len(df)} 筆")
                continue
            
            signal = detector.detect_n_pattern(df, stock_id)
            if signal:
                signals_found += 1
                print(f"  ✅ 發現訊號！評分: {signal.score}")
                print(f"     A-B-C: {signal.A_date} -> {signal.B_date} -> {signal.C_date}")
                print(f"     上漲: {signal.rise_pct:.1%}, 回撤: {signal.retr_pct:.1%}")
                print(f"     時間: AB={signal.bars_ab}天, BC={signal.bars_bc}天, C新鮮度={signal.bars_c_to_signal}天")
                
                # 判斷是否符合"例外條件"的快速型態
                if signal.bars_ab < 3 or signal.bars_bc < 3:
                    print(f"     ⚡ 快速型態 (AB={signal.bars_ab}, BC={signal.bars_bc})")
                else:
                    print(f"     📈 標準型態")
            else:
                print(f"  🔍 無符合訊號")
        
        except Exception as e:
            print(f"  ❌ 錯誤: {e}")
    
    conn.close()
    
    print(f"\n📊 測試結果：{len(test_stocks)} 檔股票中發現 {signals_found} 個N字訊號")
    
    if signals_found > 0:
        return True
    else:
        return False

def scan_with_balanced_params():
    """使用平衡參數進行快速掃描"""
    print("\n🚀 使用平衡參數快速掃描（前50檔股票）")
    print("="*50)
    
    detector = NPatternDetector(
        lookback_bars=60,
        use_dynamic_zigzag=True,
        min_leg_pct=0.05,           # 5%（比原來的4%嚴格一些）
        min_bars_ab=1,              # 允許快速上漲
        max_bars_ab=40,
        min_bars_bc=1,              # 允許快速回撤  
        max_bars_bc=25,
        max_bars_from_c=15,         # C點新鮮度稍嚴格
    )
    
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    stock_query = """
    SELECT DISTINCT stock_id, COUNT(*) as record_count
    FROM daily_prices
    GROUP BY stock_id
    HAVING COUNT(*) >= 60
    ORDER BY stock_id
    LIMIT 50
    """
    
    stock_result = pd.read_sql_query(stock_query, conn)
    test_stocks = stock_result['stock_id'].tolist()
    
    signals = []
    
    for i, stock_id in enumerate(test_stocks):
        print(f"掃描進度: {i+1}/{len(test_stocks)}", end='\r')
        
        try:
            query = """
            SELECT date, open, high, low, close, volume
            FROM daily_prices 
            WHERE stock_id = ?
            ORDER BY date
            """
            df = pd.read_sql_query(query, conn, params=(stock_id,))
            
            signal = detector.detect_n_pattern(df, stock_id)
            if signal:
                signals.append(signal)
        
        except Exception as e:
            continue
    
    conn.close()
    
    print(f"\n🎉 掃描完成！從 {len(test_stocks)} 檔股票中發現 {len(signals)} 個N字訊號")
    
    if signals:
        print(f"\n📋 訊號列表：")
        print(f"{'股票':<6} {'評分':<4} {'C點日期':<12} {'上漲':<8} {'回撤':<8} {'AB':<4} {'BC':<4} {'型態'}")
        print("-" * 70)
        
        for signal in sorted(signals, key=lambda s: s.score, reverse=True):
            pattern_type = "快速" if signal.bars_ab < 3 or signal.bars_bc < 3 else "標準"
            print(f"{signal.stock_id:<6} {signal.score:<4} {signal.C_date:<12} {signal.rise_pct:.1%}   {signal.retr_pct:.1%}   {signal.bars_ab:<4} {signal.bars_bc:<4} {pattern_type}")

if __name__ == "__main__":
    if test_balanced_algorithm():
        scan_with_balanced_params()
    else:
        print("\n💡 建議進一步調整參數或檢查演算法")