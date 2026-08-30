import json
from pathlib import Path

import chromadb

from src.rag_store import RagStore


def test_rag_store_add_and_query() -> None:
    """RagStore に取引レコードを追加し、類似検索できることを検証"""
    client = chromadb.EphemeralClient()
    store = RagStore(client=client, collection_name="test_cases_add_query")

    # 2件登録
    store.add_trade_record(
        trade_id="trade-1",
        news_text="通期の連結業績予想の上方修正を発表。営業利益が前期比25%増の大幅増益となる見通し。",
        metadata={
            "ticker_symbol": "7203.T",
            "trade_outcome": "WIN",
            "ai_score": 4.5,
            "final_action": "BUY",
            "catalyst_summary": "営業利益上方修正",
            "risk_factors": "一時的な円安要因の可能性",
            "profit_loss_rate": 0.05,
        },
    )
    store.add_trade_record(
        trade_id="trade-2",
        news_text="不正会計とリコール問題が発覚。巨額の特別損失と減配を発表。",
        metadata={
            "ticker_symbol": "8306.T",
            "trade_outcome": "LOSS",
            "ai_score": 1.5,
            "final_action": "HOLD",
            "catalyst_summary": "リコール発生による特損",
            "risk_factors": "信頼低下と追加コスト",
            "profit_loss_rate": -0.08,
        },
    )

    # 上方修正に関連するクエリで類似検索
    results = store.query_similar_cases("業績予想の上方修正と増益見通し", n_results=1)
    assert len(results) == 1
    assert results[0]["trade_id"] == "trade-1"
    assert results[0]["metadata"]["trade_outcome"] == "WIN"
    assert results[0]["metadata"]["ticker_symbol"] == "7203.T"

    # 不正会計・特損に関連するクエリで類似検索
    loss_results = store.query_similar_cases("不正会計と特別損失のリコール", n_results=1)
    assert len(loss_results) == 1
    assert loss_results[0]["trade_id"] == "trade-2"
    assert loss_results[0]["metadata"]["trade_outcome"] == "LOSS"


def test_rag_store_format_cases_for_prompt() -> None:
    """検索された過去事例がプロンプト用テキストに適切に整形されることを検証"""
    client = chromadb.EphemeralClient()
    store = RagStore(client=client, collection_name="test_cases_format")

    cases = [
        {
            "trade_id": "test-1",
            "document": "第3四半期好決算を発表するも進捗率は織り込み済み。",
            "metadata": {
                "ticker_symbol": "7203.T",
                "trade_outcome": "LOSS",
                "profit_loss_rate": -0.03,
                "final_action": "BUY",
                "ai_score": 4.0,
                "catalyst_summary": "好決算発表",
                "risk_factors": "材料出尽くしの懸念",
                "post_analysis_notes": "材料出尽くしで翌日急落",
            },
            "distance": 0.12,
        }
    ]

    formatted_text = store.format_cases_for_prompt(cases)
    assert "【過去の類似事例（参考ナレッジ）】" in formatted_text
    assert "特に「LOSS（失敗事例）」の傾向に注意" in formatted_text
    assert "銘柄: 7203.T" in formatted_text
    assert "結果: LOSS" in formatted_text
    assert "損益率: -0.03" in formatted_text
    assert "材料出尽くしで翌日急落" in formatted_text


def test_rag_store_sync_from_trade_logs(tmp_path: Path) -> None:
    """JSONLファイルからの同期処理が正しく行われることを検証"""
    dummy_log_file = tmp_path / "trade_logs.jsonl"
    sample_records = [
        {
            "trade_id": "rec-1",
            "date": "2026-08-30",
            "ticker_symbol": "7203.T",
            "news_content": "トヨタ、通期業績予想を大幅に上方修正",
            "ai_score": 4.2,
            "catalyst_summary": "通期業績上方修正",
            "risk_factors": "為替影響",
            "post_analysis_notes": "買い判定",
            "execution_result": {"bought_price": 3000.0, "profit_loss_rate": 0.05},
            "trade_outcome": "WIN",
        },
        {
            "trade_id": "rec-2",
            "date": "2026-08-30",
            "ticker_symbol": "9984.T",
            "ai_score": 3.0,
            "catalyst_summary": "ニュースなし",
            "risk_factors": "外部環境要因",
            "post_analysis_notes": "見送り",
            "execution_result": {"bought_price": None, "profit_loss_rate": None},
            "trade_outcome": None,
        },
    ]

    with open(dummy_log_file, "w", encoding="utf-8") as f:
        for r in sample_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    client = chromadb.EphemeralClient()
    store = RagStore(client=client, collection_name="test_cases_sync")

    count = store.sync_from_trade_logs(str(dummy_log_file))
    assert count == 2
    assert store.collection.count() == 2

    # 検索テスト
    res = store.query_similar_cases("トヨタ、通期業績予想を大幅に上方修正", n_results=1)
    assert len(res) == 1
    assert res[0]["trade_id"] == "rec-1"
