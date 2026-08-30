# Dapr 動作確認ガイド (Dapr Verification Guide)

本ドキュメントでは、本プロジェクトにおける **Dapr (Distributed Application Runtime)** の環境構築、起動手順、および各コンポーネント（State Store, Secret Store, Service Invocation 等）の動作確認コマンドをまとめます。

---

## 1. 事前準備 (Prerequisites)

### 1.1 Docker Desktop の起動
Dapr のデフォルトコンテナ（Redis, Zipkin, Placement 等）を利用するため、**Docker Desktop** を起動しておきます。

```powershell
# Docker の起動確認
docker ps
```

### 1.2 Dapr の初期化
初回セットアップ時、またはコンテナが未作成の場合は初期化を実行します。

```powershell
# 初期化済みのバイナリと競合する場合は一度アンインストール
dapr uninstall

# Docker コンテナを含めて再初期化
dapr init
```

`docker ps` を実行し、以下のコンテナが起動していることを確認します。
- `dapr_redis` (ポート: `6379`)
- `dapr_placement` (ポート: `6050`, `50005`)
- `dapr_zipkin` (ポート: `9411`)
- `dapr_scheduler` (ポート: `50006`)

---

## 2. アプリケーションと Dapr Sidecar の起動

必ず **プロジェクトルートディレクトリ (`SwingTrade/`)** で実行してください。

```powershell
cd c:\Users\Kiyoshi\Src\SwingTrade

# Dapr Sidecar と FastAPI アプリケーションを同時起動
dapr run --app-id trading-service --app-port 8000 --dapr-http-port 3500 --resources-path ./components -- python -m uvicorn main:app --port 8000
```

> **注意 (Note)**:
> `src/` などのサブディレクトリで `--resources-path ./components` を実行するとパスが見つからずエラーとなります。必ずプロジェクトルートから実行するか、適切な相対パスを指定してください。

---

## 3. 基本動作・ヘルスチェックの確認

別のターミナルを開き、以下のコマンドで動作状態を確認します。

### 3.1 Dapr インスタンス一覧
```powershell
dapr list
```
* `trading-service` が `HTTP PORT: 3500`, `APP PORT: 8000` で表示されていれば正常です。

### 3.2 Dapr Sidecar ヘルスチェック
```powershell
# PowerShell
Invoke-RestMethod -Uri "http://localhost:3500/v1.0/healthz"

# curl (HTTP 204 No Content が返れば正常)
curl.exe -i http://localhost:3500/v1.0/healthz
```

---

## 4. コンポーネント別の動作確認

### 4.1 シークレットストア (Secret Store)
`components/secretstore.yaml` に定義された `local-secret-store`（環境変数）からシークレットを取得します。

```powershell
# GEMINI_API_KEY の取得テスト
Invoke-RestMethod -Uri "http://localhost:3500/v1.0/secrets/local-secret-store/GEMINI_API_KEY"
```

* **期待されるレスポンス**:
  ```json
  {
    "GEMINI_API_KEY": "AIzaSy..."
  }
  ```

> **注意**:
> ストア名は `localsecretstore` ではなく、ハイフン付きの `local-secret-store` です。

---

### 4.2 ステートストア (State Store / Redis)
`components/statestore.yaml` に定義された `statestore` (Redis) に対する CRUD 操作を確認します。

#### ① データの保存 (POST)
```powershell
$body = '[{ "key": "test_order_status", "value": { "status": "PENDING", "symbol": "7203.T" }}]'
Invoke-RestMethod -Uri "http://localhost:3500/v1.0/state/statestore" -Method Post -Body $body -ContentType "application/json"
```

#### ② データの取得 (GET)
```powershell
Invoke-RestMethod -Uri "http://localhost:3500/v1.0/state/statestore/test_order_status"
```
* **期待されるレスポンス**:
  ```json
  {
    "status": "PENDING",
    "symbol": "7203.T"
  }
  ```

#### ③ データの削除 (DELETE)
```powershell
Invoke-RestMethod -Uri "http://localhost:3500/v1.0/state/statestore/test_order_status" -Method Delete
```

---

### 4.3 サービス呼び出し (Service Invocation)
Dapr Sidecar（ポート 3500）を経由して FastAPI アプリ（ポート 8000）のエンドポイントを呼び出します。

```powershell
# Dapr 経由で FastAPI のエンドポイントを実行
Invoke-RestMethod -Uri "http://localhost:3500/v1.0/invoke/trading-service/method/health"
```

---

## 5. モニタリングとトラブルシューティング

### 5.1 分散トレーシング (Zipkin)
ブラウザで以下の URL にアクセスすると、Dapr を通過したリクエストのトレースやレイテンシを可視化できます。
* URL: **http://localhost:9411**

### 5.2 Dapr Dashboard について
* Dapr CLI v1.18 以降、`dapr dashboard` コマンドは廃止（削除）されました。
* インスタンス状態の確認には `dapr list` を使用するか、外部ツールの [Diagrid Dev Dashboard](https://www.diagrid.io/) / Zipkin をご利用ください。

### 5.3 よくあるエラーと対処法

| エラー内容 | 原因 | 対処方法 |
| :--- | :--- | :--- |
| `GetFileAttributesEx ./components: The system cannot find the file specified.` | カレントディレクトリがプロジェクトルート以外（`src/` 等）になっている | プロジェクトルートに `cd` してからコマンドを実行する |
| `error connecting to redis at localhost:6379: connectex: ... refused it` | Redis コンテナが起動していない | Docker Desktop を起動し、`dapr init` または `docker start dapr_redis` を実行 |
| `failed finding secret store with key ...` | 指定したコンポーネント名が `components/*.yaml` の `metadata.name` と不一致 | `local-secret-store` など正しい名前を指定する |

---

## 6. アプリケーションおよびコンテナの停止手順

### 6.1 アプリケーション (Dapr Sidecar + FastAPI) の停止
動作確認終了後は、ポート（`3500`, `8000`）の占有を防ぐため停止することを推奨します。

* **フォアグラウンド実行中の場合**: ターミナル上で `Ctrl + C` を押します。
* **バックグラウンド実行や別ターミナルから停止する場合**:
  ```powershell
  dapr stop --app-id trading-service
  ```

### 6.2 バックグラウンドコンテナ (Redis / Zipkin 等) について
`dapr init` で起動した Docker コンテナ群（`dapr_redis`, `dapr_zipkin` 等）は、開発を継続する間は **起動したままで問題ありません**（軽量なためPC負荷はわずかです）。

PCのリソースを解放したい場合や作業を完全に終了する場合は、以下のコマンドでコンテナを停止できます。

```powershell
# Dapr 関連コンテナの停止
docker stop dapr_redis dapr_placement dapr_zipkin dapr_scheduler

# 再開時のコンテナ起動
docker start dapr_redis dapr_placement dapr_zipkin dapr_scheduler
```

