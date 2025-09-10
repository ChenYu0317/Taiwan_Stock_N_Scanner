#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用原始嚴格標準測試更多股票的N字回撤偵測
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'signal'))
from n_pattern_detector import NPatternDetector

import pandas as pd
import sqlite3

def test_original_standard_more_stocks():
    """使用原始標準測試更多股票"""
    print("🚀 使用原始嚴格標準測試N字回撤偵測")
    
    # 擴大測試股票清單到50檔
    test_stocks = [
        # 權值股
        '2330', '2454', '2317', '3008', '2382', '6505', '2881', '1101', 
        '2891', '1303', '1326', '2885', '2379', '2408', '3034', '2327',
        '6488', '2412', '2002', '1216',
        
        # 電子股
        '2409', '3711', '2474', '3443', '4938', '6669', '3406', '2368',
        '2324', '2357', '2356', '2376', '6415', '3017', '2449',
        
        # 傳產金融
        '2892', '2886', '2883', '1102', '2207', '1301', '2105', '2603',
        '2615', '1605', '2801', '2834', '2912', '9910', '2609'
    ]
    
    print(f"📊 測試股票數量: {len(test_stocks)} 檔")
    
    # 使用原始嚴格標準
    detector = NPatternDetector(
        lookback_bars=60,
        min_leg_pct=0.04,    # 最優: 4%最小波段
        retr_min=0.20,       # 原始: 20%最小回撤  
        retr_max=0.80,       # 原始: 80%最大回撤
        c_tolerance=0.00     # 原始: C點不可低於A點
    )
    
    # 確保使用最優ZigZag參數
    detector.zigzag.min_change_pct = 0.015  # 最優: 1.5%變化閾值
    
    signals = []
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    # 統計資訊
    total_tested = 0
    zigzag_adequate = 0  # ZigZag點數足夠的股票
    abc_found = 0        # 找到ABC形態的股票
    
    for i, stock_id in enumerate(test_stocks, 1):
        print(f"\n📊 ({i:2d}/{len(test_stocks)}) 測試股票: {stock_id}")
        
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
            
            total_tested += 1
            recent_df = df.tail(60).reset_index(drop=True)
            
            # 檢查ZigZag點數
            zigzag_points = detector.zigzag.detect(recent_df)
            print(f"   🔄 ZigZag轉折點: {len(zigzag_points)} 個")
            
            if len(zigzag_points) >= 3:
                zigzag_adequate += 1
                
                # 檢查是否找到ABC
                abc_result = detector.find_last_abc_pattern(zigzag_points, recent_df)
                if abc_result:
                    abc_found += 1
                    A_idx, B_idx, C_idx = abc_result
                    
                    A_price = zigzag_points[A_idx][1]
                    B_price = zigzag_points[B_idx][1]
                    C_price = zigzag_points[C_idx][1]
                    
                    rise_pct = (B_price - A_price) / A_price
                    retr_pct = (B_price - C_price) / (B_price - A_price)
                    
                    print(f"   📈 找到ABC: A={A_price:.2f} B={B_price:.2f} C={C_price:.2f}")
                    print(f"      漲幅={rise_pct:.1%} 回撤={retr_pct:.1%}")
            
            # 完整偵測
            signal = detector.detect_n_pattern(df, stock_id)
            
            if signal:
                signals.append(signal)
                print(f"   ✅ 找到N字訊號! 評分: {signal.score}/100")
                print(f"      觸發: 昨高={signal.trigger_break_yesterday_high}, EMA5量={signal.trigger_ema5_volume}, RSI={signal.trigger_rsi_strong}")
            else:
                print(f"   ❌ 未產生最終訊號")
                
        except Exception as e:
            print(f"   ⚠️ 處理錯誤: {e}")
    
    conn.close()
    
    # 詳細統計結果
    print(f"\n" + "="*80)
    print(f"🎯 原始標準測試結果統計")
    print(f"="*80)
    print(f"總測試股票數: {total_tested}")
    print(f"ZigZag點數足夠: {zigzag_adequate} ({zigzag_adequate/total_tested*100:.1f}%)")
    print(f"找到ABC形態: {abc_found} ({abc_found/total_tested*100:.1f}%)")
    print(f"最終產生訊號: {len(signals)} ({len(signals)/total_tested*100:.1f}%)")
    
    if signals:
        print(f"\n🏆 發現的訊號 ({len(signals)}個):")
        for i, signal in enumerate(sorted(signals, key=lambda s: s.score, reverse=True), 1):
            print(f"\n{i}. {signal.stock_id}: {signal.score}分")
            print(f"   A點: {signal.A_price:.2f} ({signal.A_date})")
            print(f"   B點: {signal.B_price:.2f} ({signal.B_date}) → 漲{signal.rise_pct:.1%}")
            print(f"   C點: {signal.C_price:.2f} ({signal.C_date}) → 撤{signal.retr_pct:.1%}")
            print(f"   技術指標: RSI={signal.rsi14:.1f}, 量比={signal.volume_ratio:.2f}")
            print(f"   觸發條件: 昨高={signal.trigger_break_yesterday_high}, EMA5量={signal.trigger_ema5_volume}, RSI={signal.trigger_rsi_strong}")
            print(f"   評分詳細: {signal.score_breakdown}")
    
    return signals

def analyze_no_signal_reasons():
    """分析為什麼大多數股票沒有訊號"""
    print(f"\n🔍 分析原始標準下的限制因素")
    
    sample_stocks = ['2330', '2317', '3008', '2382', '2881']
    detector = NPatternDetector(
        lookback_bars=60,
        min_leg_pct=0.04,
        retr_min=0.20,
        retr_max=0.80,
        c_tolerance=0.00
    )
    detector.zigzag.min_change_pct = 0.015
    
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    for stock_id in sample_stocks:
        print(f"\n📊 {stock_id} 詳細分析:")
        
        query = """
        SELECT date, open, high, low, close, volume
        FROM daily_prices 
        WHERE stock_id = ?
        ORDER BY date
        """
        df = pd.read_sql_query(query, conn, params=(stock_id,))
        recent_df = df.tail(60).reset_index(drop=True)
        
        # 價格波動分析
        price_range = recent_df['close'].max() - recent_df['close'].min()
        price_volatility = price_range / recent_df['close'].mean()
        print(f"   價格波動率: {price_volatility:.1%}")
        
        # ZigZag分析
        zigzag_points = detector.zigzag.detect(recent_df)
        print(f"   ZigZag點數: {len(zigzag_points)} (需要≥3)")
        
        if len(zigzag_points) >= 3:
            print(f"   最後3個轉折點:")
            for j, (idx, price, type_) in enumerate(zigzag_points[-3:]):
                date = recent_df.iloc[idx]['date']
                print(f"     {type_} {price:.2f} ({date})")
    
    conn.close()

if __name__ == "__main__":
    signals = test_original_standard_more_stocks()
    analyze_no_signal_reasons()