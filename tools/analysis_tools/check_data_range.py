#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
檢查台積電數據範圍和ZigZag處理範圍
"""

import pandas as pd
import sqlite3

def check_tsmc_data_range():
    """檢查台積電數據範圍"""
    print("🔍 檢查台積電數據範圍")
    print("="*40)
    
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
    
    print(f"📊 完整數據概況:")
    print(f"   總筆數: {len(df)}")
    print(f"   日期範圍: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}")
    
    # 最近60天
    recent_df = df.tail(60).reset_index(drop=True)
    print(f"\n📅 最近60天數據:")
    print(f"   筆數: {len(recent_df)}")
    print(f"   日期範圍: {recent_df['date'].iloc[0]} ~ {recent_df['date'].iloc[-1]}")
    
    # 檢查8月數據是否存在
    aug_data = recent_df[recent_df['date'].str.contains('2025-08')]
    print(f"\n🗓️ 8月數據:")
    print(f"   8月筆數: {len(aug_data)}")
    if len(aug_data) > 0:
        print(f"   8月範圍: {aug_data['date'].iloc[0]} ~ {aug_data['date'].iloc[-1]}")
        
        # 顯示8月所有數據
        print(f"\n📈 8月所有交易日:")
        print(f"{'索引':<4} {'日期':<12} {'開盤':<8} {'最高':<8} {'最低':<8} {'收盤':<8}")
        print("-"*55)
        for i, row in aug_data.iterrows():
            print(f"{i:<4} {row['date']:<12} {row['open']:<8.1f} {row['high']:<8.1f} {row['low']:<8.1f} {row['close']:<8.1f}")
    else:
        print("   ❌ 最近60天中沒有8月數據！")
    
    # 檢查9月數據
    sep_data = recent_df[recent_df['date'].str.contains('2025-09')]
    print(f"\n🗓️ 9月數據:")
    print(f"   9月筆數: {len(sep_data)}")
    if len(sep_data) > 0:
        print(f"   9月範圍: {sep_data['date'].iloc[0]} ~ {sep_data['date'].iloc[-1]}")

if __name__ == "__main__":
    check_tsmc_data_range()