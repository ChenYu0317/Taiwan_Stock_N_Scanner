#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Taiwan Stock Data Pipeline — Fixed Version (針對實際HTML結構優化)

修正重點:
1. 正確處理MS950編碼
2. 適配實際的HTML表格結構
3. 強化錯誤處理和日誌
"""

from __future__ import annotations
import argparse
import io
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import requests
from dateutil import tz

# ----------------------------- Logging ---------------------------------
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("tw-pipeline")

# ----------------------------- Helpers ---------------------------------
TAIPEI_TZ = tz.gettz("Asia/Taipei")

def today_taipei() -> datetime:
    return datetime.now(TAIPEI_TZ)

def to_yyyymmdd(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")

def http_get(url: str, params: Optional[dict] = None, timeout: int = 25) -> requests.Response:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    r = requests.get(url, params=params, timeout=timeout, headers=headers)
    r.raise_for_status()
    return r

# --------------------------- Database ----------------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS stock_universe (
    stock_id TEXT PRIMARY KEY,
    name TEXT,
    isin TEXT,
    market TEXT,           -- TWSE / TPEx
    listed_date DATE,
    status TEXT DEFAULT 'active',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS validation_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    universe_twse_count INTEGER,
    universe_tpex_count INTEGER,
    total_count INTEGER,
    details_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

def open_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.Connection(db_path)
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()

# --------------------------- ISIN Universe -----------------------------
ISIN_TWSE = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
ISIN_TPEX = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"

def parse_isin_html_to_df(content: bytes, market: str) -> pd.DataFrame:
    """解析 ISIN HTML 表格，適配實際結構"""
    logger.info(f"解析 {market} ISIN HTML，內容長度: {len(content)}")
    
    # 使用pandas讀取HTML表格
    tables = pd.read_html(io.BytesIO(content), encoding='ms950')
    if not tables:
        raise ValueError("HTML中沒有找到表格")
    
    df = tables[0].copy()
    logger.info(f"原始表格形狀: {df.shape}")
    logger.info(f"原始欄位: {list(df.columns)}")
    
    # 檢查實際表格結構
    if df.shape[1] < 3:
        raise ValueError(f"表格欄位不足: {df.shape[1]}")
    
    # 根據實際結構適配欄位
    # 第0欄: 有價證券代號及名稱
    # 第1欄: 國際證券辨識號碼(ISIN Code)  
    # 第2欄: 上市日
    # 第3欄: 市場別
    # 第4欄: 產業別
    
    # 重命名欄位為簡單的索引
    new_columns = [f"col_{i}" for i in range(len(df.columns))]
    df.columns = new_columns
    
    # 移除標題行（通常前2行是標題）
    df = df.iloc[2:].reset_index(drop=True)
    
    # 解析第一欄的代號和名稱
    code_name_col = df['col_0'].astype(str)
    
    # 提取4位數代號
    df['stock_id'] = code_name_col.str.extract(r'(\d{4})', expand=False)
    
    # 提取名稱（代號後面的部分）
    df['name'] = code_name_col.str.replace(r'\d{4}\s*', '', regex=True).str.strip()
    
    # 過濾：只保留4位數代號的記錄
    df = df[df['stock_id'].notna()]
    df = df[df['stock_id'].str.len() == 4]
    
    # ISIN Code
    df['isin'] = df['col_1'].astype(str).str.strip()
    
    # 設置市場
    df['market'] = market
    
    # 上市日期
    if 'col_2' in df.columns:
        df['listed_date'] = pd.to_datetime(df['col_2'], errors='coerce')
    else:
        df['listed_date'] = pd.NaT
    
    # 進一步過濾：排除明顯的非股票
    # 根據名稱排除ETF、權證等
    exclude_keywords = ['ETF', 'ETN', '權證', '受益憑證', '基金', '債']
    for keyword in exclude_keywords:
        df = df[~df['name'].str.contains(keyword, na=False)]
    
    # 排除代號開頭為0的（權證）
    df = df[~df['stock_id'].str.startswith('0')]
    
    result_df = df[['stock_id', 'name', 'isin', 'market', 'listed_date']].copy()
    result_df = result_df.drop_duplicates(subset=['stock_id'])
    
    logger.info(f"{market} 解析結果: {len(result_df)} 檔股票")
    return result_df

def fetch_isin_df(url: str, market: str) -> pd.DataFrame:
    """獲取ISIN數據"""
    logger.info(f"獲取 {market} ISIN 數據: {url}")
    
    try:
        response = http_get(url, timeout=30)
        df = parse_isin_html_to_df(response.content, market)
        
        logger.info(f"{market} 成功獲取 {len(df)} 檔股票")
        
        # 顯示前幾筆範例
        if not df.empty:
            logger.info(f"{market} 前3筆範例:")
            for _, row in df.head(3).iterrows():
                logger.info(f"  {row['stock_id']}: {row['name']}")
        
        return df
        
    except Exception as e:
        logger.error(f"{market} ISIN獲取失敗: {e}")
        return pd.DataFrame(columns=['stock_id', 'name', 'isin', 'market', 'listed_date'])

def build_universe() -> pd.DataFrame:
    """建立股票宇宙"""
    logger.info("開始建立股票宇宙...")
    
    # 獲取上市股票
    twse_df = fetch_isin_df(ISIN_TWSE, "TWSE")
    
    # 獲取上櫃股票
    tpex_df = fetch_isin_df(ISIN_TPEX, "TPEx")
    
    # 合併
    if not twse_df.empty and not tpex_df.empty:
        universe = pd.concat([twse_df, tpex_df], ignore_index=True)
    elif not twse_df.empty:
        universe = twse_df
    elif not tpex_df.empty:
        universe = tpex_df
    else:
        logger.error("無法獲取任何股票數據！")
        return pd.DataFrame()
    
    # 去重
    universe = universe.drop_duplicates(subset=['stock_id'])
    
    twse_count = len(universe[universe['market'] == 'TWSE'])
    tpex_count = len(universe[universe['market'] == 'TPEx'])
    
    logger.info(f"股票宇宙建立完成: TWSE={twse_count}, TPEx={tpex_count}, 總計={len(universe)}")
    
    return universe

def upsert_universe(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    """更新股票宇宙到資料庫"""
    logger.info("更新股票宇宙到資料庫...")
    
    cur = conn.cursor()
    cur.execute("DELETE FROM stock_universe")  # 清空重建
    
    rows = []
    for _, row in df.iterrows():
        listed_date = None
        if pd.notna(row['listed_date']):
            listed_date = row['listed_date'].strftime('%Y-%m-%d')
        
        rows.append((
            row['stock_id'],
            row['name'],
            row['isin'],
            row['market'],
            listed_date,
            'active'
        ))
    
    cur.executemany(
        "INSERT INTO stock_universe (stock_id,name,isin,market,listed_date,status) VALUES (?,?,?,?,?,?)",
        rows
    )
    
    conn.commit()
    logger.info(f"股票宇宙已更新: {len(rows)} 筆記錄")

# --------------------------- CLI Actions --------------------------------

def action_update_universe(conn: sqlite3.Connection, save_csv: bool = False, out_dir: str = ".") -> pd.DataFrame:
    """更新股票宇宙"""
    universe = build_universe()
    
    if not universe.empty:
        upsert_universe(conn, universe)
        
        if save_csv:
            filename = os.path.join(out_dir, f"universe_{today_taipei().strftime('%Y%m%d')}.csv")
            universe.to_csv(filename, index=False, encoding='utf-8-sig')
            logger.info(f"股票宇宙CSV已保存: {filename}")
    
    return universe

def action_generate_report(conn: sqlite3.Connection, save_json: bool = False, out_dir: str = ".") -> Dict:
    """生成驗證報告"""
    logger.info("生成股票宇宙報告...")
    
    # 從資料庫讀取統計
    cur = conn.cursor()
    
    total_count = cur.execute("SELECT COUNT(*) FROM stock_universe").fetchone()[0]
    twse_count = cur.execute("SELECT COUNT(*) FROM stock_universe WHERE market='TWSE'").fetchone()[0]
    tpex_count = cur.execute("SELECT COUNT(*) FROM stock_universe WHERE market='TPEx'").fetchone()[0]
    
    # 取樣本數據
    samples = cur.execute("""
        SELECT stock_id, name, market FROM stock_universe 
        ORDER BY market, stock_id LIMIT 10
    """).fetchall()
    
    report = {
        "date": today_taipei().strftime('%Y%m%d'),
        "total_stocks": total_count,
        "twse_stocks": twse_count,
        "tpex_stocks": tpex_count,
        "sample_stocks": [{"stock_id": row[0], "name": row[1], "market": row[2]} for row in samples],
        "data_quality": {
            "expected_twse_range": "900-1200",
            "expected_tpex_range": "700-1000", 
            "twse_status": "正常" if 900 <= twse_count <= 1200 else "異常",
            "tpex_status": "正常" if 700 <= tpex_count <= 1000 else "異常"
        }
    }
    
    # 保存到資料庫
    cur.execute("""
        INSERT INTO validation_report 
        (date, universe_twse_count, universe_tpex_count, total_count, details_json)
        VALUES (?,?,?,?,?)
    """, (
        report["date"], twse_count, tpex_count, total_count,
        json.dumps(report, ensure_ascii=False)
    ))
    conn.commit()
    
    if save_json:
        filename = os.path.join(out_dir, f"universe_report_{report['date']}.json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"報告已保存: {filename}")
    
    logger.info(f"報告生成完成: TWSE={twse_count}, TPEx={tpex_count}, 總計={total_count}")
    return report

# ----------------------------- Main -------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Taiwan Stock Data Pipeline (Fixed Version)")
    parser.add_argument("--db", default="taiwan_stocks_fixed.db", help="SQLite路徑")
    parser.add_argument("--update-universe", action="store_true", help="更新股票宇宙")
    parser.add_argument("--generate-report", action="store_true", help="生成驗證報告")
    parser.add_argument("--save-csv", action="store_true", help="保存CSV檔案")
    parser.add_argument("--save-json", action="store_true", help="保存JSON報告")
    parser.add_argument("--out-dir", default=".", help="輸出目錄")
    parser.add_argument("--verbose", action="store_true", help="詳細日誌")
    args = parser.parse_args(argv)

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    conn = open_db(args.db)
    try:
        ensure_schema(conn)

        if args.update_universe:
            action_update_universe(conn, save_csv=args.save_csv, out_dir=args.out_dir)

        if args.generate_report:
            report = action_generate_report(conn, save_json=args.save_json, out_dir=args.out_dir)
            print("\n" + "="*60)
            print("股票宇宙報告")
            print("="*60)
            print(json.dumps(report, ensure_ascii=False, indent=2))

        if not args.update_universe and not args.generate_report:
            # 默認執行：更新宇宙並生成報告
            action_update_universe(conn, save_csv=True, out_dir=args.out_dir)
            report = action_generate_report(conn, save_json=True, out_dir=args.out_dir)
            print("\n" + "="*60)
            print("股票宇宙報告")
            print("="*60) 
            print(json.dumps(report, ensure_ascii=False, indent=2))

        return 0
        
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())