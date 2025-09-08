#!/usr/bin/env python3
"""
清理股票宇宙 - 嚴格過濾權證和非股票
"""
import pandas as pd
import sqlite3
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_stock_universe():
    """嚴格清理股票宇宙"""
    
    # 讀取現有數據
    df = pd.read_csv("universe_20250908.csv")
    logger.info(f"原始數據: {len(df)} 檔")
    
    # 統計原始分布
    original_twse = len(df[df['market'] == 'TWSE'])
    original_tpex = len(df[df['market'] == 'TPEx'])
    logger.info(f"原始分布: TWSE={original_twse}, TPEx={original_tpex}")
    
    # 嚴格過濾條件
    
    # 1. 排除明顯的權證關鍵字
    warrant_keywords = [
        '售01', '售02', '售03', '購01', '購02', '購03',
        'U　', 'P　', 'Q　', 'X　', 'Y　', 'Z　',  # 權證常見代號
        '群益', '元大', '凱基', '統一', '富邦',  # 券商發行的權證
        '權證', '認購', '認售'
    ]
    
    for keyword in warrant_keywords:
        before_count = len(df)
        df = df[~df['name'].str.contains(keyword, na=False, regex=False)]
        after_count = len(df)
        if before_count != after_count:
            logger.info(f"排除含 '{keyword}' : {before_count - after_count} 檔")
    
    # 2. 排除特定代號範圍的權證
    # 權證通常在 7000-7999 範圍，但要保留正常股票
    warrant_pattern_codes = []
    for _, row in df.iterrows():
        code = str(row['stock_id'])  # 確保是字串
        name = str(row['name'])
        
        # 7000-7999 範圍的嚴格檢查
        if code.startswith('7'):
            # 如果名稱包含權證特徵，則排除
            if any(kw in name for kw in ['購', '售', 'U　', 'P　', 'Q　']) or len(name) > 20:
                warrant_pattern_codes.append(code)
    
    if warrant_pattern_codes:
        logger.info(f"排除權證代號模式: {len(warrant_pattern_codes)} 檔")
        df = df[~df['stock_id'].isin(warrant_pattern_codes)]
    
    # 3. 排除其他非股票
    other_keywords = ['ETF', 'ETN', '基金', '受益憑證', '債券', '特別股']
    for keyword in other_keywords:
        before_count = len(df)
        df = df[~df['name'].str.contains(keyword, na=False)]
        after_count = len(df)
        if before_count != after_count:
            logger.info(f"排除含 '{keyword}' : {before_count - after_count} 檔")
    
    # 4. 檢查代號格式：保留純4位數字
    df['stock_id'] = df['stock_id'].astype(str)  # 確保是字串型別
    df = df[df['stock_id'].str.match(r'^\d{4}$')]
    
    # 5. 去除重複
    df = df.drop_duplicates(subset=['stock_id'])
    
    # 最終統計
    final_twse = len(df[df['market'] == 'TWSE'])
    final_tpex = len(df[df['market'] == 'TPEx'])
    
    logger.info(f"清理後數據: {len(df)} 檔")
    logger.info(f"最終分布: TWSE={final_twse}, TPEx={final_tpex}")
    
    # 檢查是否有知名股票
    famous_stocks = ['2330', '2317', '2454', '2412', '1101', '1216']  # 台積電、鴻海、聯發科、中華電、台泥、統一
    missing_famous = []
    for stock_id in famous_stocks:
        if stock_id not in df['stock_id'].values:
            missing_famous.append(stock_id)
    
    if missing_famous:
        logger.warning(f"缺少知名股票: {missing_famous}")
    else:
        logger.info("✅ 知名股票檢查通過")
    
    # 顯示一些範例
    logger.info("TWSE 前5檔:")
    twse_sample = df[df['market'] == 'TWSE'].head()
    for _, row in twse_sample.iterrows():
        logger.info(f"  {row['stock_id']}: {row['name']}")
    
    logger.info("TPEx 前5檔:")
    tpex_sample = df[df['market'] == 'TPEx'].head()
    for _, row in tpex_sample.iterrows():
        logger.info(f"  {row['stock_id']}: {row['name']}")
    
    # 保存清理後的數據
    clean_filename = "universe_cleaned_20250908.csv"
    df.to_csv(clean_filename, index=False, encoding='utf-8-sig')
    logger.info(f"清理後數據已保存: {clean_filename}")
    
    # 更新到資料庫
    conn = sqlite3.connect("taiwan_stocks_cleaned.db")
    
    # 創建表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_universe (
            stock_id TEXT PRIMARY KEY,
            name TEXT,
            isin TEXT,
            market TEXT,
            listed_date DATE,
            status TEXT DEFAULT 'active',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 清空並插入
    conn.execute("DELETE FROM stock_universe")
    
    for _, row in df.iterrows():
        conn.execute("""
            INSERT INTO stock_universe (stock_id, name, isin, market, listed_date, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            row['stock_id'], row['name'], row['isin'], 
            row['market'], row['listed_date'], 'active'
        ))
    
    conn.commit()
    conn.close()
    
    logger.info("清理後數據已更新到資料庫: taiwan_stocks_cleaned.db")
    
    return df

def quality_check(df):
    """數據品質檢查"""
    logger.info("執行數據品質檢查...")
    
    # 檢查重複
    duplicates = df[df.duplicated('stock_id')]
    if not duplicates.empty:
        logger.warning(f"發現重複股票代號: {len(duplicates)} 筆")
    
    # 檢查代號格式
    invalid_codes = df[~df['stock_id'].str.match(r'^\d{4}$')]
    if not invalid_codes.empty:
        logger.warning(f"發現無效代號: {len(invalid_codes)} 筆")
    
    # 檢查市場分布合理性
    twse_count = len(df[df['market'] == 'TWSE'])
    tpex_count = len(df[df['market'] == 'TPEx'])
    
    logger.info(f"市場分布: TWSE={twse_count}, TPEx={tpex_count}")
    
    if twse_count < 900 or twse_count > 1200:
        logger.warning(f"TWSE股票數量異常: {twse_count} (正常範圍 900-1200)")
    
    if tpex_count < 600 or tpex_count > 900:
        logger.warning(f"TPEx股票數量異常: {tpex_count} (正常範圍 600-900)")
    
    logger.info("數據品質檢查完成")

if __name__ == "__main__":
    cleaned_df = clean_stock_universe()
    quality_check(cleaned_df)
    
    print("\n" + "="*50)
    print("數據清理完成")
    print("="*50)
    print(f"清理前: 2195 檔")
    print(f"清理後: {len(cleaned_df)} 檔")
    print(f"TWSE: {len(cleaned_df[cleaned_df['market'] == 'TWSE'])} 檔")
    print(f"TPEx: {len(cleaned_df[cleaned_df['market'] == 'TPEx'])} 檔")
    print("\n建議使用 universe_cleaned_20250908.csv 作為最終股票清單")