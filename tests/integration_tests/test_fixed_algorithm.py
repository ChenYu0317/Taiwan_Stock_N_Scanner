#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試修正後的N字回撤偵測演算法
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'signal'))
from n_pattern_detector import NPatternDetector

import pandas as pd
import sqlite3
import numpy as np

def test_zigzag_fix():
    """測試ZigZag修正前後的差異"""
    print("🔧 測試ZigZag修正效果")
    
    # 創建測試數據 - 明顯的N字形態
    np.random.seed(42)
    dates = pd.date_range('2025-08-01', periods=30, freq='D')
    
    # 構造明確的L-H-L-H形態
    prices = []
    # L1: 低點
    for i in range(5):
        prices.append(100 + np.random.normal(0, 0.5))
    # H1: 高點 (+8%)
    for i in range(5):
        prices.append(108 + np.random.normal(0, 0.5))
    # L2: 回撤到106 (25%回撤)
    for i in range(5):
        prices.append(106 + np.random.normal(0, 0.3))
    # H2: 再次向上
    for i in range(15):
        prices.append(108 + i*0.2 + np.random.normal(0, 0.3))
    
    df = pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'open': prices,
        'high': [p * 1.01 for p in prices],
        'low': [p * 0.99 for p in prices],
        'close': prices,
        'volume': [1000000] * len(prices)
    })
    
    print(f"📊 測試數據: 期望L(100)->H(108)->L(106)->H(111)")
    
    # 使用修正後的演算法
    detector = NPatternDetector(
        lookback_bars=30,
        zigzag_change_pct=0.02,  # 2%敏感度
        min_leg_pct=0.04,        # 4%最小波段
        min_bars_ab=2,           # 最小AB段
        max_bars_ab=15,          # 最大AB段
        min_bars_bc=2,           # 最小BC段
        max_bars_bc=15           # 最大BC段
    )
    
    # ZigZag測試
    zigzag_points = detector.zigzag.detect(df)
    print(f"\n🔄 ZigZag轉折點 ({len(zigzag_points)}個):")
    for i, (idx, price, type_) in enumerate(zigzag_points):
        date = df.iloc[idx]['date']
        print(f"   {i+1}. {type_} {price:.2f} ({date}) [第{idx}天]")
    
    # 測試ABC形態識別
    abc_result = detector.find_last_abc_pattern(zigzag_points, df)
    if abc_result:
        A_idx, B_idx, C_idx = abc_result
        print(f"\n✅ ABC形態識別:")
        print(f"   A點: {zigzag_points[A_idx][1]:.2f} ({df.iloc[zigzag_points[A_idx][0]]['date']})")
        print(f"   B點: {zigzag_points[B_idx][1]:.2f} ({df.iloc[zigzag_points[B_idx][0]]['date']})")
        print(f"   C點: {zigzag_points[C_idx][1]:.2f} ({df.iloc[zigzag_points[C_idx][0]]['date']})")
        
        A_price, B_price, C_price = zigzag_points[A_idx][1], zigzag_points[B_idx][1], zigzag_points[C_idx][1]
        rise_pct = (B_price - A_price) / A_price
        retr_pct = (B_price - C_price) / (B_price - A_price)
        
        print(f"   漲幅: {rise_pct:.1%}")
        print(f"   回撤: {retr_pct:.1%}")
    else:
        print(f"\n❌ 未找到ABC形態")
    
    # 完整N字偵測
    signal = detector.detect_n_pattern(df, "TEST")
    if signal:
        print(f"\n🎯 完整N字訊號: {signal.score}分")
    else:
        print(f"\n❌ 未產生完整訊號")

