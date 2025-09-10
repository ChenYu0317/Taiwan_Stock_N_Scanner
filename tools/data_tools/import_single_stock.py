#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
導入單一股票的歷史資料
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'signal'))
from n_pattern_detector import NPatternDetector

import pandas as pd
import sqlite3
import requests
from datetime import datetime, timedelta
import time

def get_stock_data_from_yahoo(stock_id, days=60):
    """從Yahoo Finance獲取股票數據"""
    print(f"📊 從Yahoo Finance獲取 {stock_id} 的資料...")
    
    # 台股代號需要加.TW後綴
    symbol = f"{stock_id}.TW"
    
    # 計算日期範圍（多取一些以防假日）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days+30)
    
    # Yahoo Finance API URL
    url = "https://query1.finance.yahoo.com/v7/finance/download/" + symbol
    params = {
        'period1': int(start_date.timestamp()),
        'period2': int(end_date.timestamp()),
        'interval': '1d',
        'events': 'history'
    }
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        # 解析CSV數據
        from io import StringIO
        df = pd.read_csv(StringIO(response.text))
        
        # 清理數據
        df = df.dropna()
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        
        # 重命名欄位以符合我們的格式
        df = df.rename(columns={
            'Date': 'date',
            'Open': 'open',
            'High': 'high', 
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })
        
        # 格式化日期
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')
        
        # 取最後60筆
        df = df.tail(60).reset_index(drop=True)
        
        print(f"✅ 成功獲取 {len(df)} 筆資料")
        print(f"   日期範圍: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}")
        print(f"   價格範圍: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
        
        return df
        
    except Exception as e:
        print(f"❌ Yahoo Finance 獲取失敗: {e}")
        return None

def get_stock_data_from_twse_api(stock_id, days=60):
    """從台灣證交所API獲取股票數據"""
    print(f"📊 從TWSE API獲取 {stock_id} 的資料...")
    
    all_data = []
    
    # 獲取最近幾個月的數據
    for i in range(3):  # 獲取最近3個月
        date = datetime.now() - timedelta(days=i*30)
        year = date.year
        month = date.month
        
        url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY"
        params = {
            'response': 'json',
            'date': f'{year}{month:02d}01',
            'stockNo': stock_id
        }
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            if 'data' in data and data['data']:
                for row in data['data']:
                    all_data.append({
                        'date': f"{int(row[0][:3])+1911}-{row[0][4:6]}-{row[0][7:9]}",
                        'volume': int(row[1].replace(',', '')),
                        'open': float(row[3]),
                        'high': float(row[4]),
                        'low': float(row[5]),
                        'close': float(row[6])
                    })
            
            time.sleep(0.5)  # 避免請求太頻繁
            
        except Exception as e:
            print(f"⚠️  {year}-{month:02d} 資料獲取失敗: {e}")
            continue
    
    if all_data:
        df = pd.DataFrame(all_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').drop_duplicates().reset_index(drop=True)
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')
        df = df.tail(60).reset_index(drop=True)
        
        print(f"✅ 成功獲取 {len(df)} 筆資料")
        return df
    
    return None

def insert_stock_data_to_db(stock_id, df, db_path='data/cleaned/taiwan_stocks_cleaned.db'):
    """將股票數據插入資料庫"""
    print(f"💾 將 {stock_id} 資料插入資料庫...")
    
    conn = sqlite3.connect(db_path)
    
    try:
        # 檢查是否已存在
        existing = pd.read_sql_query(
            "SELECT COUNT(*) as count FROM daily_prices WHERE stock_id = ?", 
            conn, params=(stock_id,)
        )
        
        if existing.iloc[0]['count'] > 0:
            print(f"⚠️  股票 {stock_id} 已存在，先刪除舊資料...")
            conn.execute("DELETE FROM daily_prices WHERE stock_id = ?", (stock_id,))
        
        # 插入新資料
        for _, row in df.iterrows():
            conn.execute("""
                INSERT INTO daily_prices (stock_id, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (stock_id, row['date'], row['open'], row['high'], row['low'], row['close'], row['volume']))
        
        conn.commit()
        print(f"✅ 成功插入 {len(df)} 筆 {stock_id} 資料到資料庫")
        
    except Exception as e:
        print(f"❌ 資料庫插入失敗: {e}")
        conn.rollback()
        
    finally:
        conn.close()

def test_n_pattern_for_stock(stock_id):
    """測試指定股票的N字回撤形態"""
    print(f"\n🎯 測試 {stock_id} 的N字回撤形態")
    print("="*50)
    
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    try:
        # 讀取股票數據
        query = """
        SELECT date, open, high, low, close, volume
        FROM daily_prices 
        WHERE stock_id = ?
        ORDER BY date
        """
        df = pd.read_sql_query(query, conn, params=(stock_id,))
        
        if len(df) == 0:
            print(f"❌ 沒有找到 {stock_id} 的資料")
            return
        
        print(f"📊 {stock_id} 資料概況:")
        print(f"   總筆數: {len(df)}")
        print(f"   日期範圍: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}")
        print(f"   價格範圍: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
        
        # 使用修正後的最優參數
        detector = NPatternDetector(
            lookback_bars=60,
            zigzag_change_pct=0.015,  # 1.5%
            min_leg_pct=0.04,         # 4%
            retr_min=0.20,
            retr_max=0.80,
            c_tolerance=0.00,
            min_bars_ab=1,
            max_bars_ab=80,
            min_bars_bc=1,
            max_bars_bc=50,
            volume_threshold=1.0
        )
        
        # 分析ZigZag轉折點
        recent_df = df.tail(60).reset_index(drop=True)
        zigzag_points = detector.zigzag.detect(recent_df)
        
        print(f"\n🔄 ZigZag 轉折點分析:")
        print(f"   找到 {len(zigzag_points)} 個轉折點")
        
        if len(zigzag_points) >= 6:
            print(f"   最後6個轉折點:")
            for i, (idx, price, type_) in enumerate(zigzag_points[-6:]):
                date = recent_df.iloc[idx]['date']
                print(f"     {i+1}. {type_} {price:.2f} ({date}) [第{idx}天]")
        
        # N字形態檢測
        signal = detector.detect_n_pattern(df, stock_id)
        
        if signal:
            print(f"\n✅ 發現N字回撤訊號!")
            print(f"   🏆 評分: {signal.score}/100")
            print(f"   📈 N字形態:")
            print(f"      A點: {signal.A_price:.2f} ({signal.A_date})")
            print(f"      B點: {signal.B_price:.2f} ({signal.B_date})")
            print(f"      C點: {signal.C_price:.2f} ({signal.C_date})")
            print(f"   📊 幅度統計:")
            print(f"      上漲幅度: {signal.rise_pct:.1%}")
            print(f"      回撤比例: {signal.retr_pct:.1%}")
            print(f"   🎯 技術指標:")
            print(f"      RSI: {signal.rsi14:.1f}")
            print(f"      EMA5: {signal.ema5:.2f}")
            print(f"      量比: {signal.volume_ratio:.2f}")
            print(f"   ✅ 觸發條件:")
            print(f"      突破昨高: {signal.trigger_break_yesterday_high}")
            print(f"      EMA5量增: {signal.trigger_ema5_volume}")
            print(f"      RSI強勢: {signal.trigger_rsi_strong}")
            print(f"   📝 評分詳細: {signal.score_breakdown}")
            
        else:
            print(f"\n❌ 未發現N字回撤訊號")
            
            # 分析原因
            if len(zigzag_points) < 3:
                print(f"   原因: ZigZag轉折點不足 (需要≥3個，目前{len(zigzag_points)}個)")
            else:
                abc_result = detector.find_last_abc_pattern(zigzag_points, recent_df)
                if abc_result is None:
                    print(f"   原因: 未找到符合條件的ABC形態")
                    # 顯示候選形態的問題
                    for i in range(len(zigzag_points) - 1, 1, -1):
                        if i < 2:
                            break
                        
                        C_idx, C_price, C_type = zigzag_points[i]
                        B_idx, B_price, B_type = zigzag_points[i-1]
                        A_idx, A_price, A_type = zigzag_points[i-2]
                        
                        if A_type == 'L' and B_type == 'H' and C_type == 'L':
                            rise_pct = (B_price - A_price) / A_price
                            retr_pct = (B_price - C_price) / (B_price - A_price)
                            
                            print(f"   L-H-L候選: A={A_price:.1f} B={B_price:.1f} C={C_price:.1f}")
                            print(f"   漲幅={rise_pct:.1%} (需要>4%), 回撤={retr_pct:.1%} (需要20-80%)")
                            
                            issues = []
                            if rise_pct < 0.04:
                                issues.append("漲幅不足")
                            if retr_pct < 0.20 or retr_pct > 0.80:
                                issues.append("回撤超範圍")
                            if C_price < A_price:
                                issues.append("C點破A點")
                            
                            if issues:
                                print(f"   問題: {', '.join(issues)}")
                            break
                else:
                    print(f"   原因: ABC形態存在但觸發條件不足")
        
    except Exception as e:
        print(f"❌ 分析錯誤: {e}")
    
    finally:
        conn.close()

def main():
    """主函數"""
    stock_id = "3416"  # 融程電
    
    print(f"🚀 導入並分析融程電 ({stock_id})")
    print("="*60)
    
    # 嘗試不同數據源獲取股票數據
    df = None
    
    # 先嘗試Yahoo Finance
    df = get_stock_data_from_yahoo(stock_id)
    
    # 如果Yahoo失敗，嘗試TWSE API
    if df is None:
        df = get_stock_data_from_twse_api(stock_id)
    
    if df is None:
        print(f"❌ 無法獲取 {stock_id} 的資料")
        return
    
    # 插入資料庫
    insert_stock_data_to_db(stock_id, df)
    
    # 測試N字回撤
    test_n_pattern_for_stock(stock_id)

if __name__ == "__main__":
    main()