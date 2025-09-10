#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用例外規則的完整N字掃描系統
主要篩選：AB≥3天，BC≥3天，波段≥6%
例外允許：快速但高品質的型態
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import pandas as pd
import sqlite3
from datetime import datetime
from n_pattern_detector import NPatternDetector

def scan_with_exception_rules():
    """使用例外規則進行全市場掃描"""
    print("🎯 N字回撤掃描系統 - 例外規則版")
    print("="*60)
    
    # 升級版參數配置
    detector = NPatternDetector(
        lookback_bars=60,
        use_dynamic_zigzag=True,      # 動態ZigZag門檻
        zigzag_change_pct=0.020,      # 備用2%固定門檻
        min_leg_pct=0.06,             # 6%最小波段（嚴格）
        retr_min=0.20,
        retr_max=0.80,
        c_tolerance=0.00,
        min_bars_ab=3,                # 標準：AB段≥3天
        max_bars_ab=30,               
        min_bars_bc=3,                # 標準：BC段≥3天
        max_bars_bc=15,               
        max_bars_from_c=12,           # C點新鮮度≤12天
        volume_threshold=1.0
    )
    
    print("📋 篩選策略：")
    print(f"  🎯 主要標準：AB≥{detector.min_bars_ab}天, BC≥{detector.min_bars_bc}天, 漲幅≥{detector.min_leg_pct:.0%}")
    print(f"  ⚡ 例外允許：快速型態但需嚴格條件（ATR動態門檻 + 量比要求）")
    print(f"  📅 新鮮度：C點到今天≤{detector.max_bars_from_c}天")
    
    # 連接資料庫
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
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
    standard_signals = []  # 符合標準型態
    exception_signals = []  # 例外型態
    
    for i, stock_id in enumerate(all_stocks):
        if i % 30 == 0:
            print(f"掃描進度: {i}/{len(all_stocks)} ({i/len(all_stocks)*100:.1f}%) - 已發現{len(signals)}個訊號")
        
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
            
            signal = detector.detect_n_pattern(df, stock_id)
            if signal:
                signals.append(signal)
                
                # 判斷是標準型態還是例外型態
                is_standard = (
                    signal.bars_ab >= detector.min_bars_ab and
                    signal.bars_bc >= detector.min_bars_bc
                )
                
                if is_standard:
                    standard_signals.append(signal)
                    print(f"✅ {stock_id}: 標準型態, 評分{signal.score}, AB:{signal.bars_ab}天, BC:{signal.bars_bc}天")
                else:
                    exception_signals.append(signal)
                    print(f"⚡ {stock_id}: 例外型態, 評分{signal.score}, AB:{signal.bars_ab}天, BC:{signal.bars_bc}天")
        
        except Exception as e:
            continue
    
    conn.close()
    
    # 結果統計
    print(f"\n" + "="*60)
    print(f"🎉 掃描完成！總計發現 {len(signals)} 個N字訊號")
    print(f"  📈 標準型態：{len(standard_signals)} 個")
    print(f"  ⚡ 例外型態：{len(exception_signals)} 個")
    
    if not signals:
        print("❌ 未發現符合條件的訊號")
        return
    
    # 按C點日期排序（最新的在前）
    sorted_signals = sorted(signals, key=lambda s: s.C_date, reverse=True)
    
    # 顯示前15名
    print(f"\n🏆 前15個最新訊號（按C點日期排序）：")
    print(f"{'股票':<6} {'型態':<4} {'評分':<4} {'C點日期':<12} {'漲幅':<8} {'回撤':<8} {'AB天':<4} {'BC天':<4} {'新鮮':<4}")
    print("-" * 75)
    
    for signal in sorted_signals[:15]:
        signal_type = "標準" if signal.bars_ab >= 3 and signal.bars_bc >= 3 else "例外"
        print(f"{signal.stock_id:<6} {signal_type:<4} {signal.score:<4} {signal.C_date:<12} {signal.rise_pct:.1%}   {signal.retr_pct:.1%}   {signal.bars_ab:<4} {signal.bars_bc:<4} {signal.bars_c_to_signal:<4}")
    
    # 匯出CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"n_pattern_signals_exception_rules_{timestamp}.csv"
    export_to_csv(sorted_signals, filename)
    
    print(f"\n📁 已匯出CSV：{filename}")
    print(f"🗂️  檔案路徑：{os.path.abspath(filename)}")

