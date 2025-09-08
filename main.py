#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台股 N 字回撤掃描器 - 主程式進入點
"""

import sys
import os

# 添加 src 到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from data.taiwan_stock_pipeline_fixed import main as pipeline_main

if __name__ == "__main__":
    print("台股 N 字回撤掃描器")
    print("=" * 50)
    
    # 執行數據管道
    pipeline_main()
