# 03_knowledge_rag.md：取引結果ナレッジ蓄積およびRAG・ファインチューニング運用仕様書

## 1. 概要・目的
本仕様書は、AI（Gemini 2.5 Flash）による売買判定結果および実際の取引結果（損益・自動損切り発動有無）を構造化データとして記録・蓄積し、以下の目的に活用するための仕様を定義する。

1. **取引ナレッジの構造化蓄積:** 日々の判定と決済結果をロギング。
2. **RAG（検索拡張生成）による判定精度向上:** 毎朝のAI判定時に、過去の類似事例（特に失敗パターン）を動的にコンテキストへ挿入し、同じ過ちを防ぐ。
3. **自己反省パイプラインの自動化:** 敗戦トレードの傾向分析とプロンプト改善策の自動抽出。
4. **ファインチューニング用データセットの自動生成:** 将来のモデル学習に向けた高勝率トレードデータの自動集積。

---

## 2. データ構造仕様

### 2.1 ナレッジ保存形式（JSON Lines）
取引ログは `data/trade_logs.jsonl`（またはデータベース）へ追記保存する。

### 2.2 スキーマ定義
```json
{
  "trade_id": "STRING (UUID)",
  "timestamp": "ISO8601 (YYYY-MM-DDTHH:MM:SSZ)",
  "ticker_symbol": "STRING (例: 7203.T)",
  "company_name": "STRING",
  "news_content": "STRING (判定対象となった適時開示・ニュース本文)",
  "ai_prediction": {
    "sentiment_score": "FLOAT (1.0 - 5.0)",
    "action": "BUY | SELL | HOLD",
    "catalyst_summary": "STRING",
    "risk_factors": "STRING",
    "confidence_level": "FLOAT (0.0 - 1.0)"
  },
  "technical_indicators": {
    "ma25_trend": "UPWARD | FLAT | DOWNWARD",
    "entry_price": "NUMBER"
  },
  "execution_result": {
    "bought_price": "NUMBER | null",
    "sold_price": "NUMBER | null",
    "profit_loss_rate": "FLOAT (例: 0.05 = +5%) | null",
    "stop_loss_triggered": "BOOLEAN | null",
    "holding_period_days": "INTEGER | null"
  },
  "trade_outcome": "WIN | LOSS | DRAW | PENDING",
  "post_analysis_notes": "STRING | null"
}

```

※ 発注直後は `execution_result` の各項目および `trade_outcome` は `null` または `"PENDING"` とし、決済完了時に値を更新する。

---

## 3. RAG（類似事例自動参照）仕様

### 3.1 ベクターデータベース構成

* **採用技術 (フェーズ1/2):** Chroma DB / PGvector / Qdrant (Pythonから軽量利用可能なものを推奨)
* **埋め込みモデル (Embedding):** Gemini Text Embedding API (または OpenAI text-embedding-3-small 等)

### 3.2 処理フロー (朝7:00 判定時)

1. **ベクトル化:** 収集した最新ニューステキストをベクトル変換する。
2. **コサイン類似度検索:** 過去の `trade_logs` から、ニュース内容が類似している取引ログの上位 $k$ 件（例: 3件）を検索取得する。
3. **プロンプトへの注入 (Augmentation):** 検索された過去事例をプロンプトのコンテキスト領域に含めて Gemini 2.5 Flash に送信する。

### 3.3 動的プロンプト構造例

```text
【役割】
あなたは株式スイングトレードのプロアナリストです。

【最新ニュース】
{current_news_text}

【過去の類似事例（参考ナレッジ）】
以下は過去に類似したニュースがあった際のAI判定と実際の取引結果です。特に「LOSS（失敗事例）」の傾向に注意してください。
---
事例1: [結果: LOSS / 損切り発動]
- ニュース要約: 第3四半期好決算を発表するも進捗率は織り込み済み。
- AI判定理由: 営業利益前年比+20%を過大評価。
- 結果: 材料出尽くしで翌日暴落。

事例2: [結果: WIN]
...
---

【指示】
過去の類似事例における失敗パターン（材料出尽くし、一過性要因など）を踏まえた上で、最新ニュースのインパクトとリスクを評価し、指定のJSONスキーマで出力してください。

```

---

## 4. 自動化パイプライン仕様

### 4.1 RAGナレッジ自動更新パイプライン

1. 決済処理完了イベントを検知。
2. `trade_outcome`（WIN/LOSS）および `profit_loss_rate` を確定。
3. 取引ログとニューステキストをベクターDBへ自動登録（インデックス更新）。

### 4.2 自己反省・傾向分析パイプライン（定期バッチ）

* **実行周期:** 週1回（週末）または月1回
* **処理内容:**
1. 期間内の `trade_outcome == "LOSS"` のログを抽出。
2. Gemini API へ投げて「AIが誤判別しやすいニュースの傾向」と「プロンプト改善案」の分析レポートを自動生成。
3. 分析レポートを `docs/feedback_reports/` 配下に保存し、人間に通知。



### 4.3 ファインチューニング用データ生成パイプライン

* **フィルタ条件:** `trade_outcome == "WIN"` かつ `profit_loss_rate >= 0.03 (+3%以上)`
* **出力形式:** Gemini ファインチューニング用 JSONLines (`data/ft_dataset.jsonl`)
* **JSONL形式例:**
```json
{"messages": [{"role": "user", "content": "ニュース: ..."}, {"role": "model", "content": "{\"sentiment_score\": 4.5, \"action\": \"BUY\", ...}"}]}

```



---

## 5. Antigravity 実装時のガイドライン

Antigravity でモジュールを実装する際は、以下の構成に従ってコードを分離・作成すること。

* **`src/knowledge/logger.py`**: 取引ログの保存・更新・JSONL形式出力
* **`src/knowledge/vector_store.py`**: ベクターDBへの登録・類似検索処理
* **`src/knowledge/rag_prompt.py`**: 類似事例を取り入れた動的プロンプト生成
* **`src/knowledge/exporter.py`**: ファインチューニング用データ（JSONL）自動出力処理

```
