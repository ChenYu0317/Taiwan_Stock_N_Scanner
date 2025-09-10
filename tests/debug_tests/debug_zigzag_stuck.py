#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
調試ZigZag算法卡住的原因
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'signal'))

import pandas as pd
import sqlite3

def debug_zigzag_stuck():
    """調試ZigZag算法為什麼卡在6/24"""
    print("🐛 調試ZigZag算法卡住問題")
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
    
    # 手動實現ZigZag並加上調試信息
    print("🔄 手動執行ZigZag算法（1.5%敏感度）:")
    min_change_pct = 0.015
    
    points = []
    last_pivot_idx, last_pivot_type = 0, 'L'
    points.append((0, recent_df.iloc[0]['low'], 'L'))
    cand_idx = 0
    
    print(f"   初始: 第0天 {recent_df.iloc[0]['date']} 低點{recent_df.iloc[0]['low']:.1f}")
    
    for i in range(1, len(recent_df)):
        current_date = recent_df.iloc[i]['date']
        
        if last_pivot_type == 'L':
            # 尋找高點
            if recent_df.iloc[i]['high'] >= recent_df.iloc[cand_idx]['high']:
                cand_idx = i
            
            # 計算變化幅度
            change_pct = (recent_df.iloc[cand_idx]['high'] - recent_df.iloc[last_pivot_idx]['low']) / recent_df.iloc[last_pivot_idx]['low']
            
            if change_pct >= min_change_pct:
                cand_date = recent_df.iloc[cand_idx]['date']
                cand_high = recent_df.iloc[cand_idx]['high']
                last_low = recent_df.iloc[last_pivot_idx]['low']
                
                print(f"   → 第{i}天 {current_date}: 找到高點候選 第{cand_idx}天 {cand_date} 高{cand_high:.1f}")
                print(f"     變化: {last_low:.1f} → {cand_high:.1f} = {change_pct:.2%} ≥ 1.5% ✅")
                
                points.append((cand_idx, cand_high, 'H'))
                last_pivot_idx, last_pivot_type = cand_idx, 'H'
                cand_idx = i
                
                print(f"     ✅ 確認高點: 第{last_pivot_idx}天 {cand_date} {cand_high:.1f}")
                
                # 如果已經有6個點就停止調試
                if len(points) >= 8:
                    print(f"   ... (已找到8個點，繼續執行但不顯示詳情)")
                    break
        
        else:  # last_pivot_type == 'H'
            # 尋找低點
            if recent_df.iloc[i]['low'] <= recent_df.iloc[cand_idx]['low']:
                cand_idx = i
            
            # 計算變化幅度
            change_pct = (recent_df.iloc[last_pivot_idx]['high'] - recent_df.iloc[cand_idx]['low']) / recent_df.iloc[last_pivot_idx]['high']
            
            if change_pct >= min_change_pct:
                cand_date = recent_df.iloc[cand_idx]['date']
                cand_low = recent_df.iloc[cand_idx]['low']
                last_high = recent_df.iloc[last_pivot_idx]['high']
                
                print(f"   → 第{i}天 {current_date}: 找到低點候選 第{cand_idx}天 {cand_date} 低{cand_low:.1f}")
                print(f"     變化: {last_high:.1f} → {cand_low:.1f} = {change_pct:.2%} ≥ 1.5% ✅")
                
                points.append((cand_idx, cand_low, 'L'))
                last_pivot_idx, last_pivot_type = cand_idx, 'L'
                cand_idx = i
                
                print(f"     ✅ 確認低點: 第{last_pivot_idx}天 {cand_date} {cand_low:.1f}")
                
                # 如果已經有6個點就停止調試
                if len(points) >= 8:
                    print(f"   ... (已找到8個點，繼續執行但不顯示詳情)")
                    break
    
    print(f"\n📊 總共找到 {len(points)} 個轉折點")
    print(f"   最後一個轉折點: 第{points[-1][0]}天 {recent_df.iloc[points[-1][0]]['date']}")
    
    # 檢查最後的狀態
    print(f"\n🎯 算法結束時的狀態:")
    print(f"   last_pivot_idx: {last_pivot_idx}")
    print(f"   last_pivot_type: {last_pivot_type}")
    print(f"   cand_idx: {cand_idx}")
    print(f"   數據總長度: {len(recent_df)}")
    
    # 檢查6/24之後發生了什麼
    june24_idx = None
    for i, (idx, price, type_) in enumerate(points):
        date = recent_df.iloc[idx]['date']
        if '2025-06-24' in date:
            june24_idx = idx
            break
    
    if june24_idx is not None:
        print(f"\n🔍 6/24之後的數據分析:")
        print(f"   6/24是第{june24_idx}天，價格{points[-1][1]:.1f}")
        
        # 檢查6/24之後的價格變化
        june24_price = recent_df.iloc[june24_idx]['high']
        print(f"\n   6/24之後的價格走勢:")
        for i in range(june24_idx+1, min(june24_idx+10, len(recent_df))):
            row = recent_df.iloc[i]
            change_from_june24 = (june24_price - row['low']) / june24_price
            print(f"     第{i}天 {row['date']}: 低{row['low']:.1f}, 相對6/24變化 {change_from_june24:.2%}")
            if change_from_june24 >= 0.015:
                print(f"       ★ 這裡應該產生新的低點轉折！")
                break

if __name__ == "__main__":
    debug_zigzag_stuck()