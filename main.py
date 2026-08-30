import argparse
import json
import sys
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.analyzer import SentimentAnalyzer
from src.collector import StockDataCollector, fetch_latest_news
from src.decision import TradeDecisionMaker
from src.logger import KnowledgeLogger

# .env ファイルから環境変数をロード
load_dotenv()

DEFAULT_TICKERS = ["7203.T", "8306.T", "9984.T"]


def run_pipeline(
    ticker_symbol: str = "7203.T",
    api_key: str | None = None,
    log_file_path: str = "data/trade_logs.jsonl",
) -> dict[str, Any]:
    """
    スイングトレード自動判定パイプラインを一連で実行する

    1. 株価データ・テクニカル指標(MA25)および最新適時開示ニュースの取得
    2. Gemini によるAIセンチメント解析
    3. テクニカル×AIスコアによる複合取引判定
    4. ナレッジログ(JSON Lines)の保存と結果出力
    """
    print("=" * 60)
    print(f"[1/4] 株価データおよび最新ニュースの取得開始... (銘柄: {ticker_symbol})")
    collector = StockDataCollector()
    stock_data = collector.get_stock_data(ticker_symbol)

    # TDnet RSSから最新ニュースを自動収集
    news_items = fetch_latest_news(ticker_symbol)
    if news_items:
        formatted_news = []
        for item in news_items:
            formatted_news.append(f"【見出し】{item['title']}\n【要約】{item['summary']}")
        news_text = "\n\n".join(formatted_news)
        print(f"      - 最新適時開示ニュース {len(news_items)} 件を取得しました。")
    else:
        news_text = f"【{ticker_symbol}】直近の新規適時開示ニュースはありません。"
        print("      - 直近の適時開示ニュースはありません。")

    print(f"      - 最新終値: {stock_data.latest_close:.2f}円")
    print(f"      - MA25トレンド: {stock_data.ma25_trend} (MA25値: {stock_data.ma25_value:.2f}円)")

    print("\n[2/4] Gemini によるニュースセンチメント解析実行中...")
    analyzer = SentimentAnalyzer(api_key=api_key)
    sentiment_result = analyzer.analyze_news(ticker_symbol, news_text)

    print(f"      - AI センチメントスコア: {sentiment_result.sentiment_score} (1.0-5.0)")
    print(f"      - AI 推薦アクション: {sentiment_result.action}")
    print(f"      - AI 確信度: {sentiment_result.confidence_level}")
    print(f"      - 触媒要約: {sentiment_result.catalyst_summary}")
    print(f"      - リスク要因: {sentiment_result.risk_factors}")

    print("\n[3/4] 複合売買ルールの判定処理...")
    decision_maker = TradeDecisionMaker()
    decision_result = decision_maker.make_decision(stock_data, sentiment_result)

    print(f"      - 最終決定アクション: === {decision_result.final_action} ===")
    print(f"      - 判定理由: {decision_result.reason}")

    print(f"\n[4/4] ナレッジログの追記保存 (保存先: {log_file_path})...")
    logger = KnowledgeLogger(file_path=log_file_path)
    log_record = logger.log_trade_decision(stock_data, sentiment_result, decision_result)

    print("=" * 60)
    print(f"[{ticker_symbol}] パイプライン完了。生成されたログレコード概要:")
    print(json.dumps(log_record, indent=2, ensure_ascii=False))
    print("=" * 60)

    return log_record


def run_batch_pipeline(
    tickers: list[str] | None = None,
    api_key: str | None = None,
    log_file_path: str = "data/trade_logs.jsonl",
) -> list[dict[str, Any]]:
    """複数銘柄に対してパイプラインを一括実行する"""
    target_tickers = tickers or DEFAULT_TICKERS
    results: list[dict[str, Any]] = []
    for ticker in target_tickers:
        print(f"\n>>> 銘柄 {ticker} の処理を開始します...")
        try:
            result = run_pipeline(
                ticker_symbol=ticker,
                api_key=api_key,
                log_file_path=log_file_path,
            )
            results.append(result)
        except Exception as e:
            print(f"銘柄 {ticker} の処理中にエラーが発生しました: {e}", file=sys.stderr)
    return results


app = FastAPI(
    title="SwingTrade API",
    description="スイングトレード自動売買システム - プロトタイプ (Phase 2: Dapr統合)",
    version="0.2.0",
)


class TradeRequest(BaseModel):
    ticker: str = "7203.T"
    log_file: str = "data/trade_logs.jsonl"


@app.post("/trade")
def trade_endpoint(request: TradeRequest) -> dict[str, Any]:
    """API経由でスイングトレード自動判定パイプラインを実行する"""
    try:
        result = run_pipeline(ticker_symbol=request.ticker, log_file_path=request.log_file)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def main() -> None:
    parser = argparse.ArgumentParser(
        description="スイングトレード自動売買システム - プロトタイプ (Phase 2)"
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="対象銘柄コード (例: 7203.T)。指定なしの場合はデフォルト複数銘柄を一括処理",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="data/trade_logs.jsonl",
        help="ログ出力先ファイルパス",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="FastAPI サーバーを起動する",
    )
    args = parser.parse_args()

    if args.api:
        print("Starting FastAPI server on port 8000...")
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    else:
        try:
            if args.ticker:
                run_pipeline(ticker_symbol=args.ticker, log_file_path=args.log_file)
            else:
                run_batch_pipeline(log_file_path=args.log_file)
        except Exception as e:
            print(f"\n[エラーが発生しました]: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
