---

# 要件定義書：フェーズ3 - ファインチューニング用データの自動選別・蓄積

## 1. 目的・概要

取引の決済完了（評価）時、基準を満たす「成功事例（WINトレード）」を自動検知し、Gemini APIのファインチューニング用データセット（JSONLines形式）として抽出・追加保存するパイプラインを構築します。

これにより、手動で教師データを作成することなく、運用ログから高品質なデータセット（`data/finetune_dataset.jsonl`）を自動的に蓄積します。

---

## 2. 実装機能要件

### ① 成功トレードの自動フィルタリング (Filtering)

* **実行タイミング**: `TradeEvaluator` による決済評価（WIN/LOSS確定）時。


* **抽出基準**:
* `trade_outcome == "WIN"`（勝ちトレード）


* かつ `profit_loss_rate >= 0.02`（損益率が+2.0%以上の優良取引）




* **目的**: 一時的な誤差によるプラス取引を除外し、AIが真に模倣すべき勝ちパターンのみを学習データに含めるため。



### ② Gemini ファインチューニング用フォーマット（JSONL）への変換

* **フォーマット仕様**: Gemini API / Vertex AI のファインチューニング形式（System / User / Model メッセージ構成）に準拠させる。
* **データ構造例**:
```json
{
  "messages": [
    {
      "role": "system",
      "content": "あなたは株価センチメントアナリストです。ニュース本文とテクニカル指標に基づき、短期的な株価カタリストを評価してJSONで出力してください。"
    },
    {
      "role": "user",
      "content": "【銘柄】: 7203.T\n【移動平均線】: UPWARD\n【ニュース本文】: ..."
    },
    {
      "role": "model",
      "content": "{\"ticker_symbol\": \"7203.T\", \"sentiment_score\": 4.5, \"action\": \"BUY\", \"catalyst_summary\": \"...\", \"risk_factors\": \"...\", \"confidence_level\": 0.85}"
    }
  ]
}

```



### ③ データ蓄積モジュール (`DatasetGenerator` / `src/dataset_generator.py`)

* 抽出した教師データを `data/finetune_dataset.jsonl` に追記保存（Append）する。


* 重複登録を防止するため、`trade_id` による重複チェックを実装する。

---

## 3. 品質・コーディング規約

* すべての新規関数・クラスには厳格な Type Hinting を記述する。


* Ruff（Formatter / Linter）および mypy（Strictモード）の解析結果に一切エラーを出さないコードを出力すること。



---