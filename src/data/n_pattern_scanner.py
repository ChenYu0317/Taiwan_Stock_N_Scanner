#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N字回撤掃描引擎
整合 ZigZag 轉折點偵測、技術指標計算、ABC 形態識別和評分系統
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sqlite3
from typing import List, Dict, Optional, Tuple
import logging
from pathlib import Path

try:
    from .zigzag import ZigZagDetector
    from .indicators import NPatternIndicators
except ImportError:
    # 當直接運行此檔案時的fallback
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from zigzag import ZigZagDetector
    from indicators import NPatternIndicators

logger = logging.getLogger(__name__)

class NPatternScanner:
    """N字回撤掃描器主類"""
    
    def __init__(self, 
                 lookback_bars: int = 60,
                 min_change_pct: float = 0.08,
                 retr_min: float = 0.30,
                 retr_max: float = 0.70,
                 c_tolerance: float = 0.01):
        """
        初始化掃描器
        
        Args:
            lookback_bars: 回看K線根數 (預設60根)
            min_change_pct: ZigZag最小變化百分比 (預設8%)
            retr_min: 最小回撤比例 (預設30%)  
            retr_max: 最大回撤比例 (預設70%)
            c_tolerance: C點相對A點容差 (預設1%)
        """
        self.lookback_bars = lookback_bars
        self.min_change_pct = min_change_pct
        self.retr_min = retr_min
        self.retr_max = retr_max
        self.c_tolerance = c_tolerance
        
        self.zigzag = ZigZagDetector(min_change_pct=min_change_pct)
        
    def scan_single_stock(self, stock_data: pd.DataFrame, stock_id: str, stock_name: str) -> Optional[Dict]:
        """
        掃描單一股票的N字回撤形態
        
        Args:
            stock_data: 股票OHLC資料 DataFrame
            stock_id: 股票代碼
            stock_name: 股票名稱
            
        Returns:
            掃描結果 dict 或 None
        """
        try:
            # 確保有足夠的資料
            if len(stock_data) < self.lookback_bars:
                logger.debug(f"{stock_id} 資料不足: {len(stock_data)} < {self.lookback_bars}")
                return None
            
            # 只取最近的 lookback_bars 根K線
            recent_data = stock_data.tail(self.lookback_bars).copy()
            recent_data = recent_data.reset_index(drop=True)
            
            # 1. ZigZag 轉折點偵測
            pivots = self.zigzag.detect_zigzag_points(recent_data)
            if len(pivots) < 3:
                logger.debug(f"{stock_id} ZigZag轉折點不足: {len(pivots)}")
                return None
            
            # 2. 尋找最後一組ABC形態
            abc_pattern = self.zigzag.find_last_abc_pattern(pivots)
            if not abc_pattern:
                logger.debug(f"{stock_id} 未找到符合的ABC形態")
                return None
            
            A, B, C = abc_pattern
            
            # 3. 額外的回撤比例驗證
            retr_pct = (B['price'] - C['price']) / (B['price'] - A['price'])
            if not (self.retr_min <= retr_pct <= self.retr_max):
                logger.debug(f"{stock_id} 回撤比例不符: {retr_pct:.3f}")
                return None
            
            # 4. C點不破A點驗證
            if C['price'] <= A['price'] * (1 - self.c_tolerance):
                logger.debug(f"{stock_id} C點破A點: C={C['price']:.2f}, A={A['price']:.2f}")
                return None
            
            # 5. 計算技術指標
            indicators = NPatternIndicators(recent_data)
            
            # 6. 檢查觸發條件
            triggers = indicators.check_trigger_conditions()
            if not triggers['any_triggered']:
                logger.debug(f"{stock_id} 未觸發任何條件")
                return None
            
            # 7. 計算評分
            score_result = indicators.calculate_pattern_score(A, B, C)
            latest_values = indicators.get_latest_values()
            
            # 8. 準備返回結果
            result = {
                'stock_id': stock_id,
                'stock_name': stock_name,
                'scan_date': datetime.now().strftime('%Y-%m-%d'),
                
                # ABC轉折點
                'A_date': A['date'],
                'A_price': A['price'],
                'A_index': A['index'],
                'B_date': B['date'],
                'B_price': B['price'], 
                'B_index': B['index'],
                'C_date': C['date'],
                'C_price': C['price'],
                'C_index': C['index'],
                
                # 形態指標
                'rise_pct': (B['price'] - A['price']) / A['price'],
                'retracement_pct': retr_pct,
                'bars_ab': B['index'] - A['index'],
                'bars_bc': C['index'] - B['index'],
                'bars_c_to_today': len(recent_data) - C['index'] - 1,
                
                # 當前價格與指標
                'current_price': latest_values['close'],
                'ema5': latest_values['ema5'],
                'ema20': latest_values['ema20'],
                'rsi14': latest_values['rsi14'],
                'volume_ratio': latest_values['volume_ratio'],
                
                # 觸發條件
                'trigger_break_high': triggers['condition1_break_high'],
                'trigger_volume_ema': triggers['condition2_volume_ema'],
                'trigger_rsi_strong': triggers['condition3_rsi_strong'],
                'trigger_count': triggers['trigger_count'],
                
                # 評分
                'total_score': score_result['total_score'],
                'score_breakdown': score_result['breakdown'],
                'score_metrics': score_result['metrics']
            }
            
            logger.info(f"✅ {stock_id} ({stock_name}): Score={result['total_score']}, "
                       f"Rise={result['rise_pct']:.1%}, Retr={result['retracement_pct']:.1%}")
            
            return result
            
        except Exception as e:
            logger.error(f"掃描 {stock_id} 時發生錯誤: {e}")
            return None
    
    def get_stock_data(self, stock_id: str, db_path: str) -> Optional[pd.DataFrame]:
        """
        從資料庫獲取股票歷史資料
        
        Args:
            stock_id: 股票代碼
            db_path: 資料庫路徑
            
        Returns:
            股票資料 DataFrame 或 None
        """
        try:
            conn = sqlite3.connect(db_path)
            
            # 先檢查是否有該股票的資料表
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (f"stock_{stock_id}",))
            if not cursor.fetchone():
                logger.debug(f"股票 {stock_id} 無資料表")
                return None
            
            # 獲取最近的資料
            query = f"""
            SELECT date, open, high, low, close, volume
            FROM stock_{stock_id}
            ORDER BY date DESC
            LIMIT {self.lookback_bars + 10}
            """
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if len(df) < self.lookback_bars:
                return None
                
            # 按日期正序排列
            df = df.sort_values('date').reset_index(drop=True)
            df['date'] = pd.to_datetime(df['date'])
            
            return df
            
        except Exception as e:
            logger.error(f"獲取 {stock_id} 資料時錯誤: {e}")
            return None
    
    def scan_stock_universe(self, universe_db_path: str, price_db_path: str = None) -> List[Dict]:
        """
        掃描整個股票宇宙
        
        Args:
            universe_db_path: 股票宇宙資料庫路徑
            price_db_path: 價格資料庫路徑 (如果為None則使用universe_db_path)
            
        Returns:
            掃描結果列表
        """
        if price_db_path is None:
            price_db_path = universe_db_path
            
        results = []
        
        try:
            # 獲取股票清單
            conn = sqlite3.connect(universe_db_path)
            stock_list = pd.read_sql_query(
                "SELECT stock_id, name FROM stock_universe WHERE status='active' ORDER BY stock_id", 
                conn
            )
            conn.close()
            
            total_stocks = len(stock_list)
            logger.info(f"開始掃描 {total_stocks} 檔股票...")
            
            scanned_count = 0
            found_count = 0
            
            for idx, row in stock_list.iterrows():
                stock_id = row['stock_id']
                stock_name = row['name']
                
                # 獲取股票資料
                stock_data = self.get_stock_data(stock_id, price_db_path)
                if stock_data is None:
                    continue
                
                # 掃描形態
                result = self.scan_single_stock(stock_data, stock_id, stock_name)
                if result:
                    results.append(result)
                    found_count += 1
                
                scanned_count += 1
                
                # 進度報告
                if scanned_count % 100 == 0:
                    logger.info(f"已掃描: {scanned_count}/{total_stocks}, 找到: {found_count}")
            
            logger.info(f"掃描完成! 總計掃描: {scanned_count}, 找到N字形態: {found_count}")
            
        except Exception as e:
            logger.error(f"掃描股票宇宙時錯誤: {e}")
        
        # 按評分排序
        results.sort(key=lambda x: x['total_score'], reverse=True)
        return results
    
    def save_scan_results(self, results: List[Dict], output_path: str):
        """
        保存掃描結果
        
        Args:
            results: 掃描結果列表
            output_path: 輸出檔案路徑
        """
        if not results:
            logger.warning("無掃描結果可保存")
            return
        
        # 轉換為DataFrame
        df = pd.DataFrame(results)
        
        # 重新排列欄位順序
        columns = [
            'stock_id', 'stock_name', 'total_score', 'scan_date',
            'current_price', 'rise_pct', 'retracement_pct',
            'A_date', 'A_price', 'B_date', 'B_price', 'C_date', 'C_price',
            'bars_ab', 'bars_bc', 'bars_c_to_today',
            'ema5', 'ema20', 'rsi14', 'volume_ratio',
            'trigger_break_high', 'trigger_volume_ema', 'trigger_rsi_strong', 'trigger_count'
        ]
        
        # 確保所有欄位都存在
        available_columns = [col for col in columns if col in df.columns]
        df_output = df[available_columns]
        
        # 格式化百分比
        if 'rise_pct' in df_output.columns:
            df_output['rise_pct'] = df_output['rise_pct'].map(lambda x: f"{x:.2%}")
        if 'retracement_pct' in df_output.columns:
            df_output['retracement_pct'] = df_output['retracement_pct'].map(lambda x: f"{x:.2%}")
        
        # 保存CSV
        csv_path = output_path.replace('.xlsx', '.csv')
        df_output.to_csv(csv_path, index=False, encoding='utf-8')
        logger.info(f"掃描結果已保存至: {csv_path}")
        
        # 保存Excel (如果可以)
        try:
            df_output.to_excel(output_path, index=False)
            logger.info(f"掃描結果已保存至: {output_path}")
        except ImportError:
            logger.warning("未安裝openpyxl，跳過Excel輸出")

