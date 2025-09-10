#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試最終修正版演算法 - 全200檔股票掃描
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import pandas as pd
import sqlite3
from datetime import datetime
from n_pattern_detector import NPatternDetector

def scan_all_stocks():
    """掃描所有股票（>=60筆資料的）"""
    print("🎯 最終版N字演算法 - 全市場掃描")
    print("="*60)
    
    # 使用修正後的嚴格參數
    detector = NPatternDetector(
        lookback_bars=60,
        use_dynamic_zigzag=True,      # 動態ZigZag門檻
        zigzag_change_pct=0.020,      # 固定門檻備用2%
        # 動態ZigZag參數
        atr_len=14,                   # ATR計算期間
        atr_smooth=5,                 # ATR平滑期間
        atr_multiplier=0.8,           # ATR倍數
        zigzag_floor=0.02,            # 動態門檻下限2%
        zigzag_cap=0.05,              # 動態門檻上限5%
        # 波段與回撤參數
        min_leg_pct=0.06,             # 6%最小波段（嚴格）
        retr_min=0.20,                # 20%最小回撤
        retr_max=0.80,                # 80%最大回撤
        c_tolerance=0.00,             # C不可破A
        # 時間護欄參數（你的嚴格標準 + 例外條件）
        min_bars_ab=3,                # AB段標準≥3天
        max_bars_ab=30,               # AB段最多30天
        min_bars_bc=3,                # BC段標準≥3天  
        max_bars_bc=15,               # BC段最多15天
        max_bars_from_c=12,           # C點新鮮度≤12天
        # 技術指標參數
        volume_threshold=1.0          # 量能門檻
    )
    
    print("📋 演算法配置：")
    print(f"  🎯 主要標準：AB≥{detector.min_bars_ab}天, BC≥{detector.min_bars_bc}天, 漲幅≥{detector.min_leg_pct:.0%}")
    print(f"  ⚡ AB例外：<{detector.min_bars_ab}天但漲幅≥max(6%, 1.8×ATR) + B當天量比≥1.5")
    print(f"  ⚡ BC例外：=2天但回撤30%-70% + C當天量比≥1.2")
    print(f"  📅 新鮮度：C點到今天≤{detector.max_bars_from_c}天")
    print(f"  🔄 動態ZigZag：{detector.zigzag_floor:.1%}-{detector.zigzag_cap:.1%} (ATR×{detector.atr_multiplier})")
    
    # 連接資料庫
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    # 獲取所有有足夠資料的股票
    stock_query = """
    SELECT DISTINCT stock_id, COUNT(*) as record_count
    FROM daily_prices
    GROUP BY stock_id
    HAVING COUNT(*) >= 60
    ORDER BY stock_id
    """
    
    stock_result = pd.read_sql_query(stock_query, conn)
    all_stocks = stock_result['stock_id'].tolist()
    
    print(f"\n🚀 開始掃描 {len(all_stocks)} 檔股票...")
    print("-" * 60)
    
    signals = []
    standard_signals = []    # 標準型態（AB≥3, BC≥3）
    ab_exception_signals = [] # AB例外型態
    bc_exception_signals = [] # BC例外型態
    both_exception_signals = []  # AB和BC都是例外
    
    for i, stock_id in enumerate(all_stocks):
        # 每30檔顯示進度
        if i % 30 == 0:
            print(f"掃描進度: {i:>3}/{len(all_stocks)} ({i/len(all_stocks)*100:>5.1f}%) - 已發現 {len(signals)} 個訊號")
        
        try:
            query = """
            SELECT date, open, high, low, close, volume
            FROM daily_prices 
            WHERE stock_id = ?
            ORDER BY date
            """
            df = pd.read_sql_query(query, conn, params=(stock_id,))
            
            if len(df) < 60:
                continue
            
            # 檢測N字形態
            signal = detector.detect_n_pattern(df, stock_id)
            if signal:
                signals.append(signal)
                
                # 分類型態類型
                is_ab_exception = signal.ab_is_exception
                is_bc_exception = signal.bc_is_exception
                
                if is_ab_exception and is_bc_exception:
                    both_exception_signals.append(signal)
                    type_str = "雙例外"
                elif is_ab_exception:
                    ab_exception_signals.append(signal)
                    type_str = "AB例外"
                elif is_bc_exception:
                    bc_exception_signals.append(signal)
                    type_str = "BC例外"
                else:
                    standard_signals.append(signal)
                    type_str = "標準"
                
                print(f"✅ {stock_id}: {type_str}, 評分{signal.score:>2}, AB:{signal.bars_ab}天, BC:{signal.bars_bc}天, 漲{signal.rise_pct:.1%}")
        
        except Exception as e:
            continue
    
    conn.close()
    
    # 詳細統計結果
    print(f"\n" + "="*60)
    print(f"🎉 掃描完成！從 {len(all_stocks)} 檔股票中發現 {len(signals)} 個N字訊號")
    print(f"  📈 標準型態：{len(standard_signals)} 個 (AB≥3天 且 BC≥3天)")
    print(f"  ⚡ AB例外：{len(ab_exception_signals)} 個 (AB<3天但高品質)")
    print(f"  ⚡ BC例外：{len(bc_exception_signals)} 個 (BC=2天但高品質)")  
    print(f"  ⚡ 雙例外：{len(both_exception_signals)} 個 (AB和BC都例外)")
    
    if not signals:
        print("\n❌ 未發現符合條件的訊號")
        print("💡 可考慮放寬參數或檢查市場狀況")
        return
    
    # 按C點日期排序（最新的在前）
    sorted_signals = sorted(signals, key=lambda s: s.C_date, reverse=True)
    
    print(f"\n🏆 所有訊號詳情（按C點日期排序）：")
    print(f"{'股票':<6} {'型態':<6} {'評分':<4} {'C點日期':<12} {'漲幅':<8} {'回撤':<8} {'AB天':<4} {'BC天':<4} {'新鮮':<4}")
    print("-" * 80)
    
    for signal in sorted_signals:
        # 判斷型態類型
        if signal.ab_is_exception and signal.bc_is_exception:
            signal_type = "雙例外"
        elif signal.ab_is_exception:
            signal_type = "AB例外"
        elif signal.bc_is_exception:
            signal_type = "BC例外"
        else:
            signal_type = "標準"
            
        print(f"{signal.stock_id:<6} {signal_type:<6} {signal.score:<4} {signal.C_date:<12} {signal.rise_pct:.1%}   {signal.retr_pct:.1%}   {signal.bars_ab:<4} {signal.bars_bc:<4} {signal.bars_c_to_signal:<4}")
    
    # 分析例外條件效果
    print(f"\n📊 例外條件分析：")
    total_exceptions = len(ab_exception_signals) + len(bc_exception_signals) + len(both_exception_signals)
    if total_exceptions > 0:
        print(f"  例外型態佔比：{total_exceptions/len(signals)*100:.1f}% ({total_exceptions}/{len(signals)})")
        print(f"  平均評分 - 標準：{sum(s.score for s in standard_signals)/max(len(standard_signals),1):.1f}, 例外：{sum(s.score for s in signals if s.ab_is_exception or s.bc_is_exception)/max(total_exceptions,1):.1f}")
    else:
        print(f"  所有訊號都是標準型態（符合AB≥3天, BC≥3天）")
    
    # 匯出結果
    if len(signals) > 0:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"n_pattern_final_scan_{timestamp}.csv"
        export_to_csv(sorted_signals, filename)
        print(f"\n📁 已匯出CSV：{filename}")
    
    return signals

