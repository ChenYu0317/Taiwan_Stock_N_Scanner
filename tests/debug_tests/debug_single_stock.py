#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
單股票N字偵測調試腳本
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'signal'))
from n_pattern_detector import NPatternDetector

import pandas as pd
import sqlite3

def debug_stock(stock_id='2330'):
    """詳細調試單一股票"""
    print(f"🔍 調試股票 {stock_id} 的N字偵測過程")
    
    # 連接資料庫
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    # 讀取股票數據
    query = """
    SELECT date, open, high, low, close, volume
    FROM daily_prices 
    WHERE stock_id = ?
    ORDER BY date
    """
    df = pd.read_sql_query(query, conn, params=(stock_id,))
    conn.close()
    
    print(f"📊 {stock_id} 基本資訊:")
    print(f"   總數據筆數: {len(df)}")
    print(f"   日期範圍: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}")
    print(f"   價格範圍: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
    
    # 使用寬鬆的參數
    detector = NPatternDetector(
        lookback_bars=60,
        min_leg_pct=0.03,    # 3%最小波段
        retr_min=0.15,       # 15%最小回撤
        retr_max=0.85        # 85%最大回撤
    )
    
    # 取最後60根K線
    recent_df = df.tail(60).reset_index(drop=True)
    print(f"\n📈 使用最近60根K線:")
    print(f"   期間: {recent_df['date'].iloc[0]} ~ {recent_df['date'].iloc[-1]}")
    print(f"   價格變化: {recent_df['close'].iloc[0]:.2f} → {recent_df['close'].iloc[-1]:.2f}")
    
    # Step 1: ZigZag偵測
    zigzag_points = detector.zigzag.detect(recent_df)
    print(f"\n🔄 ZigZag轉折點偵測 (共{len(zigzag_points)}個):")
    
    for i, (idx, price, type_) in enumerate(zigzag_points):
        date = recent_df.iloc[idx]['date']
        print(f"   {i+1:2d}. {type_} {price:7.2f} ({date}) [第{idx:2d}天]")
    
    # Step 2: 尋找ABC形態
    if len(zigzag_points) >= 3:
        print(f"\n🎯 尋找ABC形態 (L-H-L 模式):")
        
        abc_found = False
        for i in range(len(zigzag_points) - 1, 1, -1):
            if i < 2:
                break
                
            C_idx, C_price, C_type = zigzag_points[i]
            B_idx, B_price, B_type = zigzag_points[i-1]
            A_idx, A_price, A_type = zigzag_points[i-2]
            
            print(f"   檢查組合 {i-2}-{i-1}-{i}: {A_type}-{B_type}-{C_type}")
            
            if A_type == 'L' and B_type == 'H' and C_type == 'L':
                print(f"   ✅ 找到 L-H-L 形態:")
                print(f"      A點: {A_price:.2f} ({recent_df.iloc[A_idx]['date']})")
                print(f"      B點: {B_price:.2f} ({recent_df.iloc[B_idx]['date']})")
                print(f"      C點: {C_price:.2f} ({recent_df.iloc[C_idx]['date']})")
                
                # 檢查形態條件
                rise_pct = (B_price - A_price) / A_price
                retr_pct = (B_price - C_price) / (B_price - A_price)
                bars_from_c = len(recent_df) - 1 - C_idx
                
                print(f"      上漲幅度: {rise_pct:.1%} (需要>{detector.min_leg_pct:.1%})")
                print(f"      回撤比例: {retr_pct:.1%} (需要{detector.retr_min:.1%}-{detector.retr_max:.1%})")
                print(f"      C到現在: {bars_from_c}天 (需要<30天)")
                print(f"      C vs A: {C_price:.2f} vs {A_price*(1-detector.c_tolerance):.2f}")
                
                # 檢查每個條件
                if rise_pct >= detector.min_leg_pct:
                    print(f"      ✅ 漲幅足夠")
                else:
                    print(f"      ❌ 漲幅不足")
                
                if detector.retr_min <= retr_pct <= detector.retr_max:
                    print(f"      ✅ 回撤比例合適")
                else:
                    print(f"      ❌ 回撤比例不合適")
                    
                if C_price >= A_price * (1 - detector.c_tolerance):
                    print(f"      ✅ C點高於A點容忍範圍")
                else:
                    print(f"      ❌ C點太低")
                    
                if bars_from_c <= 30:
                    print(f"      ✅ C點夠新")
                else:
                    print(f"      ❌ C點太舊")
                
                abc_found = True
                break
        
        if not abc_found:
            print(f"   ❌ 未找到符合條件的ABC形態")
    else:
        print(f"   ❌ ZigZag轉折點不足3個")
    
    # Step 3: 完整偵測測試
    print(f"\n🎯 完整N字偵測測試:")
    signal = detector.detect_n_pattern(df, stock_id)
    
    if signal:
        print(f"✅ 偵測到N字訊號:")
        print(f"   評分: {signal.score}/100")
        print(f"   評分詳細: {signal.score_breakdown}")
        print(f"   觸發條件: 昨高={signal.trigger_break_yesterday_high}, EMA5量={signal.trigger_ema5_volume}, RSI={signal.trigger_rsi_strong}")
    else:
        print(f"❌ 未偵測到N字訊號")
        
        # 檢查技術指標
        from n_pattern_detector import TechnicalIndicators
        indicators = TechnicalIndicators()
        
        ema5 = indicators.ema(recent_df['close'], 5)
        rsi14 = indicators.rsi_wilder(recent_df['close'], 14)
        volume_ratio = indicators.volume_ratio(recent_df['volume'], 20)
        
        signal_idx = len(recent_df) - 1
        
        print(f"\n📊 最後一日技術指標:")
        print(f"   收盤價: {recent_df.iloc[signal_idx]['close']:.2f}")
        print(f"   EMA5: {ema5.iloc[signal_idx]:.2f}")
        print(f"   RSI14: {rsi14.iloc[signal_idx]:.1f}")
        print(f"   量比: {volume_ratio.iloc[signal_idx]:.2f}")
        
        # 檢查觸發條件
        if signal_idx > 0:
            yesterday_high = recent_df.iloc[signal_idx - 1]['high']
            today_close = recent_df.iloc[signal_idx]['close']
            break_yesterday = today_close > yesterday_high
            print(f"   突破昨高: {break_yesterday} ({today_close:.2f} vs {yesterday_high:.2f})")
        
        today_ema5 = ema5.iloc[signal_idx]
        today_vol_ratio = volume_ratio.iloc[signal_idx]
        ema5_volume = (recent_df.iloc[signal_idx]['close'] > today_ema5) and (today_vol_ratio > 1.0)
        print(f"   量增上穿EMA5: {ema5_volume}")
        
        today_rsi = rsi14.iloc[signal_idx]
        rsi_strong = today_rsi >= 50
        print(f"   RSI強勢: {rsi_strong}")

if __name__ == "__main__":
    debug_stock("2330")  # 台積電
    print("\n" + "="*80 + "\n")
    debug_stock("2454")  # 聯發科