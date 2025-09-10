#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
簡單修正測試 - 使用原版邏輯但稍微調整參數
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import pandas as pd
import sqlite3
from n_pattern_detector import NPatternDetector

def test_simple_fix():
    """測試簡單修正版本"""
    print("🔧 測試簡單修正版N字檢測演算法")
    print("="*50)
    
    # 使用接近原版的參數，但稍做調整
    detector = NPatternDetector(
        lookback_bars=60,
        use_dynamic_zigzag=False,     # 先用固定門檻
        zigzag_change_pct=0.018,      # 1.8%（介於1.5%和2.5%之間）
        min_leg_pct=0.05,             # 5%（比原來4%嚴格一些）
        retr_min=0.20,
        retr_max=0.80,
        c_tolerance=0.00,
        min_bars_ab=1,                # 保持原來的彈性
        max_bars_ab=50,               # 比原來80天嚴格一些
        min_bars_bc=1,
        max_bars_bc=30,               # 比原來50天嚴格一些
        max_bars_from_c=20,           # 比原來30天嚴格一些
        volume_threshold=1.0
    )
    
    print("參數設定:")
    print(f"  ZigZag門檻: {detector.zigzag_change_pct:.1%}")
    print(f"  最小漲幅: {detector.min_leg_pct:.1%}")
    print(f"  時間範圍: AB({detector.min_bars_ab}-{detector.max_bars_ab}天), BC({detector.min_bars_bc}-{detector.max_bars_bc}天)")
    print(f"  C點新鮮度: <={detector.max_bars_from_c}天")
    
    # 測試股票
    test_stocks = ['2330', '2317', '2454', '1101', '2033', '2368', '2501', '2505']
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
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
                print(f"     A: {signal.A_date} ${signal.A_price:.2f}")
                print(f"     B: {signal.B_date} ${signal.B_price:.2f}")  
                print(f"     C: {signal.C_date} ${signal.C_price:.2f}")
                print(f"     漲幅: {signal.rise_pct:.1%}, 回撤: {signal.retr_pct:.1%}")
                print(f"     時間: AB={signal.bars_ab}天, BC={signal.bars_bc}天, C新鮮度={signal.bars_c_to_signal}天")
                
                # 檢查是否符合你的"嚴格標準"
                meets_strict = (
                    signal.bars_ab >= 3 and signal.bars_ab <= 30 and
                    signal.bars_bc >= 3 and signal.bars_bc <= 15 and
                    signal.bars_c_to_signal <= 12 and
                    signal.rise_pct >= 0.06
                )
                print(f"     符合嚴格標準: {'是' if meets_strict else '否'}")
            else:
                print(f"  🔍 無符合訊號")
        
        except Exception as e:
            print(f"  ❌ 錯誤: {e}")
    
    conn.close()
    
    print(f"\n📊 測試結果：{len(test_stocks)} 檔股票中發現 {signals_found} 個N字訊號")
    return signals_found > 0

if __name__ == "__main__":
    success = test_simple_fix()
    if success:
        print("\n✅ 簡單修正版本可以運作！")
        print("💡 建議：可以在這個基礎上逐步調整參數嚴格度")
    else:
        print("\n❌ 仍有問題，需要深入檢查程式碼")