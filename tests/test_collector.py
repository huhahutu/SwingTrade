from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.collector import StockData, StockDataCollector, fetch_latest_news


def create_mock_df(prices: list[float]) -> pd.DataFrame:
    """テスト用の株価DataFrameを生成するヘルパー関数"""
    dates = pd.date_range(end=pd.Timestamp.now(), periods=len(prices), freq="D")
    df = pd.DataFrame({"Close": prices}, index=dates)
    return df


def test_get_stock_data_upward_trend(mocker: pytest.MonkeyPatch) -> None:
    """MA25が上向き（UPWARD）の場合のテスト"""
    # 25日以上の上昇トレンド株価データ (例: 30日分)
    prices = [100.0 + i * 2.0 for i in range(30)]
    mock_df = create_mock_df(prices)

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = mock_df
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)  # type: ignore[attr-defined]

    collector = StockDataCollector()
    data: StockData = collector.get_stock_data("7203.T")

    assert data.ticker_symbol == "7203.T"
    assert data.latest_close == prices[-1]
    assert data.ma25_trend == "UPWARD"
    assert data.ma25_value is not None


def test_get_stock_data_downward_trend(mocker: pytest.MonkeyPatch) -> None:
    """MA25が下向き（DOWNWARD）の場合のテスト"""
    prices = [200.0 - i * 2.0 for i in range(30)]
    mock_df = create_mock_df(prices)

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = mock_df
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)  # type: ignore[attr-defined]

    collector = StockDataCollector()
    data: StockData = collector.get_stock_data("7203.T")

    assert data.ma25_trend == "DOWNWARD"


def test_get_mock_news() -> None:
    """モックニューステキスト取得機能のテスト"""
    collector = StockDataCollector()
    news = collector.get_mock_news("7203.T")
    assert isinstance(news, str)
    assert len(news) > 0


@pytest.fixture
def mock_tdnet_rss_feed() -> dict[str, list[dict[str, str]]]:
    """TDnet RSSフィードのモックデータを返すフィクスチャ"""
    return {
        "entries": [
            {
                "title": "【7203】トヨタ自動車：通期連結業績予想の修正に関するお知らせ",
                "summary": (
                    "当期の連結業績予想を上方修正しました。営業利益は前年同期比+15%を見込みます。"
                ),
                "link": "https://www.release.tdnet.info/inbs/140120260830123456.pdf",
                "published": "Sun, 30 Aug 2026 15:00:00 +0900",
            },
            {
                "title": "【6758】ソニーグループ：新製品の発売に関するお知らせ",
                "summary": (
                    "次世代センサーの量産出荷を本年度第3四半期より開始することを決定いたしました。"
                ),
                "link": "https://www.release.tdnet.info/inbs/140120260830987654.pdf",
                "published": "Sun, 30 Aug 2026 14:30:00 +0900",
            },
        ]
    }


def test_fetch_latest_news_success_with_ticker_suffix(
    mocker: pytest.MonkeyPatch, mock_tdnet_rss_feed: dict[str, list[dict[str, str]]]
) -> None:
    """正常系: '7203.T' 形式で指定した場合に該当銘柄のニュースが正しく抽出されること"""
    mock_parse = mocker.patch("feedparser.parse")  # type: ignore[attr-defined]
    mock_parse.return_value = MagicMock(**mock_tdnet_rss_feed)

    news_list = fetch_latest_news("7203.T")

    assert len(news_list) == 1
    assert "7203" in news_list[0]["title"]
    assert "上方修正" in news_list[0]["summary"]
    assert news_list[0]["url"] == "https://www.release.tdnet.info/inbs/140120260830123456.pdf"


def test_fetch_latest_news_success_with_pure_code(
    mocker: pytest.MonkeyPatch, mock_tdnet_rss_feed: dict[str, list[dict[str, str]]]
) -> None:
    """正常系: '7203'（数字のみ）形式で指定した場合も抽出できること"""
    mock_parse = mocker.patch("feedparser.parse")  # type: ignore[attr-defined]
    mock_parse.return_value = MagicMock(**mock_tdnet_rss_feed)

    news_list = fetch_latest_news("7203")

    assert len(news_list) == 1
    assert "7203" in news_list[0]["title"]


def test_fetch_latest_news_not_found(
    mocker: pytest.MonkeyPatch, mock_tdnet_rss_feed: dict[str, list[dict[str, str]]]
) -> None:
    """正常系: 該当銘柄（例: '9984'）のニュースが存在しない場合は空リストを返すこと"""
    mock_parse = mocker.patch("feedparser.parse")  # type: ignore[attr-defined]
    mock_parse.return_value = MagicMock(**mock_tdnet_rss_feed)

    news_list = fetch_latest_news("9984.T")

    assert news_list == []


def test_fetch_latest_news_empty_or_error_feed(mocker: pytest.MonkeyPatch) -> None:
    """異常系・境界値: RSSフィードが空または取得失敗時に例外にならず空リストを返すこと"""
    mock_parse = mocker.patch("feedparser.parse")  # type: ignore[attr-defined]
    mock_parse.return_value = MagicMock(entries=[])

    news_list = fetch_latest_news("7203.T")

    assert news_list == []
