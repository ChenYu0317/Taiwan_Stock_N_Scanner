#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手動檢查台積電8/22-8/28的N字形態（不依賴ZigZag）
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'signal'))
from n_pattern_detector import NPatternDetector

import pandas as pd
import sqlite3

def manual_check_tsmc_n_pattern():
    """手動檢查台積電8/22-8/28 N字形態"""
    print("🔍 手動檢查台積電8/22-8/28 N字形態")
    print("="*60)
    
    # 手動設定ABC點
    A_price = 1135.0  # 8/22 低點
    A_date = "2025-08-22"
    
    B_price = 1190.0  # 8/27 高點  
    B_date = "2025-08-27"
    
    C_price = 1160.0  # 8/28 低點
    C_date = "2025-08-28"
    
    print(f"📊 手動ABC點設定:")
    print(f"   A點: {A_price:.1f} ({A_date}) - 8/22低點")
    print(f"   B點: {B_price:.1f} ({B_date}) - 8/27高點")
    print(f"   C點: {C_price:.1f} ({C_date}) - 8/28低點")
    
    # 計算形態參數
    rise_pct = (B_price - A_price) / A_price
    retr_pct = (B_price - C_price) / (B_price - A_price)
    
    print(f"\n📈 形態參數計算:")
    print(f"   上漲幅度: {rise_pct:.2%} (A→B)")
    print(f"   回撤比例: {retr_pct:.1%} (B→C)")
    
    # 檢查4%標準的各項條件
    print(f"\n✅ 修改後條件檢查 (4%標準):")
    
    conditions = []
    
    # 1. 漲幅檢查
    rise_pass = rise_pct >= 0.04
    conditions.append(f"漲幅≥4%: {'✅' if rise_pass else '❌'} ({rise_pct:.2%})")
    
    # 2. 回撤檢查
    retr_pass = 0.20 <= retr_pct <= 0.80
    conditions.append(f"回撤20-80%: {'✅' if retr_pass else '❌'} ({retr_pct:.1%})")
    
    # 3. C不破A
    c_vs_a_pass = C_price >= A_price
    conditions.append(f"C≥A: {'✅' if c_vs_a_pass else '❌'} ({C_price:.1f} vs {A_price:.1f})")
    
    # 4. 時間結構
    import datetime
    from datetime import datetime as dt
    
    a_dt = dt.strptime(A_date, '%Y-%m-%d')
    b_dt = dt.strptime(B_date, '%Y-%m-%d') 
    c_dt = dt.strptime(C_date, '%Y-%m-%d')
    signal_dt = dt.strptime("2025-08-28", '%Y-%m-%d')
    
    bars_ab = (b_dt - a_dt).days
    bars_bc = (c_dt - b_dt).days
    bars_c_to_signal = (signal_dt - c_dt).days
    
    time_pass = bars_c_to_signal <= 30
    conditions.append(f"時效≤30天: {'✅' if time_pass else '❌'} ({bars_c_to_signal}天)")
    
    for condition in conditions:
        print(f"   {condition}")
    
    # 綜合判斷
    all_conditions_pass = rise_pass and retr_pass and c_vs_a_pass and time_pass
    
    print(f"\n🎯 N字形態判斷結果:")
    if all_conditions_pass:
        print(f"   ✅ 台積電8/22-8/28 **符合** N字回撤形態！")
        print(f"   📊 時間結構: AB={bars_ab}天, BC={bars_bc}天, C到訊號={bars_c_to_signal}天")
        
        # 檢查8/28的技術指標觸發條件
        print(f"\n🎯 檢查8/28技術指標觸發條件:")
        check_trigger_conditions()
        
    else:
        print(f"   ❌ 台積電8/22-8/28不符合N字形態")
        failed = []
        if not rise_pass: failed.append("漲幅不足")
        if not retr_pass: failed.append("回撤超範圍")
        if not c_vs_a_pass: failed.append("C破A點")
        if not time_pass: failed.append("時效過期")
        print(f"   失敗原因: {', '.join(failed)}")

def check_trigger_conditions():
    """檢查8/28的觸發條件"""
    # 讀取台積電數據來計算技術指標
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    query = """
    SELECT date, open, high, low, close, volume
    FROM daily_prices 
    WHERE stock_id = '2330'
    ORDER BY date
    """
    df = pd.read_sql_query(query, conn, params=())
    conn.close()
    
    from n_pattern_detector import TechnicalIndicators
    indicators = TechnicalIndicators()
    
    recent_df = df.tail(60).reset_index(drop=True)
    signal_idx = recent_df[recent_df['date'] == '2025-08-28'].index[0]
    
    # 計算技術指標
    ema5 = indicators.ema(recent_df['close'], 5)
    rsi14 = indicators.rsi_wilder(recent_df['close'], 14)
    volume_ratio = indicators.volume_ratio(recent_df['volume'], 20)
    
    today_close = recent_df.iloc[signal_idx]['close']
    today_ema5 = ema5.iloc[signal_idx]
    today_rsi = rsi14.iloc[signal_idx] 
    today_vol_ratio = volume_ratio.iloc[signal_idx]
    
    print(f"   8/28技術指標:")
    print(f"     收盤價: {today_close:.1f}")
    print(f"     EMA5: {today_ema5:.1f}")
    print(f"     RSI: {today_rsi:.1f}")
    print(f"     量比: {today_vol_ratio:.2f}")
    
    # 檢查觸發條件
    triggers = []
    
    # 1. 突破昨高
    if signal_idx > 0:
        yesterday_high = recent_df.iloc[signal_idx - 1]['high']
        break_yesterday = today_close > yesterday_high
        triggers.append(f"突破昨高: {'✅' if break_yesterday else '❌'} ({today_close:.1f} vs {yesterday_high:.1f})")
    
    # 2. EMA5量增  
    ema5_volume = (today_close > today_ema5) and (today_vol_ratio > 1.0)
    triggers.append(f"EMA5量增: {'✅' if ema5_volume else '❌'}")
    
    # 3. RSI強勢
    rsi_strong = today_rsi >= 50
    triggers.append(f"RSI強勢: {'✅' if rsi_strong else '❌'}")
    
    print(f"   觸發條件檢查:")
    for trigger in triggers:
        print(f"     {trigger}")
    
    # 統計觸發條件
    trigger_count = sum(['✅' in t for t in triggers])
    print(f"\n   🏆 結果: {trigger_count}/3 項觸發條件成立")
    
    if trigger_count >= 1:
        print(f"   ✅ 符合觸發要求（至少1項成立）")
    else:
        print(f"   ❌ 不符合觸發要求")

if __name__ == "__main__":
    manual_check_tsmc_n_pattern()