def compare_before_after():
    """比較修正前後在真實數據上的表現"""
    print(f"\n📊 比較修正前後的實際表現")
    
    # 測試幾檔關鍵股票
    test_stocks = ['2330', '2454', '2409', '2204']
    
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    for stock_id in test_stocks:
        print(f"\n📈 {stock_id}:")
        
        query = """
        SELECT date, open, high, low, close, volume
        FROM daily_prices 
        WHERE stock_id = ?
        ORDER BY date
        """
        df = pd.read_sql_query(query, conn, params=(stock_id,))
        
        if len(df) < 60:
            continue
        
        # 修正後版本（使用新的時間護欄）
        detector_new = NPatternDetector(
            lookback_bars=60,
            zigzag_change_pct=0.015,  # 1.5%
            min_leg_pct=0.04,         # 4%
            min_bars_ab=3,            # 新增護欄
            max_bars_ab=60,
            min_bars_bc=2,
            max_bars_bc=40,
            volume_threshold=1.2      # 提高量能門檻
        )
        
        recent_df = df.tail(60).reset_index(drop=True)
        zigzag_points = detector_new.zigzag.detect(recent_df)
        
        print(f"   ZigZag轉折點: {len(zigzag_points)} 個")
        
        # 檢查ABC
        abc_result = detector_new.find_last_abc_pattern(zigzag_points, recent_df)
        if abc_result:
            print(f"   ✅ 找到ABC形態")
            
            signal = detector_new.detect_n_pattern(df, stock_id)
            if signal:
                print(f"   🎯 完整訊號: {signal.score}分")
                print(f"      形態: A={signal.A_price:.1f} B={signal.B_price:.1f} C={signal.C_price:.1f}")
                print(f"      漲{signal.rise_pct:.1%} 撤{signal.retr_pct:.1%}")
                
                # 檢查時間護欄是否有效
                A_idx = next(i for i, (idx, price, type_) in enumerate(zigzag_points) if idx == abc_result[0] and type_ == 'L')
                B_idx = next(i for i, (idx, price, type_) in enumerate(zigzag_points) if idx == abc_result[1] and type_ == 'H')  
                C_idx = next(i for i, (idx, price, type_) in enumerate(zigzag_points) if idx == abc_result[2] and type_ == 'L')
                
                bars_ab = zigzag_points[B_idx][0] - zigzag_points[A_idx][0]
                bars_bc = zigzag_points[C_idx][0] - zigzag_points[B_idx][0]
                
                print(f"      時間: AB={bars_ab}天, BC={bars_bc}天")
            else:
                print(f"   ❌ ABC存在但觸發條件不足")
        else:
            print(f"   ❌ 未找到ABC形態")
    
    conn.close()

def scan_with_fixed_algorithm():
    """用修正後演算法重新掃描"""
    print(f"\n🚀 修正後演算法全市場掃描")
    
    # 使用修正後的嚴格標準
    detector = NPatternDetector(
        lookback_bars=60,
        zigzag_change_pct=0.015,  # 1.5% ZigZag敏感度
        min_leg_pct=0.04,         # 4% 最小波段（最優參數）
        retr_min=0.20,            # 20% 最小回撤（保持原始）
        retr_max=0.80,            # 80% 最大回撤（保持原始）
        c_tolerance=0.00,         # C不可破A（保持原始）
        min_bars_ab=3,            # AB最少3天
        max_bars_ab=60,           # AB最多60天
        min_bars_bc=2,            # BC最少2天
        max_bars_bc=40,           # BC最多40天
        volume_threshold=1.2      # 量增門檻1.2倍
    )
    
    signals = []
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    # 獲取所有股票
    query = "SELECT DISTINCT stock_id FROM daily_prices WHERE stock_id IN (SELECT stock_id FROM daily_prices GROUP BY stock_id HAVING COUNT(*) >= 60) ORDER BY stock_id"
    all_stocks = pd.read_sql_query(query, conn)['stock_id'].tolist()
    
    print(f"掃描 {len(all_stocks)} 檔股票...")
    
    for i, stock_id in enumerate(all_stocks):
        if i % 30 == 0:
            print(f"進度: {i}/{len(all_stocks)}")
        
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
                print(f"✅ {stock_id}: {signal.score}分")
        
        except Exception as e:
            continue
    
    conn.close()
    
    print(f"\n📋 修正後結果:")
    print(f"找到 {len(signals)} 個訊號")
    
    if signals:
        # 前5名
        top5 = sorted(signals, key=lambda s: s.score, reverse=True)[:5]
        print(f"\n🏆 前5名:")
        for i, signal in enumerate(top5, 1):
            print(f"{i}. {signal.stock_id}: {signal.score}分")
            print(f"   漲{signal.rise_pct:.1%} 撤{signal.retr_pct:.1%}")
            print(f"   觸發: 昨高={signal.trigger_break_yesterday_high}, EMA5量={signal.trigger_ema5_volume}, RSI={signal.trigger_rsi_strong}")
    
    return signals

if __name__ == "__main__":
    test_zigzag_fix()
    compare_before_after()
    scan_with_fixed_algorithm()