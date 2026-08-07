import argparse
import json
import os
import sys
from dotenv import load_dotenv

from src.collector import StockDataCollector
from src.analyzer import SentimentAnalyzer
from src.decision import TradeDecisionMaker
from src.logger import KnowledgeLogger

# .env ファイルから環境変数をロード
load_dotenv()


def run_pipeline(
    ticker_symbol: str = "7203.T",
    api_key: str | None = None,
    log_file_path: str = "data/trade_logs.jsonl",
) -> dict:
    """
    スイングトレード自動判定パイプラインを一連で実行する

    1. 株価データ・テクニカル指標(MA25)およびニュースモックの取得
    2. Gemini 2.5 Flash によるAIセンチメント解析
    3. テクニカル×AIスコアによる複合取引判定
    4. ナレッジログ(JSON Lines)の保存と結果出力
    """
    print("=" * 60)
    print(f"[1/4] 株価データおよびテクニカル指標の取得開始... (銘柄: {ticker_symbol})")
    collector = StockDataCollector()
    stock_data = collector.get_stock_data(ticker_symbol)
    news_text = collector.get_mock_news(ticker_symbol)

    print(f"      - 最新終値: {stock_data.latest_close:.2f}円")
    print(f"      - MA25トレンド: {stock_data.ma25_trend} (MA25値: {stock_data.ma25_value:.2f}円)")

    print(f"\n[2/4] Gemini 2.5 Flash によるニュースセンチメント解析実行中...")
    analyzer = SentimentAnalyzer(api_key=api_key)
    sentiment_result = analyzer.analyze_news(ticker_symbol, news_text)

    print(f"      - AI センチメントスコア: {sentiment_result.sentiment_score} (1.0-5.0)")
    print(f"      - AI 推薦アクション: {sentiment_result.action}")
    print(f"      - AI 確信度: {sentiment_result.confidence_level}")
    print(f"      - 触媒要約: {sentiment_result.catalyst_summary}")
    print(f"      - リスク要因: {sentiment_result.risk_factors}")

    print(f"\n[3/4] 複合売買ルールの判定処理...")
    decision_maker = TradeDecisionMaker()
    decision_result = decision_maker.make_decision(stock_data, sentiment_result)

    print(f"      - 最終決定アクション: === {decision_result.final_action} ===")
    print(f"      - 判定理由: {decision_result.reason}")

    print(f"\n[4/4] ナレッジログの追記保存 (保存先: {log_file_path})...")
    logger = KnowledgeLogger(file_path=log_file_path)
    log_record = logger.log_trade_decision(stock_data, sentiment_result, decision_result)

    print("=" * 60)
    print("パイプライン完了。生成されたログレコード概要:")
    print(json.dumps(log_record, indent=2, ensure_ascii=False))
    print("=" * 60)

    return log_record


def main() -> None:
    parser = argparse.ArgumentParser(
        description="スイングトレード自動売買システム - プロトタイプ (Phase 1)"
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default="7203.T",
        help="対象銘柄コード (例: 7203.T)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="data/trade_logs.jsonl",
        help="ログ出力先ファイルパス",
    )
    args = parser.parse_args()

    try:
        run_pipeline(ticker_symbol=args.ticker, log_file_path=args.log_file)
    except Exception as e:
        print(f"\n[エラーが発生しました]: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
