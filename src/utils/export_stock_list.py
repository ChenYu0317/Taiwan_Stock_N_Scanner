#!/usr/bin/env python3
"""
導出股票清單供驗證
"""

import sqlite3
import pandas as pd
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def export_stock_universe():
    """導出股票宇宙清單"""
    db_path = "data/cleaned/taiwan_stocks_cleaned.db"
    
    try:
        # 連接資料庫
        conn = sqlite3.connect(db_path)
        
        # 查詢所有股票
        query = """
        SELECT 
            stock_id,
            name,
            market,
            status,
            updated_at
        FROM stock_universe
        ORDER BY market, stock_id
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # 基本統計
        total_count = len(df)
        twse_count = len(df[df['market'] == 'TWSE'])
        tpex_count = len(df[df['market'] == 'TPEx'])
        
        logger.info(f"總計: {total_count} 檔股票")
        logger.info(f"上市(TWSE): {twse_count} 檔")
        logger.info(f"上櫃(TPEx): {tpex_count} 檔")
        
        # 導出 CSV
        csv_filename = f"taiwan_stock_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(csv_filename, index=False, encoding='utf-8')
        logger.info(f"已導出至: {csv_filename}")
        
        # 導出 Excel (如果需要)
        excel_filename = f"taiwan_stock_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(excel_filename, index=False)
        logger.info(f"已導出至: {excel_filename}")
        
        # 顯示各市場前10筆範例
        print("\n=== 上市股票範例 (前10筆) ===")
        twse_sample = df[df['market'] == 'TWSE'].head(10)
        for _, row in twse_sample.iterrows():
            print(f"{row['stock_id']}\t{row['name']}\t{row['market']}")
        
        print("\n=== 上櫃股票範例 (前10筆) ===")
        tpex_sample = df[df['market'] == 'TPEx'].head(10)
        for _, row in tpex_sample.iterrows():
            print(f"{row['stock_id']}\t{row['name']}\t{row['market']}")
        
        # 檢查可能的問題
        print("\n=== 數據品質檢查 ===")
        
        # 檢查重複股票代號
        duplicates = df[df.duplicated(['stock_id'], keep=False)]
        if not duplicates.empty:
            print(f"⚠️  發現重複股票代號: {len(duplicates)} 筆")
            print(duplicates[['stock_id', 'name', 'market']])
        else:
            print("✅ 無重複股票代號")
        
        # 檢查股票代號格式
        invalid_codes = df[~df['stock_id'].str.match(r'^\d{4}$')]
        if not invalid_codes.empty:
            print(f"⚠️  股票代號格式異常: {len(invalid_codes)} 筆")
            print(invalid_codes[['stock_id', 'name', 'market']].head())
        else:
            print("✅ 股票代號格式正常")
        
        # 檢查可能的ETF混入
        etf_keywords = ['ETF', 'ETN', '受益憑證', '基金', '權證']
        potential_etf = df[df['name'].str.contains('|'.join(etf_keywords), na=False)]
        if not potential_etf.empty:
            print(f"⚠️  疑似ETF混入: {len(potential_etf)} 筆")
            print(potential_etf[['stock_id', 'name', 'market']])
        else:
            print("✅ 無明顯ETF混入")
        
        # 檢查市場分布是否合理
        print(f"\n=== 市場分布檢查 ===")
        print(f"TWSE: {twse_count} 檔 ({twse_count/total_count*100:.1f}%)")
        print(f"TPEx: {tpex_count} 檔 ({tpex_count/total_count*100:.1f}%)")
        
        if twse_count < 900 or twse_count > 1200:
            print("⚠️  TWSE股票數量可能異常 (正常範圍 900-1200)")
        if tpex_count < 600 or tpex_count > 1000:
            print("⚠️  TPEx股票數量可能異常 (正常範圍 600-1000)")
        
        return csv_filename, excel_filename
        
    except Exception as e:
        logger.error(f"導出失敗: {e}")
        return None, None

def create_market_analysis():
    """創建市場分析報告"""
    db_path = "data/cleaned/taiwan_stocks_cleaned.db"
    
    try:
        conn = sqlite3.connect(db_path)
        
        # 按市場和代碼開頭分析
        analysis_query = """
        SELECT 
            market,
            SUBSTR(stock_id, 1, 1) as first_digit,
            COUNT(*) as count
        FROM stock_universe
        GROUP BY market, SUBSTR(stock_id, 1, 1)
        ORDER BY market, first_digit
        """
        
        analysis_df = pd.read_sql_query(analysis_query, conn)
        conn.close()
        
        print("\n=== 股票代號分布分析 ===")
        for _, row in analysis_df.iterrows():
            print(f"{row['market']} - {row['first_digit']}xxx: {row['count']} 檔")
        
        # 導出分析結果
        analysis_filename = f"market_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        analysis_df.to_csv(analysis_filename, index=False)
        print(f"\n分析結果已導出至: {analysis_filename}")
        
        return analysis_filename
        
    except Exception as e:
        logger.error(f"分析失敗: {e}")
        return None

def main():
    """主函數"""
    logger.info("開始導出股票清單...")
    
    # 導出股票清單
    csv_file, excel_file = export_stock_universe()
    
    if csv_file:
        print(f"\n✅ 導出完成!")
        print(f"CSV 檔案: {csv_file}")
        print(f"Excel 檔案: {excel_file}")
    
    # 創建市場分析
    analysis_file = create_market_analysis()
    if analysis_file:
        print(f"分析檔案: {analysis_file}")
    
    print(f"\n請檢查上述檔案並驗證股票清單是否正確")

if __name__ == "__main__":
    main()