def export_to_csv(signals, filename):
    """匯出訊號到CSV"""
    import csv
    
    # 股票名稱對應
    STOCK_NAMES = {
        '1101': '台泥', '1102': '亞泥', '1108': '幸福', '1213': '大飲', '1215': '卜蜂',
        '1304': '台聚', '1305': '華夏', '1326': '台化', '1440': '南紡', '1476': '儒鴻',
        '1773': '勝一', '1789': '神隆', '2032': '新鋼', '2033': '佳大', '2204': '中華',
        '2207': '和泰車', '2227': '裕日車', '2301': '光寶科', '2303': '聯電', '2308': '台達電',
        '2317': '鴻海', '2327': '國巨', '2329': '華碩', '2330': '台積電', '2337': '漢唐',
        '2344': '華邦電', '2345': '智邦', '2351': '順德', '2352': '佳世達', '2355': '敬鵬',
        '2360': '致茂', '2368': '金像電', '2369': '菱生', '2374': '佳能', '2375': '智寶',
        '2376': '技嘉', '2379': '瑞昱', '2380': '虹光', '2382': '廣達', '2395': '研華',
        '2408': '南亞科', '2409': '友達', '2454': '聯發科', '2501': '國建', '2505': '國揚',
        '2506': '太設', '2511': '太子', '2515': '中工', '2516': '新建', '2520': '冠德',
        '2524': '京城', '2809': '京城銀', '2820': '華票', '2832': '台產', '2850': '新產',
        '2855': '統一證', '2867': '三商壽', '3481': '群創', '4966': '譜瑞-KY', '4967': '十銓',
        '5471': '松翰', '5483': '中美晶', '5525': '順天', '6442': '光聖', '6451': '訊芯-KY',
        '6456': 'GIS-KY', '6488': '環球晶', '6525': '捷敏-KY', '6531': '愛普', '8027': '鈦昇'
    }
    
    def get_stock_name(stock_id):
        return STOCK_NAMES.get(stock_id, stock_id)
    
    # 準備CSV資料
    csv_data = []
    
    for signal in signals:
        signal_type = "標準型態" if signal.bars_ab >= 3 and signal.bars_bc >= 3 else "例外型態"
        
        # 計算時間間距
        from datetime import datetime
        A_dt = datetime.strptime(signal.A_date, '%Y-%m-%d')
        B_dt = datetime.strptime(signal.B_date, '%Y-%m-%d')
        C_dt = datetime.strptime(signal.C_date, '%Y-%m-%d')
        signal_dt = datetime.strptime(signal.signal_date, '%Y-%m-%d')
        
        days_AB = (B_dt - A_dt).days
        days_BC = (C_dt - B_dt).days
        days_C_to_signal = (signal_dt - C_dt).days
        
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
            days_AB, days_BC, days_C_to_signal,
            signal.rsi14, signal.ema5, signal.ema20, signal.volume_ratio,
            "是" if signal.trigger_break_yesterday_high else "否",
            "是" if signal.trigger_ema5_volume else "否",
            "是" if signal.trigger_rsi_strong else "否",
            signal.score_breakdown.get('retracement', 0),
            signal.score_breakdown.get('volume', 0),
            signal.score_breakdown.get('early_entry', 0),
            signal.score_breakdown.get('moving_average', 0),
            signal.score_breakdown.get('health', 0),
        ]
        csv_data.append(row)
    
    # 寫入CSV
    headers = [
        '股票代號', '股票名稱', '型態類型', '綜合評分',
        'A點日期', 'A點價格', 'B點日期', 'B點價格', 'C點日期', 'C點價格', '訊號日期',
        '上漲幅度', '回撤比例', 'AB段天數', 'BC段天數', 'C到訊號天數',
        'RSI14', 'EMA5', 'EMA20', '量比',
        '突破昨高', 'EMA5量增', 'RSI強勢',
        '回撤評分', '量能評分', '早進評分', '均線評分', '健康評分'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        writer.writerows(csv_data)

if __name__ == "__main__":
    scan_with_exception_rules()