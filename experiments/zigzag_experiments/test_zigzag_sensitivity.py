#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試不同ZigZag參數的敏感度
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'signal'))
from n_pattern_detector import ZigZagDetector

import pandas as pd
import sqlite3

def test_zigzag_sensitivity(stock_id='2330'):
    """測試不同ZigZag參數"""
    print(f"🔍 測試 {stock_id} 的ZigZag敏感度")
    
    # 讀取資料
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    query = """
    SELECT date, open, high, low, close, volume
    FROM daily_prices 
    WHERE stock_id = ?
    ORDER BY date
    """
    df = pd.read_sql_query(query, conn, params=(stock_id,))
    conn.close()
    
    recent_df = df.tail(60).reset_index(drop=True)
    
    print(f"📊 測試數據: {recent_df['date'].iloc[0]} ~ {recent_df['date'].iloc[-1]}")
    print(f"價格範圍: {recent_df['close'].min():.2f} ~ {recent_df['close'].max():.2f}")
    
    # 測試不同的ZigZag參數
    test_params = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]
    
    for min_change in test_params:
        zigzag = ZigZagDetector(min_change_pct=min_change)
        points = zigzag.detect(recent_df)
        
        print(f"\n📈 最小變化 {min_change:.1%}: 找到 {len(points)} 個轉折點")
        
        if len(points) >= 3:
            # 顯示最後幾個轉折點
            print(f"   最後5個轉折點:")
            for i, (idx, price, type_) in enumerate(points[-5:]):
                date = recent_df.iloc[idx]['date']
                print(f"     {type_} {price:7.2f} ({date}) [第{idx:2d}天]")
                
            # 檢查是否有L-H-L形態
            lhl_patterns = 0
            for i in range(len(points) - 1, 1, -1):
                if i < 2:
                    break
                if (points[i][2] == 'L' and 
                    points[i-1][2] == 'H' and 
                    points[i-2][2] == 'L'):
                    lhl_patterns += 1
            print(f"   L-H-L 形態數量: {lhl_patterns}")
        else:
            print(f"   轉折點不足 (需要至少3個)")

if __name__ == "__main__":
    test_zigzag_sensitivity("2330")
    print("\n" + "="*60 + "\n")
    test_zigzag_sensitivity("2454")