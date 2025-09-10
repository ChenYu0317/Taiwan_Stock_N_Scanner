#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
200檔代表性股票測試清單 - 用於N字回撤演算法驗證
"""

import sys
import os
sys.path.insert(0, 'src/data')

from price_data_pipeline import TaiwanStockPriceDataPipeline
import sqlite3
import pandas as pd
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_200_test_stocks():
    """準備200檔代表性測試股票清單"""
    
    # 大型股 (50檔) - 權值股、藍籌股
    large_caps = [
        # 台股權王與科技龍頭
        ("2330", "台積電", "TWSE"), ("2454", "聯發科", "TWSE"), ("2317", "鴻海", "TWSE"),
        ("2412", "中華電", "TWSE"), ("1301", "台塑", "TWSE"), ("1303", "南亞", "TWSE"),
        ("2881", "富邦金", "TWSE"), ("2882", "國泰金", "TWSE"), ("2883", "開發金", "TWSE"),
        ("2891", "中信金", "TWSE"), ("2892", "第一金", "TWSE"), ("2884", "玉山金", "TWSE"),
        
        # 傳產龍頭
        ("1101", "台泥", "TWSE"), ("1102", "亞泥", "TWSE"), ("1216", "統一", "TWSE"),
        ("1301", "台塑", "TWSE"), ("1326", "台化", "TWSE"), ("2002", "中鋼", "TWSE"),
        ("2105", "正新", "TWSE"), ("2207", "和泰車", "TWSE"), ("2301", "光寶科", "TWSE"),
        ("2303", "聯電", "TWSE"), ("2308", "台達電", "TWSE"), ("2357", "華碩", "TWSE"),
        
        # 半導體與電子
        ("2379", "瑞昱", "TWSE"), ("2382", "廣達", "TWSE"), ("2395", "研華", "TWSE"),
        ("2408", "南亞科", "TWSE"), ("2409", "友達", "TWSE"), ("2474", "可成", "TWSE"),
        ("3008", "大立光", "TWSE"), ("3034", "聯詠", "TWSE"), ("3037", "欣興", "TWSE"),
        ("3045", "台灣大", "TWSE"), ("3231", "緯創", "TWSE"), ("3481", "群創", "TWSE"),
        
        # 生技與民生
        ("4904", "遠傳", "TWSE"), ("6505", "台塑化", "TWSE"), ("2912", "統一超", "TWSE"),
        ("2801", "彰銀", "TWSE"), ("2886", "兆豐金", "TWSE"), ("9904", "寶成", "TWSE"),
        ("1434", "福懋", "TWSE"), ("1440", "南紡", "TWSE"), ("1476", "儒鴻", "TWSE"),
        ("2204", "中華", "TWSE"), ("2609", "陽明", "TWSE"), ("2615", "萬海", "TWSE"),
        
        # 其他權值股
        ("2201", "裕隆", "TWSE"), ("2227", "裕日車", "TWSE"), ("2347", "聯強", "TWSE"),
        ("2376", "技嘉", "TWSE"), ("2377", "微星", "TWSE"), ("2385", "群光", "TWSE")
    ]
    
    # 中型股 (100檔) - 各產業代表
    mid_caps = [
        # 科技中型股
        ("2324", "仁寶", "TWSE"), ("2327", "國巨", "TWSE"), ("2329", "華碩", "TWSE"),
        ("2337", "漢唐", "TWSE"), ("2344", "華邦電", "TWSE"), ("2345", "智邦", "TWSE"),
        ("2351", "順德", "TWSE"), ("2352", "佳世達", "TWSE"), ("2353", "宏碁", "TWSE"),
        ("2354", "鴻準", "TWSE"), ("2355", "敬鵬", "TWSE"), ("2356", "英業達", "TWSE"),
        ("2360", "致茂", "TWSE"), ("2362", "藍天", "TWSE"), ("2365", "昆盈", "TWSE"),
        ("2367", "燿華", "TWSE"), ("2368", "金像電", "TWSE"), ("2369", "菱光", "TWSE"),
        ("2371", "大同", "TWSE"), ("2373", "震旦行", "TWSE"), ("2374", "佳能", "TWSE"),
        ("2375", "智寶", "TWSE"), ("2377", "微星", "TWSE"), ("2380", "虹光", "TWSE"),
        ("2383", "台光電", "TWSE"), ("2384", "勝華", "TWSE"), ("2387", "精元", "TWSE"),
        
        # 傳產中型股
        ("1102", "亞泥", "TWSE"), ("1108", "幸福", "TWSE"), ("1109", "信大", "TWSE"),
        ("1110", "東泥", "TWSE"), ("1201", "味全", "TWSE"), ("1203", "味王", "TWSE"),
        ("1210", "大成", "TWSE"), ("1213", "大飲", "TWSE"), ("1215", "卜蜂", "TWSE"),
        ("1217", "愛之味", "TWSE"), ("1218", "泰山", "TWSE"), ("1219", "福壽", "TWSE"),
        ("1220", "台榮", "TWSE"), ("1225", "福懋油", "TWSE"), ("1227", "佳格", "TWSE"),
        ("1229", "聯華", "TWSE"), ("1231", "聯華食", "TWSE"), ("1232", "大統益", "TWSE"),
        ("1233", "天仁", "TWSE"), ("1234", "黑松", "TWSE"), ("1235", "興泰", "TWSE"),
        ("1236", "宏亞", "TWSE"), ("1301", "台塑", "TWSE"), ("1304", "台聚", "TWSE"),
        ("1305", "華夏", "TWSE"), ("1307", "三芳", "TWSE"), ("1308", "亞聚", "TWSE"),
        
        # 金融中型股
        ("2809", "京城銀", "TWSE"), ("2812", "台中銀", "TWSE"), ("2820", "華票", "TWSE"),
        ("2823", "中壽", "TWSE"), ("2832", "台產", "TWSE"), ("2834", "臺企銀", "TWSE"),
        ("2836", "高雄銀", "TWSE"), ("2837", "萬泰銀", "TWSE"), ("2838", "聯邦銀", "TWSE"),
        ("2845", "遠東銀", "TWSE"), ("2849", "安泰銀", "TWSE"), ("2850", "新產", "TWSE"),
        ("2851", "中再保", "TWSE"), ("2852", "第一保", "TWSE"), ("2855", "統一證", "TWSE"),
        ("2856", "元富證", "TWSE"), ("2867", "三商壽", "TWSE"), ("2888", "新光金", "TWSE"),
        ("2889", "國票金", "TWSE"), ("2890", "永豐金", "TWSE"), ("2893", "王道銀", "TWSE"),
        
        # 其他中型股
        ("2501", "國建", "TWSE"), ("2504", "國產", "TWSE"), ("2505", "國揚", "TWSE"),
        ("2506", "太設", "TWSE"), ("2508", "大同", "TWSE"), ("2509", "全坤建", "TWSE"),
        ("2511", "太子", "TWSE"), ("2514", "龍邦", "TWSE"), ("2515", "中工", "TWSE"),
        ("2516", "新建", "TWSE"), ("2520", "冠德", "TWSE"), ("2524", "京城", "TWSE"),
        ("2527", "宏璟", "TWSE"), ("2528", "皇普", "TWSE"), ("2530", "華建", "TWSE"),
        ("2535", "達欣工", "TWSE"), ("2536", "宏普", "TWSE"), ("2537", "聯翔", "TWSE"),
        ("2538", "基泰", "TWSE"), ("2539", "櫻花建", "TWSE"), ("2540", "愛山林", "TWSE")
    ]
    
    # 小型股 (30檔) - 測試低流動性
    small_caps = [
        ("1233", "天仁", "TWSE"), ("1235", "興泰", "TWSE"), ("1258", "其祥-KY", "TWSE"),
        ("1259", "安心", "TWSE"), ("1262", "綠悅-KY", "TWSE"), ("1264", "德麥", "TWSE"),
        ("1265", "泰山企", "TWSE"), ("1268", "漢來美食", "TWSE"), ("1269", "凱羿-KY", "TWSE"),
        ("1271", "恆隆行", "TWSE"), ("1773", "勝一", "TWSE"), ("1774", "臺觀", "TWSE"),
        ("1776", "展宇", "TWSE"), ("1777", "生展", "TWSE"), ("1783", "和康生", "TWSE"),
        ("1784", "訊聯", "TWSE"), ("1785", "光洋科", "TWSE"), ("1786", "科妍", "TWSE"),
        ("1787", "福盈科", "TWSE"), ("1788", "杏昌", "TWSE"), ("1789", "神隆", "TWSE"),
        ("1795", "美時", "TWSE"), ("1796", "金穎生技", "TWSE"), ("1797", "事欣科", "TWSE"),
        ("1798", "億豐", "TWSE"), ("2030", "彰源", "TWSE"), ("2032", "新鋼", "TWSE"),
        ("2033", "佳大", "TWSE"), ("2034", "允強", "TWSE"), ("2038", "海光", "TWSE")
    ]
    
    # 上櫃股票 (20檔) - TPEx數據驗證
    tpex_stocks = [
        ("6488", "環球晶", "TPEx"), ("4966", "譜瑞-KY", "TPEx"), ("4967", "十銓", "TPEx"),
        ("5471", "松翰", "TPEx"), ("5483", "中美晶", "TPEx"), ("5484", "慧友", "TPEx"),
        ("5522", "遠雄", "TPEx"), ("5525", "順天", "TPEx"), ("5871", "中租-KY", "TPEx"),
        ("6442", "光聖", "TPEx"), ("6451", "訊芯-KY", "TPEx"), ("6456", "GIS-KY", "TPEx"),
        ("6525", "捷敏-KY", "TPEx"), ("6531", "愛普", "TPEx"), ("6532", "瑞耘", "TPEx"),
        ("6533", "晶心科", "TPEx"), ("6541", "泰福-KY", "TPEx"), ("6542", "隆中", "TPEx"),
        ("8027", "鈦昇", "TPEx"), ("8040", "九暘", "TPEx")
    ]
    
    # 合併所有清單
    all_stocks = large_caps + mid_caps + small_caps + tpex_stocks
    
    logger.info(f"📊 準備完成 200 檔測試股票清單:")
    logger.info(f"   大型股: {len(large_caps)} 檔")
    logger.info(f"   中型股: {len(mid_caps)} 檔") 
    logger.info(f"   小型股: {len(small_caps)} 檔")
    logger.info(f"   上櫃股: {len(tpex_stocks)} 檔")
    logger.info(f"   總計: {len(all_stocks)} 檔")
    
    return all_stocks

def batch_fetch_test_stocks(target_bars=60):
    """批次抓取200檔測試股票的歷史資料"""
    
    logger.info(f"🚀 開始批次抓取 200 檔股票的 {target_bars} 根K線")
    
    test_stocks = get_200_test_stocks()
    pipeline = TaiwanStockPriceDataPipeline()
    
    results = []
    start_time = time.time()
    
    for i, (stock_id, name, market) in enumerate(test_stocks, 1):
        logger.info(f"\n📊 [{i:3d}/200] 抓取 {stock_id} ({name}) - {market}")
        
        try:
            success = pipeline.fetch_stock_historical_data(stock_id, market, target_bars)
            
            if success:
                # 驗證數據
                conn = sqlite3.connect(pipeline.db_path)
                df = pd.read_sql_query("""
                    SELECT COUNT(*) as count, MIN(date) as min_date, MAX(date) as max_date,
                           source, market
                    FROM daily_prices 
                    WHERE stock_id = ?
                """, conn, params=(stock_id,))
                conn.close()
                
                if not df.empty and df.iloc[0]['count'] > 0:
                    count = df.iloc[0]['count']
                    min_date = df.iloc[0]['min_date']
                    max_date = df.iloc[0]['max_date']
                    source = df.iloc[0]['source']
                    
                    logger.info(f"✅ 成功: {count} 筆 ({min_date} ~ {max_date}) [{source}]")
                    
                    results.append({
                        'stock_id': stock_id,
                        'name': name,
                        'market': market,
                        'count': count,
                        'success': True,
                        'source': source,
                        'date_range': f"{min_date} ~ {max_date}"
                    })
                else:
                    logger.warning(f"❌ 無數據: {stock_id}")
                    results.append({
                        'stock_id': stock_id, 'name': name, 'market': market,
                        'count': 0, 'success': False, 'source': None, 'date_range': None
                    })
            else:
                logger.error(f"❌ 抓取失敗: {stock_id}")
                results.append({
                    'stock_id': stock_id, 'name': name, 'market': market,
                    'count': 0, 'success': False, 'source': None, 'date_range': None
                })
                
        except Exception as e:
            logger.error(f"❌ 異常: {stock_id} - {e}")
            results.append({
                'stock_id': stock_id, 'name': name, 'market': market,
                'count': 0, 'success': False, 'source': str(e), 'date_range': None
            })
    
    # 統計結果
    elapsed_time = time.time() - start_time
    success_count = sum(1 for r in results if r['success'])
    total_records = sum(r['count'] for r in results if r['success'])
    
    logger.info("\n" + "="*60)
    logger.info("📊 批次抓取結果統計")
    logger.info("="*60)
    logger.info(f"⏱️  執行時間: {elapsed_time:.1f} 秒 ({elapsed_time/60:.1f} 分鐘)")
    logger.info(f"✅ 成功率: {success_count}/200 ({success_count/2:.1f}%)")
    logger.info(f"📊 總數據: {total_records:,} 筆記錄")
    
    # 按市場統計
    twse_results = [r for r in results if r['market'] == 'TWSE']
    tpex_results = [r for r in results if r['market'] == 'TPEx']
    
    twse_success = sum(1 for r in twse_results if r['success'])
    tpex_success = sum(1 for r in tpex_results if r['success'])
    
    logger.info(f"🏢 TWSE: {twse_success}/{len(twse_results)} 成功 ({twse_success/len(twse_results)*100:.1f}%)")
    logger.info(f"🏪 TPEx: {tpex_success}/{len(tpex_results)} 成功 ({tpex_success/len(tpex_results)*100:.1f}%)")
    
    # 失敗案例
    failed_stocks = [r for r in results if not r['success']]
    if failed_stocks:
        logger.info(f"\n⚠️ 失敗股票 ({len(failed_stocks)} 檔):")
        for r in failed_stocks[:10]:  # 只顯示前10個
            logger.info(f"   {r['stock_id']} ({r['name']}) - {r['market']}")
        if len(failed_stocks) > 10:
            logger.info(f"   ... 還有 {len(failed_stocks)-10} 檔")
    
    return results

if __name__ == "__main__":
    # 先只顯示清單，不執行抓取
    test_stocks = get_200_test_stocks()
    
    logger.info("\n🎯 準備就緒！")
    logger.info("如要執行批次抓取，請運行:")
    logger.info("python test_200_stocks.py --fetch")
    
    # 如果命令行參數包含 --fetch 才執行抓取
    if len(sys.argv) > 1 and '--fetch' in sys.argv:
        batch_fetch_test_stocks(60)