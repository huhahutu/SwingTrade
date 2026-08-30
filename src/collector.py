from dataclasses import dataclass
from typing import Literal

import feedparser
import yfinance as yf

TDNET_RSS_DEFAULT_URL = "https://www.release.tdnet.info/rss/TDnet_all.xml"


def fetch_latest_news(
    ticker_symbol: str,
    feed_url: str | None = None,
    max_items: int = 5,
) -> list[dict[str, str]]:
    """
    指定された銘柄コードに関連する最新の適時開示ニュースをRSSフィードから取得・抽出する。

    Args:
        ticker_symbol: 銘柄コード（例: "7203.T", "7203"）
        feed_url: 参照先RSSフィードURL（デフォルト: TDnet適時開示RSS）
        max_items: 取得する最大件数

    Returns:
        ニュース情報の辞書リスト
    """
    url = feed_url or TDNET_RSS_DEFAULT_URL
    code = ticker_symbol.replace(".T", "").strip()

    try:
        feed = feedparser.parse(url)
        entries = getattr(feed, "entries", [])
        if not entries:
            return []

        matched_items: list[dict[str, str]] = []
        for entry in entries:
            title = str(
                entry.get("title", "") if isinstance(entry, dict) else getattr(entry, "title", "")
            )
            summary = str(
                entry.get("summary", "")
                if isinstance(entry, dict)
                else getattr(entry, "summary", "")
            )
            link = str(
                entry.get("link", "") if isinstance(entry, dict) else getattr(entry, "link", "")
            )
            published = str(
                entry.get("published", "")
                if isinstance(entry, dict)
                else getattr(entry, "published", "")
            )

            # 銘柄コードがタイトルまたはサマリーに含まれているかを判定
            if code in title or code in summary:
                matched_items.append(
                    {
                        "title": title,
                        "summary": summary,
                        "url": link,
                        "published": published,
                    }
                )
                if len(matched_items) >= max_items:
                    break

        return matched_items
    except Exception:
        return []


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
            raise ValueError(
                f"銘柄 {ticker_symbol} のデータが十分ではありません（25日以上必要です）。"
            )

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

    def get_latest_news(
        self,
        ticker_symbol: str,
        feed_url: str | None = None,
        max_items: int = 5,
    ) -> list[dict[str, str]]:
        """
        指定銘柄コードの最新ニュースを取得する
        """
        return fetch_latest_news(ticker_symbol, feed_url=feed_url, max_items=max_items)
