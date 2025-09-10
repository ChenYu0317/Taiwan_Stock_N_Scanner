#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
檢查台積電2330在8/22-8/28特定期間是否符合N字回撤
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'signal'))
from n_pattern_detector import NPatternDetector

import pandas as pd
import sqlite3
from datetime import datetime

def check_tsmc_specific_period():
    """檢查台積電8/22-8/28期間的N字形態"""
    print("🔍 檢查台積電(2330) 8/22-8/28 N字回撤形態")
    print("="*60)
    
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    # 讀取台積電數據
    query = """
    SELECT date, open, high, low, close, volume
    FROM daily_prices 
    WHERE stock_id = '2330'
    ORDER BY date
    """
    df = pd.read_sql_query(query, conn, params=())
    conn.close()
    
    if len(df) == 0:
        print("❌ 沒有找到台積電資料")
        return
    
    print(f"📊 台積電資料概況:")
    print(f"   總筆數: {len(df)}")
    print(f"   日期範圍: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}")
    
    # 找出8/22-8/28期間的資料
    target_dates = ['2025-08-22', '2025-08-23', '2025-08-26', '2025-08-27', '2025-08-28']
    period_data = df[df['date'].isin(target_dates)]
    
    print(f"\n📅 8/22-8/28期間資料:")
    print(f"{'日期':<12} {'開盤':<8} {'最高':<8} {'最低':<8} {'收盤':<8} {'成交量':<12}")
    print("-"*60)
    
    for _, row in period_data.iterrows():
        print(f"{row['date']:<12} {row['open']:<8.1f} {row['high']:<8.1f} {row['low']:<8.1f} {row['close']:<8.1f} {int(row['volume']):<12,}")
    
    # 使用目前的最優參數進行N字偵測
    detector = NPatternDetector(
        lookback_bars=60,
        zigzag_change_pct=0.015,  # 1.5%
        min_leg_pct=0.04,         # 4%
        retr_min=0.20,            # 20%
        retr_max=0.80,            # 80%
        c_tolerance=0.00,
        min_bars_ab=1,
        max_bars_ab=80,
        min_bars_bc=1,
        max_bars_bc=50,
        volume_threshold=1.0
    )
    
    # 分析ZigZag轉折點
    recent_df = df.tail(60).reset_index(drop=True)
    zigzag_points = detector.zigzag.detect(recent_df)
    
    print(f"\n🔄 ZigZag 轉折點分析:")
    print(f"   找到 {len(zigzag_points)} 個轉折點")
    
    # 找出8/22-8/28期間相關的轉折點
    period_zigzag = []
    for idx, price, type_ in zigzag_points:
        date = recent_df.iloc[idx]['date']
        if '2025-08-2' in date:  # 8月下旬的轉折點
            period_zigzag.append((idx, price, type_, date))
    
    if period_zigzag:
        print(f"\n   8月下旬相關轉折點:")
        for i, (idx, price, type_, date) in enumerate(period_zigzag):
            print(f"     {i+1}. {type_} {price:.1f} ({date}) [第{idx}天]")
    
    # 檢查是否有符合8/22-8/28的ABC形態
    print(f"\n🎯 N字形態分析 (以8/28為訊號日):")
    
    # 嘗試以8/28作為訊號日進行分析
    signal_date = '2025-08-28'
    signal_idx = recent_df[recent_df['date'] == signal_date].index
    
    if len(signal_idx) == 0:
        print(f"❌ 找不到8/28的資料")
        return
    
    signal_idx = signal_idx[0]
    
    # 手動檢查在8/28之前是否有L-H-L形態
    relevant_points = []
    for i, (idx, price, type_) in enumerate(zigzag_points):
        if idx <= signal_idx:  # 只看8/28之前的點
            relevant_points.append((i, idx, price, type_))
    
    print(f"   8/28前的轉折點 (最後10個):")
    for pos, idx, price, type_ in relevant_points[-10:]:
        date = recent_df.iloc[idx]['date']
        print(f"     #{pos}: {type_} {price:.1f} ({date})")
    
    # 檢查最近的L-H-L模式
    lhl_found = False
    
    if len(relevant_points) >= 3:
        for i in range(len(relevant_points)-1, 1, -1):
            if i < 2:
                break
            
            _, C_idx, C_price, C_type = relevant_points[i]
            _, B_idx, B_price, B_type = relevant_points[i-1]  
            _, A_idx, A_price, A_type = relevant_points[i-2]
            
            if A_type == 'L' and B_type == 'H' and C_type == 'L':
                A_date = recent_df.iloc[A_idx]['date']
                B_date = recent_df.iloc[B_idx]['date']
                C_date = recent_df.iloc[C_idx]['date']
                
                # 檢查是否在目標期間範圍內
                period_involved = False
                for target_date in target_dates:
                    if target_date >= A_date and target_date <= signal_date:
                        period_involved = True
                        break
                
                if period_involved or C_date >= '2025-08-20':  # 如果C點在8/20之後
                    print(f"\n   ✅ 找到相關L-H-L形態:")
                    print(f"      A點: {A_price:.1f} ({A_date})")
                    print(f"      B點: {B_price:.1f} ({B_date})")  
                    print(f"      C點: {C_price:.1f} ({C_date})")
                    
                    # 計算形態參數
                    rise_pct = (B_price - A_price) / A_price
                    retr_pct = (B_price - C_price) / (B_price - A_price)
                    bars_ab = B_idx - A_idx
                    bars_bc = C_idx - B_idx
                    bars_c_to_signal = signal_idx - C_idx
                    
                    print(f"      上漲幅度: {rise_pct:.1%}")
                    print(f"      回撤比例: {retr_pct:.1%}")
                    print(f"      時間: AB={bars_ab}天, BC={bars_bc}天, C到8/28={bars_c_to_signal}天")
                    
                    # 檢查各項條件
                    conditions = []
                    conditions.append(f"漲幅>4%: {'✅' if rise_pct >= 0.04 else '❌'}")
                    conditions.append(f"回撤20-80%: {'✅' if 0.20 <= retr_pct <= 0.80 else '❌'}")
                    conditions.append(f"C≥A: {'✅' if C_price >= A_price else '❌'}")
                    conditions.append(f"時效<30天: {'✅' if bars_c_to_signal <= 30 else '❌'}")
                    
                    print(f"      條件檢查: {', '.join(conditions)}")
                    
                    # 如果形態符合，檢查技術指標觸發條件
                    if (rise_pct >= 0.04 and 0.20 <= retr_pct <= 0.80 and 
                        C_price >= A_price and bars_c_to_signal <= 30):
                        
                        print(f"\n   🎯 ABC形態符合，檢查8/28觸發條件:")
                        
                        # 計算8/28的技術指標
                        from n_pattern_detector import TechnicalIndicators
                        indicators = TechnicalIndicators()
                        
                        ema5 = indicators.ema(recent_df['close'], 5)
                        rsi14 = indicators.rsi_wilder(recent_df['close'], 14)
                        volume_ratio = indicators.volume_ratio(recent_df['volume'], 20)
                        
                        today_close = recent_df.iloc[signal_idx]['close']
                        today_ema5 = ema5.iloc[signal_idx]
                        today_rsi = rsi14.iloc[signal_idx]
                        today_vol_ratio = volume_ratio.iloc[signal_idx]
                        
                        print(f"      8/28技術指標:")
                        print(f"        收盤價: {today_close:.1f}")
                        print(f"        EMA5: {today_ema5:.1f}")
                        print(f"        RSI: {today_rsi:.1f}")
                        print(f"        量比: {today_vol_ratio:.2f}")
                        
                        # 檢查觸發條件
                        triggers = []
                        
                        # 突破昨高
                        if signal_idx > 0:
                            yesterday_high = recent_df.iloc[signal_idx - 1]['high']
                            break_yesterday = today_close > yesterday_high
                            triggers.append(f"突破昨高: {'✅' if break_yesterday else '❌'} ({today_close:.1f} vs {yesterday_high:.1f})")
                        
                        # EMA5量增
                        ema5_volume = (today_close > today_ema5) and (today_vol_ratio > 1.0)
                        triggers.append(f"EMA5量增: {'✅' if ema5_volume else '❌'}")
                        
                        # RSI強勢
                        rsi_strong = today_rsi >= 50
                        triggers.append(f"RSI強勢: {'✅' if rsi_strong else '❌'}")
                        
                        print(f"      觸發條件:")
                        for trigger in triggers:
                            print(f"        {trigger}")
                        
                        # 綜合判斷
                        trigger_count = sum([
                            '✅' in trigger for trigger in triggers
                        ])
                        
                        if trigger_count > 0:
                            print(f"\n   🎉 結論: 台積電8/22-8/28期間 {'符合' if trigger_count >= 1 else '不符合'} N字回撤形態!")
                            print(f"   觸發條件: {trigger_count}/3 項成立")
                        else:
                            print(f"\n   ❌ 結論: 雖有ABC形態，但8/28無觸發條件成立")
                        
                        lhl_found = True
                        break
    
    if not lhl_found:
        print(f"\n   ❌ 未找到8/22-8/28期間相關的N字形態")
    
    # 最後用完整演算法驗證
    print(f"\n🔬 完整演算法驗證:")
    signal = detector.detect_n_pattern(df, "2330")
    if signal:
        # 檢查訊號日期是否在目標期間
        if signal.signal_date in target_dates:
            print(f"✅ 完整演算法確認: 8/22-8/28有N字訊號 (訊號日: {signal.signal_date})")
            print(f"   評分: {signal.score}/100")
        else:
            print(f"⚪ 完整演算法找到其他日期的訊號: {signal.signal_date}")
    else:
        print(f"❌ 完整演算法確認: 台積電目前無N字訊號")

if __name__ == "__main__":
    check_tsmc_specific_period()