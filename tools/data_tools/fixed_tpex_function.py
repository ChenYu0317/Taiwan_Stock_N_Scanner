    def fetch_tpex_stock_data(self, stock_id: str, year: int, month: int) -> Optional[pd.DataFrame]:
        """
        從TPEx獲取單一股票的月度歷史資料 - 強制修復版
        TPEx 官方API已損壞，直接使用 FinMind 穩定備援
        
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