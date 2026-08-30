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
from src.rag_store import RagStore

# .env ファイルから環境変数をロード
load_dotenv()

DEFAULT_TICKERS = ["7203.T", "8306.T", "9984.T"]


def run_pipeline(
    ticker_symbol: str = "7203.T",
    api_key: str | None = None,
    log_file_path: str = "data/trade_logs.jsonl",
    chroma_dir: str = "data/chroma_db",
) -> dict[str, Any]:
    """
    スイングトレード自動判定パイプラインを一連で実行する

    1. 株価データ・テクニカル指標(MA25)および最新適時開示ニュースの取得
    2. Chroma DB から類似する過去事例を検索 (RAG Retrieval)
    3. Gemini によるAIセンチメント解析 (動的 RAG コンテキスト注入)
    4. テクニカル×AIスコアによる複合取引判定
    5. ナレッジログ(JSON Lines)の保存および Chroma DB への自動登録
    """
    print("=" * 60)
    print(f"[1/5] 株価データおよび最新ニュースの取得開始... (銘柄: {ticker_symbol})")
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

    print("\n[2/5] Chroma DB による過去類似事例の検索 (RAG Retrieval)...")
    rag_store = RagStore(persist_directory=chroma_dir)
    # 既存ログが存在するがコレクションが空の場合に自動同期
    if rag_store.collection.count() == 0:
        rag_store.sync_from_trade_logs(log_file_path)

    similar_cases = rag_store.query_similar_cases(news_text, n_results=3)
    rag_context = rag_store.format_cases_for_prompt(similar_cases)
    if similar_cases:
        print(f"      - 類似過去事例 {len(similar_cases)} 件を取得しプロンプトへ注入します。")
    else:
        print("      - 該当する過去事例はありません（初期状態）。")

    print("\n[3/5] Gemini によるニュースセンチメント解析実行中 (RAG動的コンテキスト適用)...")
    analyzer = SentimentAnalyzer(api_key=api_key)
    sentiment_result = analyzer.analyze_news(
        ticker_symbol=ticker_symbol,
        news_text=news_text,
        rag_context=rag_context if rag_context else None,
    )

    print(f"      - AI センチメントスコア: {sentiment_result.sentiment_score} (1.0-5.0)")
    print(f"      - AI 推薦アクション: {sentiment_result.action}")
    print(f"      - AI 確信度: {sentiment_result.confidence_level}")
    print(f"      - 触媒要約: {sentiment_result.catalyst_summary}")
    print(f"      - リスク要因: {sentiment_result.risk_factors}")

    print("\n[4/5] 複合売買ルールの判定処理...")
    decision_maker = TradeDecisionMaker()
    decision_result = decision_maker.make_decision(stock_data, sentiment_result)

    print(f"      - 最終決定アクション: === {decision_result.final_action} ===")
    print(f"      - 判定理由: {decision_result.reason}")

    print(f"\n[5/5] ナレッジログの追記保存および Chroma DB 登録 (保存先: {log_file_path})...")
    logger = KnowledgeLogger(file_path=log_file_path)
    log_record = logger.log_trade_decision(
        stock_data,
        sentiment_result,
        decision_result,
        news_content=news_text,
    )

    # Chroma DB に今回の判定結果を登録
    rag_store.add_trade_record(
        trade_id=log_record["trade_id"],
        news_text=news_text,
        metadata={
            "ticker_symbol": stock_data.ticker_symbol,
            "date": log_record["date"],
            "ai_score": sentiment_result.sentiment_score,
            "final_action": decision_result.final_action,
            "catalyst_summary": sentiment_result.catalyst_summary,
            "risk_factors": sentiment_result.risk_factors,
            "post_analysis_notes": log_record["post_analysis_notes"],
            "trade_outcome": "",
        },
    )

    print("=" * 60)
    print(f"[{ticker_symbol}] パイプライン完了。生成されたログレコード概要:")
    print(json.dumps(log_record, indent=2, ensure_ascii=False))
    print("=" * 60)

    return log_record


def run_batch_pipeline(
    tickers: list[str] | None = None,
    api_key: str | None = None,
    log_file_path: str = "data/trade_logs.jsonl",
    chroma_dir: str = "data/chroma_db",
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
                chroma_dir=chroma_dir,
            )
            results.append(result)
        except Exception as e:
            print(f"銘柄 {ticker} の処理中にエラーが発生しました: {e}", file=sys.stderr)
    return results


app = FastAPI(
    title="SwingTrade API",
    description="スイングトレード自動売買システム - プロトタイプ (Phase 2: RAG / Dapr統合)",
    version="0.2.0",
)


class TradeRequest(BaseModel):
    ticker: str = "7203.T"
    log_file: str = "data/trade_logs.jsonl"
    chroma_dir: str = "data/chroma_db"


@app.post("/trade")
def trade_endpoint(request: TradeRequest) -> dict[str, Any]:
    """API経由でスイングトレード自動判定パイプラインを実行する"""
    try:
        result = run_pipeline(
            ticker_symbol=request.ticker,
            log_file_path=request.log_file,
            chroma_dir=request.chroma_dir,
        )
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def main() -> None:
    parser = argparse.ArgumentParser(
        description="スイングトレード自動売買システム - プロトタイプ (Phase 2: RAG)"
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
        "--chroma-dir",
        type=str,
        default="data/chroma_db",
        help="Chroma DB 永続化ディレクトリ",
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
                run_pipeline(
                    ticker_symbol=args.ticker,
                    log_file_path=args.log_file,
                    chroma_dir=args.chroma_dir,
                )
            else:
                run_batch_pipeline(
                    log_file_path=args.log_file,
                    chroma_dir=args.chroma_dir,
                )
        except Exception as e:
            print(f"\n[エラーが発生しました]: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