def test_scanner():
    """測試N字回撤掃描器"""
    # 創建測試資料
    scanner = NPatternScanner(lookback_bars=60)
    
    # 生成固定60天的測試資料
    np.random.seed(42)  # 固定隨機種子
    dates = pd.date_range('2024-01-01', periods=60, freq='D')
    
    # 簡化的N字形態生成
    prices = []
    
    # 前20天：基礎價格100附近
    for i in range(20):
        prices.append(100 + np.random.uniform(-2, 2))
    
    # 21-35天：上漲段 (A到B)
    for i in range(15):
        prices.append(prices[-1] + np.random.uniform(0.5, 1.2))
    
    # 36-45天：回撤段 (B到C)
    peak_price = max(prices[-15:])
    for i in range(10):
        retr = peak_price * 0.06  # 每天回撤6%的峰值
        prices.append(prices[-1] - retr + np.random.uniform(-0.5, 0.5))
    
    # 46-60天：整理段
    for i in range(15):
        prices.append(prices[-1] + np.random.uniform(-1, 1))
    
    # 創建OHLC資料
    df = pd.DataFrame({
        'date': dates,
        'open': [max(1, p + np.random.uniform(-0.5, 0.5)) for p in prices],
        'high': [max(1, p + abs(np.random.uniform(0, 1))) for p in prices],
        'low': [max(1, p - abs(np.random.uniform(0, 1))) for p in prices],
        'close': prices,
        'volume': [int(np.random.uniform(1000000, 5000000)) for _ in range(60)]
    })
    
    # 測試掃描
    result = scanner.scan_single_stock(df, '9999', '測試股票')
    
    if result:
        print("🎯 找到N字回撤形態!")
        print(f"股票: {result['stock_id']} ({result['stock_name']})")
        print(f"評分: {result['total_score']}")
        print(f"上漲幅度: {result['rise_pct']:.1%}")
        print(f"回撤比例: {result['retracement_pct']:.1%}")
        print(f"觸發條件數: {result['trigger_count']}")
        print(f"A: {result['A_date']} = {result['A_price']:.2f}")
        print(f"B: {result['B_date']} = {result['B_price']:.2f}")
        print(f"C: {result['C_date']} = {result['C_price']:.2f}")
    else:
        print("未找到符合條件的N字形態")

if __name__ == "__main__":
    test_scanner()