def export_to_csv(signals, filename):
    """匯出訊號到CSV"""
    import csv
    
    # 股票名稱對應（簡化版）
    STOCK_NAMES = {
        '1101': '台泥', '1102': '亞泥', '2033': '佳大', '2317': '鴻海', '2330': '台積電',
        '2368': '金像電', '2501': '國建', '2505': '國揚', '2506': '太設', '2511': '太子',
        '2520': '冠德', '2820': '華票', '5525': '順天'
    }
    
    def get_stock_name(stock_id):
        return STOCK_NAMES.get(stock_id, stock_id)
    
    # 準備CSV資料
    csv_data = []
    
    for signal in signals:
        # 判斷型態類型
        if signal.ab_is_exception and signal.bc_is_exception:
            signal_type = "雙例外型態"
        elif signal.ab_is_exception:
            signal_type = "AB例外型態"
        elif signal.bc_is_exception:
            signal_type = "BC例外型態"
        else:
            signal_type = "標準型態"
        
        row = [
            signal.stock_id,
            get_stock_name(signal.stock_id),
            signal_type,
            signal.score,
            signal.A_date, signal.A_price,
            signal.B_date, signal.B_price,
            signal.C_date, signal.C_price,
            signal.signal_date,
            f"{signal.rise_pct*100:.2f}%",
            f"{signal.retr_pct*100:.1f}%",
            signal.bars_ab, signal.bars_bc, signal.bars_c_to_signal,
            "是" if signal.ab_is_exception else "否",
            "是" if signal.bc_is_exception else "否",
            signal.rsi14, signal.ema5, signal.ema20, signal.volume_ratio,
            "是" if signal.trigger_break_yesterday_high else "否",
            "是" if signal.trigger_ema5_volume else "否",
            "是" if signal.trigger_rsi_strong else "否"
        ]
        csv_data.append(row)
    
    # 寫入CSV
    headers = [
        '股票代號', '股票名稱', '型態類型', '綜合評分',
        'A點日期', 'A點價格', 'B點日期', 'B點價格', 'C點日期', 'C點價格', '訊號日期',
        '上漲幅度', '回撤比例', 'AB段天數', 'BC段天數', 'C到訊號天數',
        'AB段例外', 'BC段例外', 'RSI14', 'EMA5', 'EMA20', '量比',
        '突破昨高', 'EMA5量增', 'RSI強勢'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        writer.writerows(csv_data)

if __name__ == "__main__":
    signals = scan_all_stocks()