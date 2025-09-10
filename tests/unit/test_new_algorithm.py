#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試新的N字檢測演算法
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import pandas as pd
import sqlite3
from n_pattern_detector import NPatternDetector

def test_new_algorithm():
    """測試新演算法"""
    print("🔬 測試升級後的N字檢測演算法")
    print("="*50)
    
    # 使用新的參數配置
    detector = NPatternDetector(
        lookback_bars=60,
        use_dynamic_zigzag=True,      # 動態ZigZag門檻
        zigzag_change_pct=0.025,      # 固定門檻備用
        min_leg_pct=0.06,             # 6%最小波段
        retr_min=0.20,                # 20%最小回撤
        retr_max=0.80,                # 80%最大回撤
        c_tolerance=0.00,             # C不可破A
        min_bars_ab=3,                # AB段最少3天
        max_bars_ab=30,               # AB段最多30天
        min_bars_bc=3,                # BC段最少3天
        max_bars_bc=15,               # BC段最多15天
        max_bars_from_c=12,           # C到今天最多12天
        volume_threshold=1.0          # 量能門檻
    )
    
    # 連接資料庫
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    # 測試幾個具代表性的股票
    test_stocks = ['2330', '2317', '2454', '1101', '2033']  # 台積電、鴻海、聯發科、台泥、佳大
    
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
            
            # 檢測N字形態
            signal = detector.detect_n_pattern(df, stock_id)
            if signal:
                signals_found += 1
                print(f"  ✅ 發現訊號！評分: {signal.score}")
                print(f"     A: {signal.A_date} ${signal.A_price:.2f}")
                print(f"     B: {signal.B_date} ${signal.B_price:.2f}")
                print(f"     C: {signal.C_date} ${signal.C_price:.2f}")
                print(f"     上漲: {signal.rise_pct:.1%}, 回撤: {signal.retr_pct:.1%}")
                print(f"     AB段: {signal.bars_ab}天, BC段: {signal.bars_bc}天")
                print(f"     C到訊號: {signal.bars_c_to_signal}天")
            else:
                print(f"  🔍 無符合訊號")
        
        except Exception as e:
            print(f"  ❌ 錯誤: {e}")
    
    conn.close()
    
    print(f"\n📊 測試結果：{test_stocks} 中發現 {signals_found} 個N字訊號")
    
    if signals_found > 0:
        print("\n🚀 演算法升級成功！開始全市場掃描...")
        return True
    else:
        print("\n⚠️  測試股票中未發現訊號，可能需要調整參數")
        return False

def scan_full_market():
    """全市場掃描"""
    print("\n" + "="*60)
    print("🌍 全市場N字訊號掃描（升級版演算法）")
    print("="*60)
    
    detector = NPatternDetector(
        lookback_bars=60,
        use_dynamic_zigzag=True,
        min_leg_pct=0.06,
        min_bars_ab=3,
        max_bars_ab=30,
        min_bars_bc=3,
        max_bars_bc=15,
        max_bars_from_c=12,
    )
    
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    # 獲取所有股票
    stock_query = """
    SELECT DISTINCT stock_id, COUNT(*) as record_count
    FROM daily_prices
    GROUP BY stock_id
    HAVING COUNT(*) >= 60
    ORDER BY stock_id
    """
    
    stock_result = pd.read_sql_query(stock_query, conn)
    all_stocks = stock_result['stock_id'].tolist()
    
    print(f"開始掃描 {len(all_stocks)} 檔股票...")
    
    signals = []
    
    for i, stock_id in enumerate(all_stocks):
        if i % 20 == 0:
            print(f"進度: {i}/{len(all_stocks)} ({i/len(all_stocks)*100:.1f}%)")
        
        try:
            query = """
            SELECT date, open, high, low, close, volume
            FROM daily_prices 
            WHERE stock_id = ?
            ORDER BY date
            """
            df = pd.read_sql_query(query, conn, params=(stock_id,))
            
            if len(df) < 60:
                continue
            
            signal = detector.detect_n_pattern(df, stock_id)
            if signal:
                signals.append(signal)
                print(f"✅ {stock_id}: 評分{signal.score}, AB:{signal.bars_ab}天, BC:{signal.bars_bc}天")
        
        except Exception as e:
            continue
    
    conn.close()
    
    print(f"\n🎉 掃描完成！共發現 {len(signals)} 個N字訊號")
    
    if signals:
        # 按評分排序
        sorted_signals = sorted(signals, key=lambda s: s.score, reverse=True)
        
        print(f"\n🏆 前10名高分訊號：")
        print(f"{'股票':<6} {'評分':<4} {'C點日期':<12} {'上漲':<8} {'回撤':<8} {'AB天':<5} {'BC天':<5}")
        print("-" * 60)
        
        for signal in sorted_signals[:10]:
            print(f"{signal.stock_id:<6} {signal.score:<4} {signal.C_date:<12} {signal.rise_pct:.1%}   {signal.retr_pct:.1%}   {signal.bars_ab:<5} {signal.bars_bc:<5}")

if __name__ == "__main__":
    # 先測試代表性股票
    if test_new_algorithm():
        # 如果測試成功，進行全市場掃描
        scan_full_market()
    else:
        print("\n🛠️  建議檢查參數設定或演算法邏輯")