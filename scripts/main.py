#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台股N字回撤掃描系統 - 主執行入口
"""

import sys
import os
import argparse

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data.price_data_pipeline import TaiwanStockPriceDataPipeline
from signal.n_pattern_detector import NPatternDetector
from config.settings import get_database_path

def collect_data(max_stocks: int = 500, target_bars: int = 60):
    """收集股票數據"""
    print(f"🚀 收集股票數據：{max_stocks}檔股票，{target_bars}根K線")
    
    pipeline = TaiwanStockPriceDataPipeline(get_database_path())
    success, failed = pipeline.run_price_data_pipeline_optimized(
        max_stocks=max_stocks,
        target_bars=target_bars
    )
    
    print(f"✅ 數據收集完成：成功{success}檔，失敗{failed}檔")
    return success, failed

def scan_patterns(export_csv: bool = False):
    """掃描N字模式"""
    print("🔍 開始N字模式掃描")
    
    detector = NPatternDetector(get_database_path())
    signals = detector.scan_all_stocks()
    
    print(f"📊 找到{len(signals)}個N字信號")
    
    if export_csv and signals:
        output_path = "data/exports/n_pattern_signals.csv"
        detector.export_signals_to_csv(signals, output_path)
        print(f"📄 信號已匯出至：{output_path}")
    
    return signals

def full_analysis(max_stocks: int = 1900, target_bars: int = 60, export_csv: bool = True):
    """完整分析流程"""
    print("🎯 執行完整N字回撤分析")
    
    # 1. 收集數據
    collect_data(max_stocks, target_bars)
    
    # 2. 掃描模式
    signals = scan_patterns(export_csv)
    
    print("🎉 完整分析完成")
    return signals

def main():
    parser = argparse.ArgumentParser(description='台股N字回撤掃描系統')
    parser.add_argument('command', choices=['collect', 'scan', 'full'], 
                       help='執行命令: collect(收集數據), scan(掃描模式), full(完整分析)')
    parser.add_argument('--stocks', type=int, default=1900, 
                       help='最大股票數量 (預設: 1900, 全市場)')
    parser.add_argument('--bars', type=int, default=60, 
                       help='K線數量 (預設: 60)')
    parser.add_argument('--export', action='store_true', 
                       help='匯出結果至CSV')
    
    args = parser.parse_args()
    
    if args.command == 'collect':
        collect_data(args.stocks, args.bars)
    elif args.command == 'scan':
        scan_patterns(args.export)
    elif args.command == 'full':
        full_analysis(args.stocks, args.bars, args.export)

if __name__ == "__main__":
    main()