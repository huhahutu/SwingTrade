import os

from dapr.clients import DaprClient


def get_secret(key: str, secret_store_name: str = "local-secret-store") -> str:
    """
    Dapr Secrets API を使用して機密情報を取得する。
    ローカル開発時など Dapr が起動していない場合は、フォールバックとして環境変数を参照する。
    """
    # Daprが動作しているかの簡易判定（環境変数 DAPR_GRPC_PORT 等の存在確認）
    if os.getenv("DAPR_GRPC_PORT") or os.getenv("DAPR_HTTP_PORT"):
        try:
            with DaprClient() as client:
                response = client.get_secret(store_name=secret_store_name, key=key)
                if response and response.secret and key in response.secret:
                    return response.secret[key]
        except Exception as e:
            print(
                f"[Warning] Dapr Secrets API からの {key} 取得に失敗しました: {e}. "
                "環境変数をフォールバックとして使用します。"
            )

    # Daprから取得できなかった場合、またはDapr未稼働の場合は環境変数から取得
    val = os.getenv(key)
    if not val:
        raise ValueError(
            f"シークレット '{key}' がストア '{secret_store_name}' "
            "および環境変数から取得できませんでした。"
        )
    return val
