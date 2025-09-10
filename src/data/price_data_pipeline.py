#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台股歷史價格數據獲取管道
修復Phase 1遺漏：從官方來源獲取真實的歷史OHLC數據
"""

import requests
import pandas as pd
import sqlite3
import time
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import os
from urllib.parse import urlencode
import calendar
from dateutil.relativedelta import relativedelta
from dateutil import tz
import math
import numpy as np
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
from collections import deque

# 台北時區定義
TAIPEI = tz.gettz("Asia/Taipei")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 全域速率限制器
class RateLimiter:
    def __init__(self, max_requests=6, window_seconds=1.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.hits = deque()
    
    def acquire(self):
        """獲取請求許可，如需要會自動等待"""
        now = time.time()
        
        # 移除窗口外的舊請求
        while self.hits and now - self.hits[0] > self.window_seconds:
            self.hits.popleft()
        
        # 如果達到限制，等待到最舊請求過期
        if len(self.hits) >= self.max_requests:
            sleep_time = self.window_seconds - (now - self.hits[0]) + 0.001
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        # 記錄新請求
        self.hits.append(time.time())

# 全域速率限制器實例
rate_limiter = RateLimiter(max_requests=6, window_seconds=1.0)

def sanitize_stock_id(stock_id: str) -> str:
    """校驗股票代碼格式"""
    if not re.fullmatch(r"\d{4}", str(stock_id)):
        raise ValueError(f"invalid stock_id: {stock_id}")
    return stock_id

def ensure_daily_prices_table(conn):
    """建立單一價格事實表"""
    conn.execute("""
    CREATE TABLE IF NOT EXISTS daily_prices (
        stock_id TEXT NOT NULL,
        date DATE NOT NULL,
        open REAL, high REAL, low REAL, close REAL, volume INTEGER,
        market TEXT, source TEXT,
        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (stock_id, date)
    )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prices_date ON daily_prices(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prices_market ON daily_prices(market)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prices_stock_date ON daily_prices(stock_id, date)")
    conn.commit()

class TaiwanStockPriceDataPipeline:
    """台股歷史價格數據管道"""
    
    def __init__(self, db_path: str = "data/cleaned/taiwan_stocks_cleaned.db"):
        self.db_path = db_path
        self.session = requests.Session()
        
        # 優化連線池設定
        adapter = HTTPAdapter(
            pool_connections=100,  # 連線池大小
            pool_maxsize=100,      # 每個連線池的最大連線數
            max_retries=Retry(
                total=3, 
                backoff_factor=0.2,  # 更快的重試
                status_forcelist=[429, 500, 502, 503, 504]
            )
        )
        
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })

    def is_fresh_enough(self, stock_id: str, target_bars: int, freshness_days: int = 7) -> bool:
        """檢查股票數據是否足夠新鮮，避免重複抓取"""
        conn = sqlite3.connect(self.db_path)
        try:
            result = conn.execute(
                "SELECT COUNT(*), MAX(date) FROM daily_prices WHERE stock_id=?",
                (stock_id,)
            ).fetchone()
            c, maxd = result or (0, None)
        finally:
            conn.close()
            
        if not maxd:
            return False
            
        maxd = pd.to_datetime(maxd)
        today = pd.Timestamp.now(tz=TAIPEI).normalize().tz_localize(None)
        
        if c >= target_bars and (today - maxd).days <= freshness_days:
            return True
        return False
        
    def get_stock_list(self) -> List[Tuple[str, str, str]]:
        """從資料庫獲取股票清單"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT stock_id, name, market FROM stock_universe WHERE status='active' ORDER BY stock_id")
            stocks = cursor.fetchall()
            conn.close()
            return stocks
        except Exception as e:
            logger.error(f"獲取股票清單失敗: {e}")
            return []
    
    def fetch_twse_stock_data(self, stock_id: str, year: int, month: int) -> Optional[pd.DataFrame]:
        """
        從TWSE獲取單一股票的月度歷史資料
        
        Args:
            stock_id: 股票代碼
            year: 年份
            month: 月份
            
        Returns:
            DataFrame 或 None
        """
        try:
            # TWSE STOCK_DAY API
            url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
            params = {
                'response': 'json',
                'date': f"{year}{month:02d}01",
                'stockNo': stock_id
            }
            
            rate_limiter.acquire()  # 全域速率限制
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('stat') != 'OK':
                logger.warning(f"TWSE API返回非OK狀態: {stock_id} {year}/{month}")
                return None
                
            if not data.get('data'):
                logger.debug(f"無數據: {stock_id} {year}/{month}")
                return None
            
            # 解析數據
            df = pd.DataFrame(data['data'])
            if len(df) == 0:
                return None
            
            # TWSE 欄位改版韌性 (必補項目3) - 修正版
            fields = data.get('fields') or []
            if fields:
                logger.debug(f"TWSE API 欄位: {fields}")
                
                # 建立欄名映射（支援中英文）
                field_mapping = {}
                for i, field in enumerate(fields):
                    if field in ['日期', 'Date']:
                        field_mapping['date'] = i
                    elif field in ['成交股數', '成交量', 'Volume']:
                        field_mapping['volume'] = i
                    elif field in ['開盤價', '開盤', 'Open']:
                        field_mapping['open'] = i
                    elif field in ['最高價', '最高', 'High']:
                        field_mapping['high'] = i
                    elif field in ['最低價', '最低', 'Low']:
                        field_mapping['low'] = i
                    elif field in ['收盤價', '收盤', 'Close']:
                        field_mapping['close'] = i
                
                # 確認必要欄位都存在
                required_fields = ['date', 'volume', 'open', 'high', 'low', 'close']
                if all(field in field_mapping for field in required_fields):
                    # 只選取需要的欄位並重新排序
                    selected_columns = [field_mapping[field] for field in required_fields]
                    df = df.iloc[:, selected_columns]
                    df.columns = required_fields
                    logger.debug(f"使用智能欄位映射，選取欄位: {required_fields}")
                else:
                    logger.warning(f"TWSE API 欄位結構變更，回退到固定格式: {fields}")
                    missing = [f for f in required_fields if f not in field_mapping]
                    logger.warning(f"缺少欄位: {missing}")
                    
                    # 回退到固定欄位順序（根據實際API回應調整）
                    df.columns = ['date', 'volume', 'turnover', 'open', 'high', 'low', 'close', 'change', 'transaction']
                    # 選取需要的欄位
                    df = df[['date', 'volume', 'open', 'high', 'low', 'close']]
            else:
                # Fallback: 使用固定欄位名稱
                logger.warning("TWSE API 未提供欄位資訊，使用固定格式")
                df.columns = ['date', 'volume', 'turnover', 'open', 'high', 'low', 'close', 'change', 'transaction']
                df = df[['date', 'volume', 'open', 'high', 'low', 'close']]
            
            # 數據清理 - 處理民國年轉西元年
            def convert_roc_date(date_str):
                """轉換民國年日期為西元年"""
                parts = date_str.split('/')
                if len(parts) == 3:
                    roc_year = int(parts[0])
                    month = parts[1]
                    day = parts[2]
                    ad_year = roc_year + 1911  # 民國年轉西元年
                    return f"{ad_year}-{month.zfill(2)}-{day.zfill(2)}"
                return date_str
            
            df['date'] = df['date'].apply(convert_roc_date)
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            
            # 轉換數字欄位 (更安全的數值清洗，保留原始值)
            numeric_cols = ['volume', 'open', 'high', 'low', 'close']
            for col in numeric_cols:
                if col in df.columns:  # 確保欄位存在
                    # 保留原始值用於追溯
                    df[f'{col}_raw'] = df[col].copy()
                    
                    # 清洗並轉換
                    s = df[col].astype(str)
                    s = s.str.replace(",", "", regex=False)
                    s = s.replace({"--": None, "—": None, "": None, "nan": None})
                    df[col] = pd.to_numeric(s, errors="coerce")
                else:
                    logger.debug(f"欄位 {col} 不存在，跳過處理")
            
            # 過濾無效數據
            df = df.dropna(subset=['open', 'high', 'low', 'close'])
            df = df[df['close'] > 0]
            
            if len(df) == 0:
                return None
                
            # 只保留需要的欄位並添加來源標記
            result = df[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
            result['stock_id'] = stock_id
            result['market'] = 'TWSE'
            result['source'] = 'TWSE_STOCK_DAY'
            
            return result
            
        except Exception as e:
            logger.error(f"獲取TWSE數據失敗 {stock_id} {year}/{month}: {e}")
            return None
    
    def fetch_tpex_stock_data(self, stock_id: str, year: int, month: int) -> Optional[pd.DataFrame]:
        """
        從TPEx獲取單一股票的月度歷史資料
        
        Args:
            stock_id: 股票代碼
            year: 年份 
            month: 月份
            
        Returns:
            DataFrame 或 None
        """
        logger.info(f"🚀 TPEx 使用 FinMind 穩定方案: {stock_id} {year}/{month}")
        
        # 直接使用 FinMind - TPEx 官方 API 已損壞，這是最穩定的方案
        return self.fetch_tpex_finmind_backup(stock_id, year, month)

        # 以下是原始程式碼（已停用）
        try:
            # TPEx 個股日成交資訊（已知損壞）
            url = "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php"
            
            # 轉換為民國年
            roc_year = year - 1911
            
            params = {
                'l': 'zh-tw',
                'o': 'json',
                'd': f"{roc_year}/{month:02d}",  # 民國年格式
                'stkno': stock_id
            }
            
            rate_limiter.acquire()  # 全域速率限制
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('stat') != 'OK':
                logger.warning(f"TPEx JSON API返回非OK狀態: {stock_id} {year}/{month}，嘗試CSV備援")
                # 嘗試CSV備援
                return self.fetch_tpex_stock_data_csv_fallback(stock_id, year, month)
                
            if not data.get('aaData'):
                logger.debug(f"無數據: {stock_id} {year}/{month}")
                return None
            
            # 解析數據
            rows = []
            for row in data['aaData']:
                if len(row) >= 6:
                    # TPEx格式: [日期, 開盤, 最高, 最低, 收盤, 成交量, ...]
                    date_str = f"{year}-{row[0].replace('/', '-')}"
                    rows.append({
                        'date': date_str,
                        'open': row[1],
                        'high': row[2], 
                        'low': row[3],
                        'close': row[4],
                        'volume': row[5] if len(row) > 5 else 0
                    })
            
            if not rows:
                return None
                
            df = pd.DataFrame(rows)
            
            # 數據清理
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            
            # 轉換數字欄位 (更安全的數值清洗，保留原始值)
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                # 保留原始值用於追溯
                df[f'{col}_raw'] = df[col].copy()
                
                # 清洗並轉換
                s = df[col].astype(str)
                s = s.str.replace(",", "", regex=False)
                s = s.replace({"--": None, "—": None, "": None, "nan": None})
                df[col] = pd.to_numeric(s, errors="coerce")
            
            # 過濾無效數據
            df = df.dropna(subset=['date', 'open', 'high', 'low', 'close'])
            df = df[df['close'] > 0]
            
            if len(df) == 0:
                return None
                
            df['stock_id'] = stock_id
            df['market'] = 'TPEx'
            df['source'] = 'TPEX_JSON'
            
            return df[['date', 'open', 'high', 'low', 'close', 'volume', 'stock_id', 'market', 'source']]
            
        except Exception as e:
            logger.error(f"獲取TPEx數據失敗 {stock_id} {year}/{month}: {e}")
            # 直接使用 FinMind 備援
            return self.fetch_tpex_finmind_backup(stock_id, year, month)

    def fetch_tpex_finmind_backup(self, stock_id: str, year: int, month: int) -> Optional[pd.DataFrame]:
        """TPEx FinMind 備援機制 - 穩定可靠的歷史數據"""
        try:
            logger.info(f"🚀 使用 FinMind 備援獲取 {stock_id} {year}/{month}")
            
            # FinMind API
            url = "https://api.finmindtrade.com/api/v4/data"
            
            # 計算日期範圍
            start_date = f"{year}-{month:02d}-01"
            
            # 計算月末
            if month == 12:
                next_year = year + 1
                next_month = 1
            else:
                next_year = year
                next_month = month + 1
            
            from datetime import datetime, timedelta
            last_day = datetime(next_year, next_month, 1) - timedelta(days=1)
            end_date = last_day.strftime('%Y-%m-%d')
            
            params = {
                'dataset': 'TaiwanStockPrice',
                'data_id': stock_id,
                'start_date': start_date,
                'end_date': end_date
            }
            
            logger.debug(f"FinMind 參數: {params}")
            
            rate_limiter.acquire()  # 全域速率限制
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != 200:
                logger.warning(f"FinMind API 非成功狀態: {data.get('status')} - {data.get('msg', '')}")
                return None
                
            if not data.get('data'):
                logger.warning(f"FinMind 無數據: {stock_id} {year}/{month}")
                return None
            
            finmind_data = data['data']
            logger.info(f"📊 FinMind 獲取 {len(finmind_data)} 筆數據")
            
            # 轉換為標準格式
            rows = []
            for item in finmind_data:
                try:
                    rows.append({
                        'date': item['date'],
                        'open': float(item['open']),
                        'high': float(item['max']),  # FinMind 使用 'max'
                        'low': float(item['min']),   # FinMind 使用 'min'  
                        'close': float(item['close']),
                        'volume': int(item['Trading_Volume']) if item['Trading_Volume'] else 0
                    })
                except (KeyError, ValueError, TypeError) as e:
                    logger.debug(f"FinMind 數據解析跳過: {item} - {e}")
                    continue
            
            if not rows:
                logger.warning(f"FinMind 數據解析後為空: {stock_id}")
                return None
                
            df = pd.DataFrame(rows)
            
            # 數據清理
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df.dropna(subset=['date', 'open', 'high', 'low', 'close'])
            df = df[df['close'] > 0]
            df = df.sort_values('date').reset_index(drop=True)
            
            if len(df) == 0:
                logger.warning(f"FinMind 數據清洗後為空: {stock_id}")
                return None
                
            # 添加來源標記
            result = df[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
            result['stock_id'] = stock_id
            result['market'] = 'TPEx'
            result['source'] = 'FINMIND_BACKUP'
            
            logger.info(f"✅ FinMind 成功: {stock_id} {year}/{month}, {len(result)} 筆")
            return result
            
        except Exception as e:
            logger.error(f"FinMind 備援失敗 {stock_id} {year}/{month}: {e}")
            # 最後嘗試 CSV 備援
            return self.fetch_tpex_stock_data_csv_fallback(stock_id, year, month)

    def fetch_tpex_stock_data_csv_fallback(self, stock_id: str, year: int, month: int) -> Optional[pd.DataFrame]:
        """TPEx CSV 備援機制 (民國年格式)"""
        try:
            # 轉換為民國年
            roc_year = year - 1911
            
            # TPEx CSV 下載 URL (民國年格式)
            url = "https://www.tpex.org.tw/web/stock/historical_trading/stk_quote_download.php"
            params = {
                "l": "zh-tw",
                "d": f"{roc_year}/{month:02d}",
                "stkno": stock_id,
                "download": "csv"
            }
            
            logger.info(f"嘗試 TPEx CSV 備援: {stock_id} {roc_year}/{month:02d}")
            
            rate_limiter.acquire()  # 全域速率限制
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # 檢查是否為CSV內容
            content_type = response.headers.get('content-type', '')
            if 'text/csv' not in content_type and 'application/csv' not in content_type:
                logger.warning(f"TPEx CSV 回應類型異常: {content_type}")
            
            # 解析 CSV 內容
            lines = response.text.strip().split('\n')
            if len(lines) < 2:
                logger.warning(f"TPEx CSV 無資料: {stock_id} {year}-{month:02d}")
                return None
            
            rows = []
            header = lines[0].split(',')
            
            # 更韌性的 TPEx CSV 欄位名抓取
            def _find_col(cols, keys):
                """以包含式比對找欄位名，更韌性處理微調"""
                for k in keys:
                    for c in cols:
                        if k in c:
                            return c
                return None
            
            try:
                # 使用包含式匹配找欄位名 (返回欄位名而非索引)
                date_col = _find_col(header, ['日期', '成交日期'])
                open_col = _find_col(header, ['開盤'])
                high_col = _find_col(header, ['最高'])
                low_col = _find_col(header, ['最低'])
                close_col = _find_col(header, ['收盤'])
                vol_col = _find_col(header, ['成交股數', '成交股數(千股)'])
                
                # 轉換為索引
                date_idx = header.index(date_col) if date_col else None
                open_idx = header.index(open_col) if open_col else None
                high_idx = header.index(high_col) if high_col else None
                low_idx = header.index(low_col) if low_col else None
                close_idx = header.index(close_col) if close_col else None
                volume_idx = header.index(vol_col) if vol_col else None
                        
                if None in [date_idx, open_idx, high_idx, low_idx, close_idx, volume_idx]:
                    logger.error(f"TPEx CSV 找不到必要欄位: {header}")
                    logger.error(f"匹配結果: date={date_idx}, open={open_idx}, high={high_idx}, low={low_idx}, close={close_idx}, volume={volume_idx}")
                    return None
                    
            except Exception as e:
                logger.error(f"TPEx CSV 欄位解析異常: {e}")
                return None
            
            for line in lines[1:]:
                if not line.strip():
                    continue
                    
                fields = line.split(',')
                if len(fields) != len(header):
                    continue
                
                try:
                    # 解析日期 (民國年 xxx/mm/dd 格式)
                    date_str = fields[date_idx].strip()
                    if '/' not in date_str:
                        continue
                    
                    roc_parts = date_str.split('/')
                    if len(roc_parts) != 3:
                        continue
                    
                    roc_year_str, month_str, day_str = roc_parts
                    ad_year = int(roc_year_str) + 1911
                    date_obj = datetime(ad_year, int(month_str), int(day_str))
                    
                    # 解析價格 (去除千分位逗號)
                    def parse_price(value_str):
                        cleaned = value_str.replace(',', '').replace('--', '').replace('—', '').strip()
                        return float(cleaned) if cleaned and cleaned != '0' else None
                    
                    open_price = parse_price(fields[open_idx])
                    high_price = parse_price(fields[high_idx])
                    low_price = parse_price(fields[low_idx])
                    close_price = parse_price(fields[close_idx])
                    
                    # 成交量 (千股轉為股)
                    volume_str = fields[volume_idx].replace(',', '').strip()
                    volume = int(float(volume_str) * 1000) if volume_str and volume_str not in ['--', '—'] else 0
                    
                    # 基本資料驗證
                    if not all([open_price, high_price, low_price, close_price]):
                        continue
                    if high_price < max(open_price, close_price):
                        continue
                    if low_price > min(open_price, close_price):
                        continue
                    
                    rows.append({
                        'date': date_obj,
                        'open': open_price,
                        'high': high_price,
                        'low': low_price,
                        'close': close_price,
                        'volume': volume
                    })
                    
                except (ValueError, IndexError) as e:
                    logger.debug(f"TPEx CSV 解析失敗行: {line[:50]}, error: {e}")
                    continue
            
            if not rows:
                logger.warning(f"TPEx CSV 備援無有效資料: {stock_id} {year}-{month:02d}")
                return None
                
            df = pd.DataFrame(rows)
            df['stock_id'] = stock_id
            df['market'] = 'TPEx'
            df['source'] = 'TPEX_CSV_BACKUP'
            
            logger.info(f"TPEx CSV 備援成功: {stock_id} {year}-{month:02d}, 取得 {len(rows)} 筆")
            return df[['date', 'open', 'high', 'low', 'close', 'volume', 'stock_id', 'market', 'source']]
            
        except Exception as e:
            logger.error(f"TPEx CSV 備援失敗 {stock_id} {year}-{month:02d}: {e}")
            return None
    
    def create_price_tables(self):
        """建立價格數據表結構和索引優化"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 確保 daily_prices 表存在
            ensure_daily_prices_table(conn)
            
            # C級優化: 建立索引
            ensure_optimized_indexes(conn)
            
            # 檢查已存在的價格表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'stock_%'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"現有價格表數量: {len(existing_tables)}")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"檢查價格表失敗: {e}")
    
    def save_stock_price_data(self, stock_id: str, market: str, source: str, df: pd.DataFrame):
        """保存股票價格資料到單一事實表 (服務級架構)"""
        conn = None
        try:
            # 校驗股票代碼
            stock_id = sanitize_stock_id(stock_id)
            
            conn = sqlite3.connect(self.db_path)
            # 優化SQLite效能
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            
            # 確保單表架構存在
            ensure_daily_prices_table(conn)
            
            # 批次插入數據 - 使用 per-row 精準來源追溯 (必補項目2)
            rows = []
            for r in df.itertuples(index=False):
                try:
                    # 確保所有數值都是有效的
                    if pd.notna(r.open) and pd.notna(r.high) and pd.notna(r.low) and pd.notna(r.close) and pd.notna(r.volume):
                        # 優先使用 df 內的 market/source，回退到參數傳入值
                        row_market = getattr(r, 'market', market)
                        row_source = getattr(r, 'source', source)
                        
                        # 處理日期格式：支援字符串和datetime兩種
                        date_str = r.date if isinstance(r.date, str) else r.date.strftime("%Y-%m-%d")
                        
                        rows.append((
                            stock_id,
                            date_str, 
                            float(r.open), 
                            float(r.high),
                            float(r.low), 
                            float(r.close), 
                            int(r.volume),
                            row_market,
                            row_source
                        ))
                except (ValueError, AttributeError, OverflowError) as e:
                    logger.warning(f"跳過無效記錄 {stock_id} {r.date}: {e}")
                    continue
            
            if rows:
                # 寫入效能微調 (應加項目7)
                # 批次寫入以降低 I/O 頻率
                batch_size = 1000
                for i in range(0, len(rows), batch_size):
                    batch = rows[i:i + batch_size]
                    conn.executemany("""
                        INSERT OR REPLACE INTO daily_prices
                        (stock_id, date, open, high, low, close, volume, market, source)
                        VALUES (?,?,?,?,?,?,?,?,?)
                    """, batch)
                    
                    # 每批次後短暫休息，避免 I/O 峰值
                    if i + batch_size < len(rows):
                        time.sleep(0.01)
                
                conn.commit()
                logger.debug(f"保存 {stock_id}: {len(rows)} 筆記錄到單表")
            else:
                logger.warning(f"股票 {stock_id} 無有效記錄可保存")
            
        except Exception as e:
            logger.error(f"保存 {stock_id} 價格數據失敗: {e}")
        finally:
            if conn:
                conn.close()
    
    def fetch_market_daily_data(self, date: str) -> Optional[pd.DataFrame]:
        """
        取得TWSE全市場特定日期的股價資料 (B級優化)
        
        Args:
            date: 日期格式 YYYYMMDD (e.g., '20250909')
            
        Returns:
            DataFrame: 包含全市場股票的OHLCV資料
        """
        url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL"
        params = {
            'response': 'json',
            'date': date
        }
        
        try:
            rate_limiter.acquire()  # 全域速率限制
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # 檢查API狀態和資料
            if data.get('stat') != 'OK':
                logger.warning(f"TWSE全市場日彙總API狀態異常: {data.get('stat')} - {date}")
                return None
                
            if 'data' not in data or not data['data']:
                logger.warning(f"TWSE全市場日彙總無資料: {date}")
                return None
            
            rows = []
            for row in data['data']:
                try:
                    # STOCK_DAY_ALL API的欄位格式 (根據fields順序)：
                    # [0]證券代號, [1]證券名稱, [2]成交股數, [3]成交金額
                    # [4]開盤價, [5]最高價, [6]最低價, [7]收盤價
                    # [8]漲跌價差, [9]成交筆數
                    
                    if len(row) < 10:
                        continue
                        
                    stock_code = str(row[0]).strip()
                    
                    # 過濾非4位數股票代號
                    if not re.match(r'^\d{4}$', stock_code):
                        continue
                    
                    # 解析價格欄位
                    def parse_price_safe(price_str):
                        if not price_str or price_str in ['--', 'X', '', '除權']:
                            return None
                        try:
                            # 移除逗號和特殊字元
                            clean_str = str(price_str).replace(',', '').replace('X', '').replace('+', '').replace('-', '').strip()
                            return float(clean_str) if clean_str else None
                        except (ValueError, AttributeError):
                            return None
                    
                    open_price = parse_price_safe(row[4])   # 開盤價
                    high_price = parse_price_safe(row[5])   # 最高價
                    low_price = parse_price_safe(row[6])    # 最低價
                    close_price = parse_price_safe(row[7])  # 收盤價
                    
                    # 解析成交量 (已經是股數，不需要×1000)
                    volume_str = str(row[2]).replace(',', '').strip()
                    try:
                        volume = int(float(volume_str)) if volume_str and volume_str not in ['--', ''] else 0
                    except (ValueError, AttributeError):
                        volume = 0
                    
                    # 資料驗證
                    if not all([open_price, high_price, low_price, close_price]):
                        continue
                    if high_price < max(open_price, close_price, low_price):
                        continue
                    if low_price > min(open_price, close_price, high_price):
                        continue
                    
                    # 轉換日期格式 YYYYMMDD -> YYYY-MM-DD
                    date_formatted = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
                    
                    rows.append({
                        'stock_id': stock_code,
                        'date': date_formatted,
                        'open': open_price,
                        'high': high_price,
                        'low': low_price,
                        'close': close_price,
                        'volume': volume,
                        'market': 'TWSE',
                        'source': 'TWSE_DAILY_ALL'
                    })
                    
                except (ValueError, IndexError, TypeError) as e:
                    logger.debug(f"TWSE全市場日彙總解析失敗行: {row[:3] if len(row) > 2 else row}, error: {e}")
                    continue
            
            if not rows:
                logger.warning(f"TWSE全市場日彙總無有效資料: {date}")
                return None
            
            df = pd.DataFrame(rows)
            logger.info(f"✅ TWSE全市場日彙總 {date}: {len(df)} 檔股票")
            return df
            
        except requests.exceptions.RequestException as e:
            logger.error(f"TWSE全市場日彙總網路錯誤 {date}: {e}")
            return None
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"TWSE全市場日彙總解析錯誤 {date}: {e}")
            return None
    
    def get_recent_trading_dates(self, days: int = 60) -> List[str]:
        """
        獲取最近N個交易日(排除假日) - B級優化輔助函數
        
        Args:
            days: 需要的交易日數量
            
        Returns:
            List[str]: 交易日清單，格式YYYYMMDD
        """
        from datetime import datetime, timedelta
        
        trading_dates = []
        current_date = datetime.now()
        days_checked = 0
        max_checks = days * 2  # 防止無限迴圈
        
        while len(trading_dates) < days and days_checked < max_checks:
            # 跳過週末
            if current_date.weekday() < 5:  # 0-6, 週一到週五
                date_str = current_date.strftime('%Y%m%d')
                trading_dates.append(date_str)
            
            current_date -= timedelta(days=1)
            days_checked += 1
        
        return trading_dates[:days]  # 最新的在前
    
    def fetch_market_recent_data_batch(self, target_bars: int = 60) -> Dict[str, pd.DataFrame]:
        """
        B級優化：批次抽取近期全市場資料
        取代逐檔逐月的傳統方式，用日彙總API一次取得多檔股票
        
        Args:
            target_bars: 目標K線根數
            
        Returns:
            Dict[str, pd.DataFrame]: {stock_id: DataFrame}
        """
        logger.info(f"🚀 B級優化：開始全市場批次抽取 {target_bars} 個交易日資料")
        
        # 1. 獲取交易日清單
        trading_dates = self.get_recent_trading_dates(target_bars + 10)  # 多取10天保险
        logger.info(f"📅 將抽取 {len(trading_dates)} 個交易日: {trading_dates[:5]}...{trading_dates[-3:]}")
        
        # 2. 逐日抽取全市場資料
        all_stock_data = {}
        successful_dates = 0
        
        for i, date in enumerate(trading_dates):
            logger.info(f"📏 抽取 {i+1}/{len(trading_dates)}: {date}")
            
            daily_data = self.fetch_market_daily_data(date)
            if daily_data is not None and len(daily_data) > 0:
                successful_dates += 1
                
                # 將資料按stock_id分組
                for _, row in daily_data.iterrows():
                    stock_id = row['stock_id']
                    if stock_id not in all_stock_data:
                        all_stock_data[stock_id] = []
                    all_stock_data[stock_id].append(row.to_dict())
            else:
                logger.warning(f"⚠️ {date} 無資料或抽取失敗")
        
        # 3. 轉換DataFrame並篩選
        final_stock_data = {}
        for stock_id, records in all_stock_data.items():
            if len(records) >= target_bars:  # 確保有足夠的K線
                df = pd.DataFrame(records)
                df = df.sort_values('date').tail(target_bars)  # 取最近target_bars筆
                final_stock_data[stock_id] = df
        
        logger.info(f"✅ B級優化完成：成功抽取 {successful_dates}/{len(trading_dates)} 個交易日，得到 {len(final_stock_data)} 檔股票")
        return final_stock_data
    
    def fetch_stock_historical_data(self, stock_id: str, market: str, target_bars: int = 60) -> bool:
        """
        獲取股票歷史資料 (精確控制K線根數) - 修正版
        
        Args:
            stock_id: 股票代碼
            market: 市場 (TWSE/TPEx)
            target_bars: 目標K線根數 (預設60根)
            
        Returns:
            成功與否
        """
        all_data = []
        
        try:
            current_date = datetime.now()
            # 動態計算需要月數：一個月約18交易日
            need_months = max(3, math.ceil(target_bars / 18) + 1)
            months_tried = 0
            total_records = 0
            
            # 第一輪：按預估月數抓取
            while total_records < target_bars and months_tried < need_months:
                year = current_date.year
                month = current_date.month
                months_tried += 1
                
                logger.debug(f"獲取 {stock_id} {year}/{month} (目標: {target_bars}根, 已獲取: {len(all_data)}根)")
                
                # 根據市場選擇API
                if market == 'TWSE':
                    df = self.fetch_twse_stock_data(stock_id, year, month)
                else:  # TPEx
                    df = self.fetch_tpex_stock_data(stock_id, year, month)
                
                if df is not None and len(df) > 0:
                    all_data.append(df)
                    total_records += len(df)
                    logger.info(f"✅ {stock_id} {year}/{month}: {len(df)} 筆 (累計: {total_records})")
                else:
                    logger.warning(f"❌ {stock_id} {year}/{month}: 無數據")
                
                # 關鍵修正：往前移動一個月
                current_date = current_date - relativedelta(months=1)
                
                # 已有全域速率限制，移除固定延遲
            
            # 第二輪：如果還不夠，再最多抓6個月作為保險
            max_extra_months = 6
            while total_records < target_bars and months_tried < need_months + max_extra_months:
                year = current_date.year
                month = current_date.month
                months_tried += 1
                
                logger.debug(f"保險輪: 獲取 {stock_id} {year}/{month}")
                
                if market == 'TWSE':
                    df = self.fetch_twse_stock_data(stock_id, year, month)
                else:
                    df = self.fetch_tpex_stock_data(stock_id, year, month)
                
                if df is not None and len(df) > 0:
                    all_data.append(df)
                    total_records += len(df)
                    logger.info(f"✅ {stock_id} {year}/{month}: {len(df)} 筆 (保險輪累計: {total_records})")
                
                current_date = current_date - relativedelta(months=1)
                time.sleep(0.5)
            
            if not all_data:
                logger.warning(f"❌ 股票 {stock_id} 無法獲取任何數據")
                return False
            
            # 合併所有DataFrame
            df_all = pd.concat(all_data, ignore_index=True)
            df_all['date'] = pd.to_datetime(df_all['date'])
            
            # 去重與排序
            df_all = df_all.dropna(subset=['date', 'open', 'high', 'low', 'close'])
            
            # 避免未來日誤入庫 - 台北時區一致化 (必補項目1)
            today = pd.Timestamp.now(tz=TAIPEI).normalize().tz_localize(None)
            future_dates = df_all[df_all['date'] > today]
            if len(future_dates) > 0:
                logger.warning(f"⚠️ {stock_id} 發現 {len(future_dates)} 筆未來日期，已過濾: {future_dates['date'].tolist()}")
                df_all = df_all[df_all['date'] <= today]
            
            df_all = df_all.drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
            
            # 異常量價保守處理 (應加項目4)
            df_all = df_all.dropna(subset=['open', 'high', 'low', 'close'])
            df_all = df_all[df_all['close'] > 0]
            # 若不想把停牌日寫入，取消下行注釋：
            # df_all = df_all[df_all['volume'].fillna(0) > 0]
            
            # 抓不滿的明確告警 (應加項目5)
            if len(df_all) < target_bars:
                logger.warning(f"⚠️ {stock_id} 僅 {len(df_all)}/{target_bars} 根（months_tried={months_tried}）")
            
            if len(df_all) > target_bars:
                df_all = df_all.tail(target_bars).reset_index(drop=True)
            
            # 保存到資料庫 (單表架構)
            source = f"{market}_API"
            self.save_stock_price_data(stock_id, market, source, df_all)
            
            # 修正日志格式
            start = df_all.iloc[0]['date'].strftime('%Y-%m-%d')
            end = df_all.iloc[-1]['date'].strftime('%Y-%m-%d')
            logger.info(f"✅ 股票 {stock_id} 完成: 共 {len(df_all)} 筆 ({start} ~ {end})")
            return True
        
        except Exception as e:
            logger.error(f"獲取 {stock_id} 歷史資料失敗: {e}")
            return False
    
    def optimize_db_for_bulk_insert(self, conn):
        """
        C級優化：設置SQL的PRAGMA進行大量匯入優化
        """
        logger.info("🛠️ C級優化: 設定高性能PRAGMA")
        
        # 高性能寫入模式
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")  # 從 FULL 降至 NORMAL
        conn.execute("PRAGMA temp_store=MEMORY")    # 暫存記憶體
        conn.execute("PRAGMA cache_size=-200000")   # 200MB cache
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory mapping
        
        logger.info("✅ PRAGMA設定完成：已優化資料庫寫入性能")
    
    def restore_db_settings(self, conn):
        """
        C級優化：還原正常的PRAGMA設定
        """
        logger.info("🔄 還原正常資料庫設定...")
        
        conn.execute("PRAGMA synchronous=FULL")   # 還原為最安全模式
        conn.execute("PRAGMA cache_size=2000")     # 還原預設值
        conn.execute("PRAGMA mmap_size=0")         # 關閉memory mapping
        
        logger.info("✅ 資料庫設定已還原")
    
    def batch_insert_stock_data(self, all_stock_data: Dict[str, pd.DataFrame]):
        """
        C級優化：批次寫入股票資料，使用大transaction
        
        Args:
            all_stock_data: {stock_id: DataFrame} 的資料
        
        Returns:
            Tuple[int, int]: (success_count, failed_count)
        """
        logger.info(f"📦 C級優化: 批次寫入 {len(all_stock_data)} 檔股票資料")
        
        conn = None
        success = 0
        failed = 0
        
        try:
            # 連線資料庫並優化
            conn = sqlite3.connect(self.db_path)
            self.optimize_db_for_bulk_insert(conn)
            
            # 開始大transaction
            conn.execute("BEGIN TRANSACTION")
            logger.info("🚀 開始大transaction批次寫入...")
            
            # 準備批次插入語句
            insert_sql = """
                INSERT OR REPLACE INTO daily_prices 
                (stock_id, date, open, high, low, close, volume, market, source, ingested_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """
            
            # 收集所有資料為一個大批次
            all_rows = []
            
            for stock_id, df in all_stock_data.items():
                try:
                    # 檢查是否需要更新 (D級優化的簡化版)
                    if self.is_fresh_enough(stock_id, len(df)):
                        logger.debug(f"↪️ 跳過 {stock_id}（資料夠新）")
                        success += 1
                        continue
                    
                    # 準備該股票的所有資料
                    for _, row in df.iterrows():
                        # 處理日期格式
                        date_str = row['date'] if isinstance(row['date'], str) else row['date'].strftime('%Y-%m-%d')
                        
                        all_rows.append((
                            stock_id,
                            date_str,
                            float(row['open']),
                            float(row['high']),
                            float(row['low']),
                            float(row['close']),
                            int(row['volume']),
                            row['market'],
                            row['source']
                        ))
                    
                    success += 1
                    
                except Exception as e:
                    logger.error(f"❌ 準備 {stock_id} 資料失敗: {e}")
                    failed += 1
                    continue
            
            # 一次性批次插入所有資料
            if all_rows:
                logger.info(f"📥 執行批次插入: {len(all_rows)} 筆記錄")
                conn.executemany(insert_sql, all_rows)
                logger.info(f"✅ 批次插入完成")
            
            # 提交大transaction
            conn.commit()
            logger.info(f"🎉 大transaction提交成功: {len(all_rows)} 筆記錄")
            
        except Exception as e:
            logger.error(f"❌ 批次寫入失敗: {e}")
            if conn:
                conn.rollback()
                logger.info("🔄 已回滾交易")
            # 全部記為失敗
            failed = len(all_stock_data)
            success = 0
        
        finally:
            if conn:
                # 還原資料庫設定
                self.restore_db_settings(conn)
                conn.close()
        
        return success, failed
    
    def run_price_data_pipeline_optimized(self, max_stocks: Optional[int] = None, target_bars: int = 60, specific_stocks: Optional[List[str]] = None):
        """
        執行價格數據管道 - B級優化版 (日彙總批次抽取)
        取代逐檔逐月的傳統方式，速度提升 5-10 倍
        
        Args:
            max_stocks: 最大處理股票數 (None = 全部)
            target_bars: 目標K線根數 (預設60根)
            specific_stocks: 指定股票清單 (None = 使用預設清單)
        """
        logger.info("🚀 執行 B級優化版價格數據管道...")
        start_time = datetime.now()
        
        # 建立表結構
        self.create_price_tables()
        
        # 1. 使用全市場批次抽取 (B級優化核心)
        logger.info("🎆 B級優化: 使用全市場日彙總API批次拽取")
        market_data = self.fetch_market_recent_data_batch(target_bars)
        
        if not market_data:
            logger.error("❌ B級優化失敗: 無法獲取市場資料")
            return 0, 0
        
        # 2. 過濾股票 (如果指定)
        if specific_stocks:
            filtered_data = {k: v for k, v in market_data.items() if k in specific_stocks}
            logger.info(f"🎯 指定股票過濾: {len(filtered_data)}/{len(market_data)} 檔")
            market_data = filtered_data
        
        if max_stocks:
            # 取前 max_stocks 檔
            market_data = dict(list(market_data.items())[:max_stocks])
            logger.info(f"🎯 數量限制: 前 {max_stocks} 檔")
        
        # 3. 使用C級優化批次寫入資料庫
        logger.info("🎆 C級優化: 使用大transaction批次寫入")
        success, failed = self.batch_insert_stock_data(market_data)
        
        # 結果統計
        total_time = (datetime.now() - start_time).seconds
        logger.info(f"🎉 B級優化版完成!")
        logger.info(f"📏 處理結果: 總計{len(market_data)}檔, 成功{success}檔, 失敗{failed}檔")
        logger.info(f"⏱️  總耗時: {total_time/60:.1f}分鐘 (平均 {total_time/len(market_data):.1f}秒/檔)")
        
        # 顯示資料庫統計
        self.validate_price_data()
        
        return success, failed
    
    def run_price_data_pipeline(self, max_stocks: Optional[int] = None, target_bars: int = 60, specific_stocks: Optional[List[str]] = None):
        """
        執行價格數據管道
        
        Args:
            max_stocks: 最大處理股票數 (None = 全部)
            target_bars: 目標K線根數 (預設60根)
            specific_stocks: 指定股票清單 (None = 使用預設清單)
        """
        logger.info("🚀 開始執行價格數據管道...")
        
        # 獲取股票清單
        if specific_stocks:
            # 將字符串列表轉換為(stock_id, name, market)格式
            stocks = []
            for stock_id in specific_stocks:
                # 簡單推測市場：4位數字且<=3000通常是TWSE，否則是TPEx
                market = 'twse' if stock_id.isdigit() and int(stock_id) <= 3000 else 'tpex'
                stocks.append((stock_id, stock_id, market))  # 暫時用stock_id當作name
            logger.info(f"📊 使用指定股票清單: {len(stocks)} 檔")
        else:
            stocks = self.get_stock_list()
            if not stocks:
                logger.error("❌ 無法獲取股票清單")
                return
        
        if max_stocks and not specific_stocks:
            stocks = stocks[:max_stocks]
            logger.info(f"📊 限制處理前 {max_stocks} 檔股票")
        
        logger.info(f"📊 總計 {len(stocks)} 檔股票需要處理")
        
        # 建立表結構
        self.create_price_tables()
        
        # 處理統計
        processed = 0
        success = 0
        failed = 0
        
        start_time = datetime.now()
        
        for stock_id, name, market in stocks:
            logger.info(f"處理 {processed+1}/{len(stocks)}: {stock_id} ({name}) - {market}")
            
            # 跳過已足夠新鮮的股票（減少重抓）
            if self.is_fresh_enough(stock_id, target_bars):
                logger.info(f"↪︎ 跳過 {stock_id}（資料夠新）")
                success += 1
                processed += 1
                continue
            
            if self.fetch_stock_historical_data(stock_id, market, target_bars):
                success += 1
            else:
                failed += 1
                
            processed += 1
            
            # 已有全域速率限制，移除固定延遲
            
            # 每10檔報告進度並長時間休息
            if processed % 10 == 0:
                elapsed = (datetime.now() - start_time).seconds
                eta = (elapsed / processed) * (len(stocks) - processed)
                logger.info(f"📈 進度: {processed}/{len(stocks)} (成功:{success}, 失敗:{failed}), 預估剩餘: {eta/60:.1f}分鐘")
                # 已有全域速率限制，移除固定延遲
        
        # 完成報告
        total_time = (datetime.now() - start_time).seconds
        logger.info(f"🎉 價格數據管道完成!")
        logger.info(f"📊 處理結果: 總計{processed}檔, 成功{success}檔, 失敗{failed}檔")
        logger.info(f"⏱️  總耗時: {total_time/60:.1f}分鐘")
        
        # 驗證結果
        self.validate_price_data()
        
        return success, failed
    
    def validate_price_data(self):
        """驗證價格數據完整性（單表版）"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 檢查總體數據
            cursor.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM daily_prices")
            total, min_date, max_date = cursor.fetchone() or (0, None, None)
            logger.info(f"✅ daily_prices 總筆數: {total}（{min_date} ~ {max_date}）")

            # 市場合計
            for mkt in ("TWSE", "TPEx"):
                cursor.execute("""
                    SELECT COUNT(*), MIN(date), MAX(date)
                    FROM daily_prices WHERE market = ?
                """, (mkt,))
                c, dmin, dmax = cursor.fetchone() or (0, None, None)
                logger.info(f"📊 {mkt}: {c} 筆（{dmin} ~ {dmax}）")

            # 抽樣 5 檔檢查連續性
            cursor.execute("""
                SELECT stock_id, COUNT(*) as c FROM daily_prices
                GROUP BY stock_id ORDER BY c DESC LIMIT 5
            """)
            for sid, c in cursor.fetchall():
                cursor.execute("""
                    SELECT MIN(date), MAX(date) FROM daily_prices WHERE stock_id=?
                """, (sid,))
                dmin, dmax = cursor.fetchone()
                logger.info(f"🔍 {sid}: {c} 筆（{dmin} ~ {dmax}）")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"驗證價格數據失敗: {e}")
    
    def update_existing_stocks(self, stock_list: List[str]):
        """
        更新現有股票到最新日期
        
        Args:
            stock_list: 需要更新的股票清單
        """
        logger.info(f"🔄 更新 {len(stock_list)} 檔現有股票到最新日期...")
        
        conn = sqlite3.connect(self.db_path)
        
        updated = 0
        failed = 0
        
        for i, stock_id in enumerate(stock_list):
            if i % 20 == 0:
                logger.info(f"更新進度: {i}/{len(stock_list)} ({i/len(stock_list)*100:.1f}%)")
            
            try:
                # 檢查該股票的最新日期
                latest_query = """
                SELECT MAX(date) as latest_date, COUNT(*) as total_bars
                FROM daily_prices 
                WHERE stock_id = ?
                """
                result = pd.read_sql_query(latest_query, conn, params=(stock_id,))
                
                if result.empty or result['latest_date'].iloc[0] is None:
                    logger.debug(f"{stock_id}: 無現有資料，跳過更新")
                    continue
                
                latest_date = result['latest_date'].iloc[0]
                
                # 如果資料已經是最新的，跳過
                today = datetime.now().strftime('%Y-%m-%d')
                if latest_date >= today:
                    continue
                
                # 嘗試獲取最新2-3天的數據
                success = False
                for market in ['twse', 'tpex']:
                    try:
                        # 使用現有API獲取最新幾天的數據
                        recent_data = self.get_recent_trading_data(stock_id, market, days=5)
                        if recent_data:
                            self.store_daily_prices(stock_id, recent_data, market, 'recent_update')
                            success = True
                            break
                    except:
                        continue
                
                if success:
                    updated += 1
                else:
                    failed += 1
                
                # 控制請求頻率
                time.sleep(0.2)
                
            except Exception as e:
                failed += 1
                logger.error(f"{stock_id}: 更新錯誤 - {e}")
        
        conn.close()
        logger.info(f"📊 更新完成！成功: {updated}, 失敗: {failed}")
        return updated, failed
    
    def get_recent_trading_data(self, stock_id: str, market: str, days: int = 5):
        """獲取最近幾天的交易數據"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            return self.fetch_stock_data_twse_api(
                stock_id, market, 
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
        except Exception as e:
            logger.debug(f"獲取 {stock_id} 最新數據失敗: {e}")
            return None

def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description="台股歷史價格數據獲取")
    parser.add_argument("--max-stocks", type=int, help="最大處理股票數量 (測試用)")
    parser.add_argument("--bars", type=int, default=60, help="目標K線根數 (預設60根)")
    parser.add_argument("--db-path", default="data/cleaned/taiwan_stocks_cleaned.db", help="資料庫路徑")
    
    args = parser.parse_args()
    
    pipeline = TaiwanStockPriceDataPipeline(args.db_path)
    pipeline.run_price_data_pipeline(args.max_stocks, args.bars)

if __name__ == "__main__":
    main()