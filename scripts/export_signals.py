#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N字回撤訊號匯出工具
匯出掃描結果為CSV格式，按C點日期排序
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from n_pattern_detector import NPatternDetector

import pandas as pd
import sqlite3
from datetime import datetime
import csv

# 股票名稱對應表 (常見的股票)
STOCK_NAMES = {
    '1101': '台泥',
    '1102': '亞泥', 
    '1108': '幸福',
    '1213': '大飲',
    '1215': '卜蜂',
    '1304': '台聚',
    '1305': '華夏',
    '1326': '台化',
    '1440': '南紡',
    '1476': '儒鴻',
    '1773': '勝一',
    '1789': '神隆',
    '2032': '新鋼',
    '2033': '佳大',
    '2204': '中華',
    '2207': '和泰車',
    '2227': '裕日車',
    '2301': '光寶科',
    '2303': '聯電',
    '2308': '台達電',
    '2317': '鴻海',
    '2327': '國巨',
    '2329': '華碩',
    '2330': '台積電',
    '2337': '漢唐',
    '2344': '華邦電',
    '2345': '智邦',
    '2351': '順德',
    '2352': '佳世達',
    '2355': '敬鵬',
    '2360': '致茂',
    '2368': '金像電',
    '2369': '菱生',
    '2374': '佳能',
    '2375': '智寶',
    '2376': '技嘉',
    '2379': '瑞昱',
    '2380': '虹光',
    '2382': '廣達',
    '2395': '研華',
    '2408': '南亞科',
    '2409': '友達',
    '2454': '聯發科',
    '2501': '國建',
    '2505': '國揚',
    '2506': '太設',
    '2511': '太子',
    '2515': '中工',
    '2516': '新建',
    '2520': '冠德',
    '2524': '京城',
    '2809': '京城銀',
    '2820': '華票',
    '2832': '台產',
    '2850': '新產',
    '2855': '統一證',
    '2867': '三商壽',
    '3481': '群創',
    '4966': '譜瑞-KY',
    '4967': '十銓',
    '5471': '松翰',
    '5483': '中美晶',
    '5525': '順天',
    '6442': '光聖',
    '6451': '訊芯-KY',
    '6456': 'GIS-KY',
    '6488': '環球晶',
    '6525': '捷敏-KY',
    '6531': '愛普',
    '8027': '鈦昇'
}

def get_stock_name(stock_id):
    """取得股票名稱，如果沒有對應則返回股票代號"""
    return STOCK_NAMES.get(stock_id, stock_id)

def scan_and_export_signals():
    """掃描市場並匯出訊號為CSV"""
    print("🚀 掃描N字回撤訊號並匯出CSV")
    print("="*50)
    
    # 使用最優化參數配置
    detector = NPatternDetector(
        lookback_bars=60,
        zigzag_change_pct=0.015,  # 1.5% ZigZag敏感度
        min_leg_pct=0.04,         # 4% 最小波段
        retr_min=0.20,            # 20% 最小回撤
        retr_max=0.80,            # 80% 最大回撤
        c_tolerance=0.00,         # C不可破A
        min_bars_ab=1,            # AB最少1天
        max_bars_ab=80,           # AB最多80天
        min_bars_bc=1,            # BC最少1天
        max_bars_bc=50,           # BC最多50天
        volume_threshold=1.0      # 量能門檻1.0
    )
    
    # 獲取股票清單和掃描
    signals = []
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
    
    print(f"開始掃描 {len(all_stocks)} 檔股票...")
    
    for i, stock_id in enumerate(all_stocks):
        if i % 20 == 0:
            print(f"進度: {i}/{len(all_stocks)} ({i/len(all_stocks)*100:.1f}%)")
        
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
                print(f"✅ {stock_id}: {signal.score}分")
        
        except Exception as e:
            continue
    
    conn.close()
    
    if not signals:
        print("❌ 未發現符合條件的N字回撤訊號")
        return
    
    # 按C點日期排序（越接近今天越前面）
    sorted_signals = sorted(signals, key=lambda s: s.C_date, reverse=True)
    
    print(f"\n📊 共發現 {len(sorted_signals)} 個訊號，開始匯出...")
    
    # 準備CSV資料
    csv_data = []
    
    for signal in sorted_signals:
        # 計算額外參數
        rise_pct = signal.rise_pct * 100  # 轉換為百分比
        retr_pct = signal.retr_pct * 100  # 轉換為百分比
        
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
            signal.stock_id,                    # 股票代號
            get_stock_name(signal.stock_id),    # 股票名稱
            signal.score,                       # 綜合評分
            signal.A_date,                      # A點日期
            signal.A_price,                     # A點價格
            signal.B_date,                      # B點日期
            signal.B_price,                     # B點價格
            signal.C_date,                      # C點日期
            signal.C_price,                     # C點價格
            signal.signal_date,                 # 訊號日期
            f"{rise_pct:.2f}%",                # 上漲幅度
            f"{retr_pct:.1f}%",               # 回撤比例
            days_AB,                           # AB段天數
            days_BC,                           # BC段天數
            days_C_to_signal,                  # C到訊號天數
            signal.rsi14,                      # RSI14
            signal.ema5,                       # EMA5
            signal.ema20,                      # EMA20
            signal.volume_ratio,               # 量比
            "是" if signal.trigger_break_yesterday_high else "否",    # 突破昨高
            "是" if signal.trigger_ema5_volume else "否",             # EMA5量增
            "是" if signal.trigger_rsi_strong else "否",              # RSI強勢
            signal.score_breakdown.get('retracement', 0),            # 回撤評分
            signal.score_breakdown.get('volume', 0),                 # 量能評分
            signal.score_breakdown.get('early_entry', 0),            # 早進評分
            signal.score_breakdown.get('moving_average', 0),         # 均線評分
            signal.score_breakdown.get('health', 0),                 # 健康評分
        ]
        csv_data.append(row)
    
    # 匯出CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"n_pattern_signals_{timestamp}.csv"
    
    headers = [
        '股票代號', '股票名稱', '綜合評分',
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
    
    print(f"✅ 成功匯出 {len(csv_data)} 筆訊號至 {filename}")
    print(f"🗂️ 檔案位置: {os.path.abspath(filename)}")
    
    # 顯示前5筆預覽
    print(f"\n📋 前5筆訊號預覽 (按C點日期排序):")
    print("-" * 100)
    print(f"{'股票':<6} {'名稱':<8} {'評分':<4} {'C點日期':<12} {'訊號日期':<12} {'漲幅':<8} {'回撤':<8}")
    print("-" * 100)
    
    for i, signal in enumerate(sorted_signals[:5]):
        stock_name = get_stock_name(signal.stock_id)
        print(f"{signal.stock_id:<6} {stock_name:<8} {signal.score:<4} {signal.C_date:<12} {signal.signal_date:<12} {signal.rise_pct:.1%}   {signal.retr_pct:.1%}")
    
    print(f"\n🎉 匯出完成！檔案：{filename}")

if __name__ == "__main__":
    scan_and_export_signals()