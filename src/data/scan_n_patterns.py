#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N字回撤掃描主程式
對整個台股市場進行N字形態掃描並輸出結果
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path

# 添加專案路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.data.n_pattern_scanner import NPatternScanner
except ImportError:
    from n_pattern_scanner import NPatternScanner

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('n_pattern_scan.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """主函數：執行N字回撤掃描"""
    logger.info("🎯 開始執行N字回撤掃描...")
    
    # 設定參數
    config = {
        'lookback_bars': 60,      # 回看60根日K
        'min_change_pct': 0.08,   # ZigZag最小8%變化 
        'retr_min': 0.30,         # 最小30%回撤
        'retr_max': 0.70,         # 最大70%回撤
        'c_tolerance': 0.01       # C點容差1%
    }
    
    # 資料庫路徑
    universe_db = "data/cleaned/taiwan_stocks_cleaned.db"
    price_db = "data/cleaned/taiwan_stocks_cleaned.db"  # 同一個資料庫
    
    # 檢查資料庫是否存在
    if not os.path.exists(universe_db):
        logger.error(f"找不到股票宇宙資料庫: {universe_db}")
        return
    
    # 初始化掃描器
    scanner = NPatternScanner(**config)
    
    logger.info("掃描參數:")
    for key, value in config.items():
        logger.info(f"  {key}: {value}")
    
    # 執行掃描
    start_time = datetime.now()
    results = scanner.scan_stock_universe(universe_db, price_db)
    end_time = datetime.now()
    
    scan_duration = (end_time - start_time).total_seconds()
    logger.info(f"⏱️  掃描耗時: {scan_duration:.1f} 秒")
    
    if not results:
        logger.warning("⚠️  未找到符合條件的N字回撤形態")
        return
    
    # 保存結果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"data/reports/n_pattern_scan_results_{timestamp}.xlsx"
    
    # 確保輸出目錄存在
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # 保存掃描結果
    scanner.save_scan_results(results, output_file)
    
    # 顯示摘要
    logger.info(f"🎉 掃描完成! 找到 {len(results)} 檔符合N字回撤條件的股票")
    
    # 顯示前10名
    logger.info("\n🏆 評分前10名:")
    for i, result in enumerate(results[:10], 1):
        logger.info(f"  {i:2d}. {result['stock_id']} {result['stock_name']:8s} "
                   f"評分:{result['total_score']:3d} "
                   f"漲幅:{result['rise_pct']:.1%} "
                   f"回撤:{result['retracement_pct']:.1%}")
    
    # 統計分析
    scores = [r['total_score'] for r in results]
    logger.info(f"\n📊 評分分布:")
    logger.info(f"  平均分: {sum(scores)/len(scores):.1f}")
    logger.info(f"  最高分: {max(scores)}")
    logger.info(f"  最低分: {min(scores)}")
    logger.info(f"  80分以上: {sum(1 for s in scores if s >= 80)} 檔")
    logger.info(f"  70分以上: {sum(1 for s in scores if s >= 70)} 檔")
    
    # 觸發條件統計
    trigger_stats = {
        'break_high': sum(1 for r in results if r['trigger_break_high']),
        'volume_ema': sum(1 for r in results if r['trigger_volume_ema']),
        'rsi_strong': sum(1 for r in results if r['trigger_rsi_strong'])
    }
    
    logger.info(f"\n🎯 觸發條件統計:")
    logger.info(f"  突破昨高: {trigger_stats['break_high']} 檔")
    logger.info(f"  量增上穿EMA5: {trigger_stats['volume_ema']} 檔")
    logger.info(f"  RSI強勢: {trigger_stats['rsi_strong']} 檔")
    
    logger.info(f"\n📁 結果檔案: {output_file}")
    logger.info("✅ N字回撤掃描完成!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("❌ 用戶中斷掃描")
    except Exception as e:
        logger.error(f"❌ 掃描過程發生錯誤: {e}")
        import traceback
        logger.error(traceback.format_exc())