#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
詳細分析ZigZag在1.5%敏感度下找到的轉折點
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'signal'))
from n_pattern_detector import ZigZagDetector

import pandas as pd
import sqlite3

def debug_zigzag_15_percent():
    """詳細分析1.5%敏感度的ZigZag結果"""
    print("🔍 詳細分析ZigZag 1.5%敏感度結果")
    print("="*50)
    
    # 讀取台積電數據
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    query = """
    SELECT date, open, high, low, close, volume
    FROM daily_prices 
    WHERE stock_id = '2330'
    ORDER BY date
    """
    df = pd.read_sql_query(query, conn, params=())
    conn.close()
    
    recent_df = df.tail(60).reset_index(drop=True)
    
    # 1.5%敏感度的ZigZag
    zigzag = ZigZagDetector(min_change_pct=0.015)
    points = zigzag.detect(recent_df)
    
    print(f"📊 找到 {len(points)} 個轉折點:")
    print(f"{'序號':<4} {'類型':<4} {'價格':<8} {'日期':<12} {'索引':<4}")
    print("-"*40)
    
    for i, (idx, price, type_) in enumerate(points):
        date = recent_df.iloc[idx]['date']
        print(f"{i+1:<4} {type_:<4} {price:<8.1f} {date:<12} {idx:<4}")
    
    # 找到8/22, 8/27, 8/28的索引
    aug22_idx = recent_df[recent_df['date'] == '2025-08-22'].index[0]
    aug27_idx = recent_df[recent_df['date'] == '2025-08-27'].index[0]  
    aug28_idx = recent_df[recent_df['date'] == '2025-08-28'].index[0]
    
    print(f"\n🎯 關鍵日期索引:")
    print(f"   8/22: 第{aug22_idx}天")
    print(f"   8/27: 第{aug27_idx}天") 
    print(f"   8/28: 第{aug28_idx}天")
    
    # 檢查這些日期附近的原始數據
    print(f"\n📈 8/20-8/30期間原始數據:")
    print(f"{'日期':<12} {'開盤':<8} {'最高':<8} {'最低':<8} {'收盤':<8}")
    print("-"*50)
    
    for i in range(max(0, aug22_idx-3), min(len(recent_df), aug28_idx+3)):
        row = recent_df.iloc[i]
        marker = ""
        if i == aug22_idx:
            marker = " ← 8/22"
        elif i == aug27_idx:
            marker = " ← 8/27"  
        elif i == aug28_idx:
            marker = " ← 8/28"
            
        print(f"{row['date']:<12} {row['open']:<8.1f} {row['high']:<8.1f} {row['low']:<8.1f} {row['close']:<8.1f}{marker}")
    
    # 手動計算變化幅度
    print(f"\n🧮 手動計算變化幅度:")
    aug22_low = recent_df.iloc[aug22_idx]['low']    # 8/22低點
    aug27_high = recent_df.iloc[aug27_idx]['high']  # 8/27高點
    aug28_low = recent_df.iloc[aug28_idx]['low']    # 8/28低點
    
    change_22_to_27 = (aug27_high - aug22_low) / aug22_low
    change_27_to_28 = (aug27_high - aug28_low) / aug27_high
    
    print(f"   8/22低點 {aug22_low} → 8/27高點 {aug27_high}: {change_22_to_27:.2%}")
    print(f"   8/27高點 {aug27_high} → 8/28低點 {aug28_low}: {change_27_to_28:.2%}")
    
    # 分析為什麼ZigZag沒有捕捉到
    print(f"\n❓ 分析ZigZag為什麼沒捕捉到:")
    print(f"   理論上 {change_27_to_28:.2%} > 1.5%，應該被捕捉")
    print(f"   但ZigZag可能被其他更大的波動覆蓋了")
    
    # 檢查是否有其他更大的波動
    print(f"\n🔄 檢查期間內的日間波動:")
    for i in range(aug22_idx, aug28_idx+1):
        row = recent_df.iloc[i]
        daily_range = (row['high'] - row['low']) / row['low']
        print(f"   {row['date']}: 日內波動 {daily_range:.2%} (最高{row['high']:.1f} 最低{row['low']:.1f})")

if __name__ == "__main__":
    debug_zigzag_15_percent()