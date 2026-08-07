from dataclasses import dataclass
from typing import Literal
import yfinance as yf


@dataclass
class StockData:
    """株価データのデータクラス"""
    ticker_symbol: str
    latest_close: float
    ma25_trend: Literal["UPWARD", "FLAT", "DOWNWARD"]
    ma25_value: float | None = None


class StockDataCollector:
    """yfinanceを利用して株価データおよびモックニュースを収集するクラス"""

    def get_stock_data(self, ticker_symbol: str) -> StockData:
        """
        指定銘柄コードの株価データを取得し、25日移動平均線のトレンドおよび前日終値を算出する
        """
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period="60d")

        if df.empty or len(df) < 25:
            raise ValueError(f"銘柄 {ticker_symbol} のデータが十分ではありません（25日以上必要です）。")

        # 25日移動平均線を算出
        ma25 = df["Close"].rolling(window=25).mean()

        latest_close = float(df["Close"].iloc[-1])
        latest_ma25 = float(ma25.iloc[-1])

        # 直近数日間（3日前）と比較してトレンドを判定
        trend: Literal["UPWARD", "FLAT", "DOWNWARD"] = "FLAT"
        if len(ma25.dropna()) >= 4:
            prev_ma25 = float(ma25.iloc[-4])
            if latest_ma25 > prev_ma25 * 1.0005:
                trend = "UPWARD"
            elif latest_ma25 < prev_ma25 * 0.9995:
                trend = "DOWNWARD"

        return StockData(
            ticker_symbol=ticker_symbol,
            latest_close=latest_close,
            ma25_trend=trend,
            ma25_value=latest_ma25,
        )

    def get_mock_news(self, ticker_symbol: str) -> str:
        """
        テスト用のニューステキストを取得するモック関数
        """
        return (
            f"【{ticker_symbol} ニュース速報】"
            f"当期の連結業績予想の上方修正を発表。最新の製品需要が旺盛で営業利益は前期比+25%増となる見通し。"
            f"新事業の展開も順調であり、アナリストからは好意的なコメントが相次いでいる。"
        )
