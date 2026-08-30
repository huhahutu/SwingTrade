import json
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection


class RagStore:
    """
    Chroma DB を利用してニュース本文および取引ログをベクトル化して蓄積・類似検索するクラス
    """

    def __init__(
        self,
        persist_directory: str | None = "data/chroma_db",
        collection_name: str = "trade_cases",
        client: Any | None = None,
        embedding_function: Any | None = None,
    ) -> None:
        if client is not None:
            self.client = client
        elif persist_directory is not None:
            Path(persist_directory).mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            self.client = chromadb.EphemeralClient()

        kwargs: dict[str, Any] = {
            "name": collection_name,
            "metadata": {"hnsw:space": "cosine"},
        }
        if embedding_function is not None:
            kwargs["embedding_function"] = embedding_function

        self.collection: Collection = self.client.get_or_create_collection(**kwargs)

    def add_trade_record(
        self,
        trade_id: str,
        news_text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        取引ログおよびニュース本文をコレクションに登録または更新する
        """
        cleaned_metadata: dict[str, str | int | float | bool] = {}
        if metadata:
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    cleaned_metadata[k] = v
                elif v is None:
                    cleaned_metadata[k] = ""
                else:
                    cleaned_metadata[k] = str(v)

        doc_text = news_text.strip() if news_text and news_text.strip() else "ニュースなし"

        self.collection.upsert(
            ids=[trade_id],
            documents=[doc_text],
            metadatas=[cleaned_metadata],
        )

    def query_similar_cases(
        self,
        query_text: str,
        n_results: int = 3,
        outcome_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        最新ニュースと類似する過去事例を Chroma DB から上位n件検索する
        """
        if not query_text or not query_text.strip():
            return []

        total_count = self.collection.count()
        if total_count == 0:
            return []

        actual_n = min(n_results, total_count)
        where_clause: dict[str, Any] | None = None
        if outcome_filter:
            where_clause = {"trade_outcome": outcome_filter}

        results = self.collection.query(
            query_texts=[query_text],
            n_results=actual_n,
            where=where_clause,
            include=["documents", "metadatas", "distances"],
        )

        similar_cases: list[dict[str, Any]] = []
        ids_data = results.get("ids")
        docs_data = results.get("documents")
        meta_data = results.get("metadatas")
        dist_data = results.get("distances")

        if ids_data and docs_data and meta_data:
            ids = ids_data[0]
            docs = docs_data[0]
            metadatas = meta_data[0]
            distances = dist_data[0] if dist_data else [0.0] * len(ids)

            for trade_id, doc, meta, dist in zip(ids, docs, metadatas, distances, strict=False):
                similar_cases.append(
                    {
                        "trade_id": trade_id,
                        "document": doc,
                        "metadata": meta,
                        "distance": float(dist),
                    }
                )

        return similar_cases

    def format_cases_for_prompt(self, cases: list[dict[str, Any]]) -> str:
        """
        検索された過去事例を Gemini プロンプト向けのコンテキストテキストに整形する
        """
        if not cases:
            return ""

        formatted_lines = [
            "【過去の類似事例（参考ナレッジ）】",
            "以下は過去に類似したニュースがあった際のAI判定と実際の取引結果です。特に「LOSS（失敗事例）」の傾向に注意してください。",
            "---",
        ]

        for i, case in enumerate(cases, 1):
            meta = case.get("metadata", {})
            outcome = meta.get("trade_outcome") or "PENDING"
            ticker = meta.get("ticker_symbol", "N/A")
            ai_score = meta.get("ai_score", "N/A")
            catalyst = meta.get("catalyst_summary", "")
            risk = meta.get("risk_factors", "")
            action = meta.get("final_action", meta.get("action", "HOLD"))
            post_notes = meta.get("post_analysis_notes", "")
            profit_loss = meta.get("profit_loss_rate", "")

            profit_loss_str = f" / 損益率: {profit_loss}" if profit_loss != "" else ""

            formatted_lines.append(
                f"事例{i}: [銘柄: {ticker} / 結果: {outcome}{profit_loss_str} / 最終判定: {action}]"
            )
            if catalyst:
                formatted_lines.append(f"- 材料・触媒: {catalyst}")
            if risk:
                formatted_lines.append(f"- 懸念要因: {risk}")
            if ai_score != "N/A":
                formatted_lines.append(f"- AIスコア: {ai_score}")
            if post_notes:
                formatted_lines.append(f"- 事後分析・判定理由: {post_notes}")

            doc_snippet = str(case.get("document", ""))[:200]
            if doc_snippet and doc_snippet != "ニュースなし":
                formatted_lines.append(f"- ニュース抜粋: {doc_snippet}")
            formatted_lines.append("")

        formatted_lines.append("---")
        return "\n".join(formatted_lines)

    def sync_from_trade_logs(self, jsonl_path: str = "data/trade_logs.jsonl") -> int:
        """
        JSONL形式の取引ログファイルを読み込み、Chroma DBに一括登録・更新する
        """
        file_path = Path(jsonl_path)
        if not file_path.exists():
            return 0

        imported_count = 0
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    record: dict[str, Any] = json.loads(line_str)
                except json.JSONDecodeError:
                    continue

                trade_id = record.get("trade_id")
                if not trade_id:
                    continue

                # ニューステキスト抽出（優先度: news_content > catalyst > reason）
                news_text = record.get("news_content") or ""
                if not news_text:
                    catalyst = record.get("catalyst_summary") or ""
                    action_reason = record.get("ai_action_reason") or ""
                    news_text = f"{catalyst} {action_reason}".strip()

                metadata: dict[str, Any] = {
                    "ticker_symbol": record.get("ticker_symbol", ""),
                    "date": record.get("date", ""),
                    "trade_outcome": record.get("trade_outcome") or "",
                    "ai_score": float(record.get("ai_score", 0.0)),
                    "catalyst_summary": record.get("catalyst_summary", ""),
                    "risk_factors": record.get("risk_factors", ""),
                    "post_analysis_notes": record.get("post_analysis_notes", ""),
                }

                exec_result = record.get("execution_result", {})
                if isinstance(exec_result, dict):
                    if exec_result.get("profit_loss_rate") is not None:
                        metadata["profit_loss_rate"] = float(exec_result["profit_loss_rate"])
                    if exec_result.get("bought_price") is not None:
                        metadata["bought_price"] = float(exec_result["bought_price"])

                self.add_trade_record(
                    trade_id=trade_id,
                    news_text=news_text,
                    metadata=metadata,
                )
                imported_count += 1

        return imported_count
