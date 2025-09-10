#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
優化後的N字回撤偵測測試
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'signal'))
from n_pattern_detector import NPatternDetector

import pandas as pd
import sqlite3

def test_optimized_detection():
    """使用優化參數測試N字偵測"""
    print("🚀 優化後的N字回撤偵測測試")
    
    # 測試股票清單
    test_stocks = ['2330', '2454', '2881', '1101', '3008', '2891', '1303', '1326', '6505']
    
    # 使用更敏感的參數
    detector = NPatternDetector(
        lookback_bars=60,
        min_leg_pct=0.02,    # 2%最小波段 (更敏感)
        retr_min=0.20,       # 20%最小回撤
        retr_max=0.80,       # 80%最大回撤
        c_tolerance=0.05     # C點可低於A點5%
    )
    
    # 手動設置更敏感的ZigZag
    detector.zigzag.min_change_pct = 0.015  # 1.5%變化
    
    signals = []
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    for stock_id in test_stocks:
        print(f"\n📊 測試股票: {stock_id}")
        
        try:
            # 獲取股票數據
            query = """
            SELECT date, open, high, low, close, volume
            FROM daily_prices 
            WHERE stock_id = ?
            ORDER BY date
            """
            df = pd.read_sql_query(query, conn, params=(stock_id,))
            
            if len(df) < 60:
                print(f"   ❌ 數據不足: {len(df)} 筆")
                continue
            
            print(f"   📈 數據範圍: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]} ({len(df)} 筆)")
            
            # 先檢查ZigZag點數
            recent_df = df.tail(60).reset_index(drop=True)
            zigzag_points = detector.zigzag.detect(recent_df)
            print(f"   🔄 ZigZag轉折點: {len(zigzag_points)} 個")
            
            # 偵測N字形態
            signal = detector.detect_n_pattern(df, stock_id)
            
            if signal:
                signals.append(signal)
                print(f"   ✅ 找到N字訊號!")
                print(f"      A點: {signal.A_price:.2f} ({signal.A_date})")
                print(f"      B點: {signal.B_price:.2f} ({signal.B_date})")
                print(f"      C點: {signal.C_price:.2f} ({signal.C_date})")
                print(f"      漲幅: {signal.rise_pct:.1%}, 回撤: {signal.retr_pct:.1%}")
                print(f"      評分: {signal.score}/100")
                print(f"      觸發: 昨高={signal.trigger_break_yesterday_high}, EMA5量={signal.trigger_ema5_volume}, RSI={signal.trigger_rsi_strong}")
            else:
                print(f"   ❌ 未找到N字訊號")
                
                # 顯示前幾個ZigZag點幫助理解
                if len(zigzag_points) >= 3:
                    print(f"      最後3個轉折點:")
                    for i, (idx, price, type_) in enumerate(zigzag_points[-3:]):
                        date = recent_df.iloc[idx]['date']
                        print(f"        {type_} {price:.2f} ({date})")
                
        except Exception as e:
            print(f"   ⚠️ 處理錯誤: {e}")
    
    conn.close()
    
    print(f"\n📋 測試結果總結:")
    print(f"   測試股票數: {len(test_stocks)}")
    print(f"   找到訊號數: {len(signals)}")
    print(f"   命中率: {len(signals)/len(test_stocks)*100:.1f}%")
    
    if signals:
        print(f"\n🏆 發現的訊號:")
        for i, signal in enumerate(sorted(signals, key=lambda s: s.score, reverse=True), 1):
            print(f"   {i}. {signal.stock_id}: {signal.score}分")
            print(f"      {signal.A_date} A={signal.A_price:.2f}")
            print(f"      {signal.B_date} B={signal.B_price:.2f} (漲{signal.rise_pct:.1%})")
            print(f"      {signal.C_date} C={signal.C_price:.2f} (撤{signal.retr_pct:.1%})")
            print(f"      RSI={signal.rsi14:.1f}, 量比={signal.volume_ratio:.2f}")
            print()

def detailed_analysis(stock_id='2454'):
    """詳細分析特定股票"""
    print(f"\n🔍 詳細分析 {stock_id}")
    
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    query = """
    SELECT date, open, high, low, close, volume
    FROM daily_prices 
    WHERE stock_id = ?
    ORDER BY date
    """
    df = pd.read_sql_query(query, conn, params=(stock_id,))
    conn.close()
    
    # 使用優化參數
    detector = NPatternDetector(
        lookback_bars=60,
        min_leg_pct=0.02,
        retr_min=0.20,
        retr_max=0.80,
        c_tolerance=0.05
    )
    detector.zigzag.min_change_pct = 0.015
    
    recent_df = df.tail(60).reset_index(drop=True)
    zigzag_points = detector.zigzag.detect(recent_df)
    
    print(f"ZigZag轉折點 ({len(zigzag_points)} 個):")
    for i, (idx, price, type_) in enumerate(zigzag_points):
        date = recent_df.iloc[idx]['date']
        print(f"  {i+1:2d}. {type_} {price:7.2f} ({date}) [第{idx:2d}天]")
    
    # 尋找ABC
    abc_result = detector.find_last_abc_pattern(zigzag_points, recent_df)
    if abc_result:
        A_idx, B_idx, C_idx = abc_result
        print(f"\n✅ 找到ABC形態:")
        
        A_price = zigzag_points[A_idx][1]
        B_price = zigzag_points[B_idx][1]
        C_price = zigzag_points[C_idx][1]
        
        rise_pct = (B_price - A_price) / A_price
        retr_pct = (B_price - C_price) / (B_price - A_price)
        
        print(f"   A點 #{A_idx}: {A_price:.2f} ({recent_df.iloc[zigzag_points[A_idx][0]]['date']})")
        print(f"   B點 #{B_idx}: {B_price:.2f} ({recent_df.iloc[zigzag_points[B_idx][0]]['date']})")
        print(f"   C點 #{C_idx}: {C_price:.2f} ({recent_df.iloc[zigzag_points[C_idx][0]]['date']})")
        print(f"   上漲: {rise_pct:.1%}")
        print(f"   回撤: {retr_pct:.1%}")
    
    # 完整偵測
    signal = detector.detect_n_pattern(df, stock_id)
    if signal:
        print(f"\n✅ 完整訊號生成成功")
        print(f"   評分: {signal.score}/100")
        print(f"   評分詳細: {signal.score_breakdown}")
    else:
        print(f"\n❌ 完整偵測失敗 (可能觸發條件不滿足)")

if __name__ == "__main__":
    test_optimized_detection()
    detailed_analysis('2454')