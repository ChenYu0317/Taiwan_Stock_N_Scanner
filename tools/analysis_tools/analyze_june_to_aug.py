#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析6/24到8月期間的價格變化
"""

import pandas as pd
import sqlite3

def analyze_june_to_aug():
    """分析6/24到8月的價格變化"""
    print("🔍 分析6/24到8月的價格變化")
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
    
    # 找到6/24的索引
    june24_idx = 5  # 我們知道是第5天
    june24_high = recent_df.iloc[june24_idx]['high']  # 1050.0
    
    print(f"📊 6/24基準點: 第{june24_idx}天, 高點{june24_high:.1f}")
    
    # 分析6/24之後的重要變化
    print(f"\n📈 6/24之後的重要價格變化:")
    print(f"{'日期':<12} {'高點':<8} {'低點':<8} {'vs 6/24高':<12} {'可能轉折'}")
    print("-"*60)
    
    significant_changes = []
    
    for i in range(june24_idx + 1, len(recent_df)):
        row = recent_df.iloc[i]
        high_change = (row['high'] - june24_high) / june24_high
        low_vs_june24_high = (june24_high - row['low']) / june24_high
        
        # 如果高點比6/24高很多，或低點相對6/24有足夠跌幅
        is_significant = False
        note = ""
        
        if high_change > 0.03:  # 高點比6/24高3%以上
            is_significant = True
            note = f"新高點+{high_change:.1%}"
            significant_changes.append(('H', i, row['high'], row['date']))
            
        if low_vs_june24_high > 0.015:  # 低點比6/24高點低1.5%以上
            is_significant = True  
            note += f" 低點跌{low_vs_june24_high:.1%}"
            
        if is_significant:
            print(f"{row['date']:<12} {row['high']:<8.1f} {row['low']:<8.1f} {high_change:>+6.1%}     {note}")
    
    print(f"\n🎯 期間內應該產生的重要轉折點:")
    for i, (ptype, idx, price, date) in enumerate(significant_changes):
        print(f"   {i+1}. {ptype}點 {price:.1f} ({date}) [第{idx}天]")
    
    # 特別檢查8月的變化
    print(f"\n📅 8月關鍵變化:")
    
    # 8/7的突破
    aug7_idx = recent_df[recent_df['date'] == '2025-08-07'].index[0]
    aug7_high = recent_df.iloc[aug7_idx]['high']
    change_june24_to_aug7 = (aug7_high - june24_high) / june24_high
    print(f"   8/7: 高點{aug7_high:.1f}, 相對6/24高點漲{change_june24_to_aug7:.1%}")
    
    # 8/20的大跌
    aug20_idx = recent_df[recent_df['date'] == '2025-08-20'].index[0]  
    aug20_low = recent_df.iloc[aug20_idx]['low']
    
    # 找到8/20之前的最近高點
    prev_high = 0
    prev_high_idx = 0
    for i in range(aug20_idx-1, -1, -1):
        if recent_df.iloc[i]['high'] > prev_high:
            prev_high = recent_df.iloc[i]['high']
            prev_high_idx = i
            
    change_prev_high_to_aug20 = (prev_high - aug20_low) / prev_high
    print(f"   8/20: 低點{aug20_low:.1f}, 相對前高{prev_high:.1f}跌{change_prev_high_to_aug20:.1%}")
    
    # 8/27的反彈
    aug27_idx = recent_df[recent_df['date'] == '2025-08-27'].index[0]
    aug27_high = recent_df.iloc[aug27_idx]['high'] 
    aug22_low = recent_df.iloc[recent_df[recent_df['date'] == '2025-08-22'].index[0]]['low']
    change_aug22_to_aug27 = (aug27_high - aug22_low) / aug22_low
    print(f"   8/22→8/27: {aug22_low:.1f}→{aug27_high:.1f}, 漲{change_aug22_to_aug27:.1%}")
    
    # 8/28的回撤  
    aug28_idx = recent_df[recent_df['date'] == '2025-08-28'].index[0]
    aug28_low = recent_df.iloc[aug28_idx]['low']
    change_aug27_to_aug28 = (aug27_high - aug28_low) / aug27_high
    print(f"   8/27→8/28: {aug27_high:.1f}→{aug28_low:.1f}, 跌{change_aug27_to_aug28:.1%}")
    
    print(f"\n💡 結論:")
    print(f"   1. 6/24(1050)→8/7(1180): +{change_june24_to_aug7:.1%} 應產生新高點")
    print(f"   2. 8/13前後高點→8/20低點: -{change_prev_high_to_aug20:.1%} 應產生新低點") 
    print(f"   3. 8/22→8/27: +{change_aug22_to_aug27:.1%} 應產生新高點")
    print(f"   4. 8/27→8/28: -{change_aug27_to_aug28:.1%} 應產生新低點")
    print(f"   ★ ZigZag應該至少包含這4個主要轉折點！")

if __name__ == "__main__":
    analyze_june_to_aug()