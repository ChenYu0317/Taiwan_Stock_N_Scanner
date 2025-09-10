#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
調試新演算法 - 找出問題所在
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import pandas as pd
import sqlite3
from n_pattern_detector import NPatternDetector

def debug_single_stock(stock_id='2330'):
    """調試單一股票，看看各階段的篩選狀況"""
    print(f"🔬 詳細調試股票 {stock_id}")
    print("="*50)
    
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    query = """
    SELECT date, open, high, low, close, volume
    FROM daily_prices 
    WHERE stock_id = ?
    ORDER BY date
    """
    df = pd.read_sql_query(query, conn, params=(stock_id,))
    conn.close()
    
    print(f"資料筆數: {len(df)}")
    print(f"日期範圍: {df.iloc[0]['date']} ~ {df.iloc[-1]['date']}")
    
    # 測試不同嚴格度的參數
    configs = [
        {
            "name": "原版參數",
            "params": {
                "use_dynamic_zigzag": False,
                "zigzag_change_pct": 0.015,
                "min_leg_pct": 0.04,
                "min_bars_ab": 1,
                "max_bars_ab": 80,
                "min_bars_bc": 1,
                "max_bars_bc": 50,
                "max_bars_from_c": 30,
            }
        },
        {
            "name": "中等嚴格",
            "params": {
                "use_dynamic_zigzag": True,
                "zigzag_change_pct": 0.020,
                "min_leg_pct": 0.05,
                "min_bars_ab": 2,
                "max_bars_ab": 40,
                "min_bars_bc": 2,
                "max_bars_bc": 20,
                "max_bars_from_c": 15,
            }
        },
        {
            "name": "你的嚴格版",
            "params": {
                "use_dynamic_zigzag": True,
                "zigzag_change_pct": 0.025,
                "min_leg_pct": 0.06,
                "min_bars_ab": 3,
                "max_bars_ab": 30,
                "min_bars_bc": 3,
                "max_bars_bc": 15,
                "max_bars_from_c": 12,
            }
        }
    ]
    
    for config in configs:
        print(f"\n🧪 測試配置: {config['name']}")
        print("-" * 30)
        
        detector = NPatternDetector(
            lookback_bars=60,
            volume_threshold=1.0,
            **config['params']
        )
        
        signal = detector.detect_n_pattern(df, stock_id)
        
        if signal:
            print(f"✅ 發現訊號！")
            print(f"   評分: {signal.score}")
            print(f"   A-B-C: {signal.A_date} -> {signal.B_date} -> {signal.C_date}")
            print(f"   上漲: {signal.rise_pct:.1%}, 回撤: {signal.retr_pct:.1%}")
            print(f"   時間: AB={signal.bars_ab}天, BC={signal.bars_bc}天, C到今天={signal.bars_c_to_signal}天")
        else:
            print("❌ 無訊號")
            # 嘗試找出原因
            debug_why_no_signal(detector, df, stock_id)

def debug_why_no_signal(detector, df, stock_id):
    """調試為什麼沒有訊號"""
    # 檢查ZigZag點數
    lookback_df = df.tail(detector.lookback_bars).reset_index(drop=True)
    
    # 使用動態或固定門檻
    if detector.use_dynamic_zigzag:
        from n_pattern_detector import TechnicalIndicators
        dynamic_threshold = TechnicalIndicators.dynamic_zigzag_threshold(
            lookback_df['close'], lookback_df['high'], lookback_df['low']
        )
        latest_threshold = dynamic_threshold.iloc[-1] if not pd.isna(dynamic_threshold.iloc[-1]) else detector.zigzag_change_pct
        print(f"   動態ZigZag門檻: {latest_threshold:.3f}")
        detector.zigzag = detector.__class__.__dict__['__init__'].__code__.co_names  # 這裡有問題，我需要重新實作
    else:
        print(f"   固定ZigZag門檻: {detector.zigzag_change_pct:.3f}")
    
    # 檢查ZigZag點數
    from n_pattern_detector import ZigZagDetector
    zigzag = ZigZagDetector(min_change_pct=detector.zigzag_change_pct)
    zigzag_points = zigzag.detect(lookback_df)
    
    print(f"   ZigZag轉折點數: {len(zigzag_points)}")
    
    if len(zigzag_points) >= 3:
        # 顯示最後幾個轉折點
        print("   最後3個轉折點:")
        for i, (idx, price, ptype) in enumerate(zigzag_points[-3:]):
            date = lookback_df.iloc[idx]['date']
            print(f"     {i+1}. {date} ${price:.2f} ({ptype})")
        
        # 檢查是否有L-H-L形態
        last_3 = zigzag_points[-3:]
        if len(last_3) == 3:
            types = [p[2] for p in last_3]
            print(f"   最後形態: {'-'.join(types)}")
            
            if types == ['L', 'H', 'L']:
                # 檢查各項條件
                A_price, B_price, C_price = last_3[0][1], last_3[1][1], last_3[2][1]
                rise_pct = (B_price - A_price) / A_price
                retr_pct = (B_price - C_price) / (B_price - A_price)
                
                bars_ab = last_3[1][0] - last_3[0][0]
                bars_bc = last_3[2][0] - last_3[1][0]
                bars_from_c = len(lookback_df) - 1 - last_3[2][0]
                
                print(f"   上漲幅度: {rise_pct:.1%} (需要>={detector.min_leg_pct:.1%})")
                print(f"   回撤比例: {retr_pct:.1%} (需要{detector.retr_min:.1%}~{detector.retr_max:.1%})")
                print(f"   AB段天數: {bars_ab} (需要{detector.min_bars_ab}~{detector.max_bars_ab}天)")
                print(f"   BC段天數: {bars_bc} (需要{detector.min_bars_bc}~{detector.max_bars_bc}天)")
                print(f"   C點新鮮度: {bars_from_c} (需要<={detector.max_bars_from_c}天)")
                
                # 檢查C不破A
                c_vs_a_ok = C_price >= A_price * (1 - detector.c_tolerance)
                print(f"   C不破A: {c_vs_a_ok} (C=${C_price:.2f} vs A=${A_price:.2f})")

if __name__ == "__main__":
    debug_single_stock('2330')  # 台積電
    print("\n" + "="*60)
    debug_single_stock('2033')  # 佳大 (之前有訊號)