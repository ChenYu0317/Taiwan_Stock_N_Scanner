#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試不同ZigZag敏感度對台積電8/22-8/28的影響
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'signal'))
from n_pattern_detector import ZigZagDetector, NPatternDetector

import pandas as pd
import sqlite3

def test_zigzag_sensitivity_for_tsmc():
    """測試不同ZigZag敏感度對台積電的影響"""
    print("🔍 測試ZigZag敏感度對台積電8/22-8/28的影響")
    print("="*70)
    
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
    
    # 找到8/22, 8/27, 8/28在數據中的位置
    aug22_idx = recent_df[recent_df['date'] == '2025-08-22'].index
    aug27_idx = recent_df[recent_df['date'] == '2025-08-27'].index  
    aug28_idx = recent_df[recent_df['date'] == '2025-08-28'].index
    
    if len(aug22_idx) == 0 or len(aug27_idx) == 0 or len(aug28_idx) == 0:
        print("❌ 找不到8/22, 8/27, 8/28的資料")
        return
    
    aug22_idx, aug27_idx, aug28_idx = aug22_idx[0], aug27_idx[0], aug28_idx[0]
    
    print(f"📊 關鍵日期在數據中的位置:")
    print(f"   8/22 (A點): 第{aug22_idx}天, 低點{recent_df.iloc[aug22_idx]['low']:.1f}")
    print(f"   8/27 (B點): 第{aug27_idx}天, 高點{recent_df.iloc[aug27_idx]['high']:.1f}")
    print(f"   8/28 (C點): 第{aug28_idx}天, 低點{recent_df.iloc[aug28_idx]['low']:.1f}")
    
    # 測試不同ZigZag敏感度
    sensitivities = [0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04]
    
    for sensitivity in sensitivities:
        print(f"\n🔄 ZigZag敏感度: {sensitivity:.1%}")
        print("-" * 50)
        
        zigzag = ZigZagDetector(min_change_pct=sensitivity)
        points = zigzag.detect(recent_df)
        
        print(f"   找到 {len(points)} 個轉折點")
        
        # 檢查是否包含我們期望的轉折點
        contains_aug22 = False
        contains_aug27 = False  
        contains_aug28 = False
        
        relevant_points = []
        
        for idx, price, type_ in points:
            date = recent_df.iloc[idx]['date']
            
            # 檢查是否是我們關注的日期附近
            if abs(idx - aug22_idx) <= 1:  # 8/22附近
                contains_aug22 = True
                relevant_points.append((idx, price, type_, date, "接近8/22"))
            elif abs(idx - aug27_idx) <= 1:  # 8/27附近
                contains_aug27 = True
                relevant_points.append((idx, price, type_, date, "接近8/27"))
            elif abs(idx - aug28_idx) <= 1:  # 8/28附近
                contains_aug28 = True
                relevant_points.append((idx, price, type_, date, "接近8/28"))
        
        if relevant_points:
            print(f"   🎯 期間相關轉折點:")
            for idx, price, type_, date, note in relevant_points:
                print(f"     {type_} {price:.1f} ({date}) - {note}")
        
        # 檢查能否形成L-H-L
        if len(points) >= 3:
            lhl_found = False
            for i in range(len(points)-1, 1, -1):
                if i < 2:
                    break
                
                C_idx, C_price, C_type = points[i]
                B_idx, B_price, B_type = points[i-1]
                A_idx, A_price, A_type = points[i-2]
                
                if A_type == 'L' and B_type == 'H' and C_type == 'L':
                    # 檢查是否接近我們的目標日期
                    A_date = recent_df.iloc[A_idx]['date']
                    B_date = recent_df.iloc[B_idx]['date']
                    C_date = recent_df.iloc[C_idx]['date']
                    
                    # 如果A在8/20之後，B在8/25之後，C在8/27之後
                    if (A_date >= '2025-08-20' and B_date >= '2025-08-25' and C_date >= '2025-08-27'):
                        rise_pct = (B_price - A_price) / A_price
                        retr_pct = (B_price - C_price) / (B_price - A_price)
                        
                        print(f"   📈 找到相關L-H-L形態:")
                        print(f"     A={A_price:.1f}({A_date}) B={B_price:.1f}({B_date}) C={C_price:.1f}({C_date})")
                        print(f"     漲幅={rise_pct:.1%}, 回撤={retr_pct:.1%}")
                        
                        # 檢查4%標準
                        if rise_pct >= 0.04 and 0.20 <= retr_pct <= 0.80:
                            print(f"   ✅ 符合4%標準的N字形態！")
                            
                            # 用完整演算法測試
                            detector = NPatternDetector(
                                lookback_bars=60,
                                zigzag_change_pct=sensitivity,
                                min_leg_pct=0.04,
                                retr_min=0.20,
                                retr_max=0.80,
                                c_tolerance=0.00
                            )
                            
                            signal = detector.detect_n_pattern(df, "2330")
                            if signal:
                                print(f"   🎉 完整演算法確認: 找到N字訊號！評分{signal.score}")
                        
                        lhl_found = True
                        break
            
            if not lhl_found:
                print(f"   ❌ 未找到相關期間的L-H-L形態")
        else:
            print(f"   ❌ 轉折點不足以形成L-H-L")
    
    print(f"\n📋 總結:")
    print(f"手動計算的理想N字 (8/22→8/27→8/28):")
    print(f"- 需要ZigZag能識別這3個關鍵轉折點")
    print(f"- 8/22低點1135 → 8/27高點1190 (4.85%漲幅)")
    print(f"- 8/27高點1190 → 8/28低點1160 (54.5%回撤)")
    print(f"- 關鍵是找到合適的ZigZag敏感度來捕捉這個形態")

def calculate_required_sensitivity():
    """計算捕捉8/22-8/28形態所需的ZigZag敏感度"""
    print(f"\n🧮 計算所需的ZigZag敏感度:")
    
    # 關鍵變化幅度
    aug22_to_aug27 = (1190 - 1135) / 1135  # 4.85%
    aug27_to_aug28 = (1190 - 1160) / 1190  # 2.52%
    
    print(f"   8/22→8/27: {aug22_to_aug27:.2%}")
    print(f"   8/27→8/28: {aug27_to_aug28:.2%}")
    print(f"   最小變化: {min(aug22_to_aug27, aug27_to_aug28):.2%}")
    print(f"   建議ZigZag敏感度: ≤{min(aug22_to_aug27, aug27_to_aug28):.2%}")

if __name__ == "__main__":
    test_zigzag_sensitivity_for_tsmc()
    calculate_required_sensitivity()