import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from src.collector import StockDataCollector, StockData


def create_mock_df(prices: list[float]) -> pd.DataFrame:
    """テスト用の株価DataFrameを生成するヘルパー関数"""
    dates = pd.date_range(end=pd.Timestamp.now(), periods=len(prices), freq="D")
    df = pd.DataFrame({"Close": prices}, index=dates)
    return df


def test_get_stock_data_upward_trend(mocker):
    """MA25が上向き（UPWARD）の場合のテスト"""
    # 25日以上の上昇トレンド株価データ (例: 30日分)
    prices = [100.0 + i * 2.0 for i in range(30)]
    mock_df = create_mock_df(prices)

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = mock_df
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    collector = StockDataCollector()
    data: StockData = collector.get_stock_data("7203.T")

    assert data.ticker_symbol == "7203.T"
    assert data.latest_close == prices[-1]
    assert data.ma25_trend == "UPWARD"
    assert data.ma25_value is not None


def test_get_stock_data_downward_trend(mocker):
    """MA25が下向き（DOWNWARD）の場合のテスト"""
    prices = [200.0 - i * 2.0 for i in range(30)]
    mock_df = create_mock_df(prices)

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = mock_df
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    collector = StockDataCollector()
    data: StockData = collector.get_stock_data("7203.T")

    assert data.ma25_trend == "DOWNWARD"


def test_get_mock_news():
    """モックニューステキスト取得機能のテスト"""
    collector = StockDataCollector()
    news = collector.get_mock_news("7203.T")
    assert isinstance(news, str)
    assert len(news) > 0
