# NFC API サーバー

`nfc_api_server.py` は Flask で動く Raspberry Pi 向けのローカル NFC 読み取り API である。PC/SC 経由でカードリーダーに接続し、FeliCa IDm を取得する。

## セットアップ

Raspberry Pi 上で `raspi/nfc/` に移動して実行する。

```bash
./setup.sh
```

スクリプトは `sudo` で直接実行しない。`pcscd`、`pcsc-tools`、`libpcsclite-dev` などをインストールし、pyenv で Python 3.11.13 を用意して `.venv` に `requirements.txt` をインストールする。

カードリーダーを確認してから手動起動する。

```bash
pcsc_scan
source .venv/bin/activate
python nfc_api_server.py
curl http://localhost:8000/health
```

## エンドポイント

| メソッド | パス | 用途 |
| --- | --- | --- |
| `GET` | `/health` | ヘルスチェック |
| `POST` | `/start-nfc` | 非同期の NFC 読み取りを開始する。本文の `timeout` は秒数で、既定は 20。 |
| `GET` | `/check-nfc` | 読み取り状態を返す。`idle`、`reading`、`success`、`timeout` を使用する。 |
| `GET` | `/read-nfc` | 直近の読み取り結果を返す。 |

`/check-nfc` の成功時は `idm` を返す。成功した結果は約 5 秒後にリセットされる。

## systemd

自動起動を設定するには次を実行する。

```bash
./setup.sh --systemd
```

`nfc-api.service` には固定のユーザーとパスが記述されているため、有効化する前に実機の配置先・実行ユーザー・仮想環境パスと一致するか確認する。

## 制約と確認待ち

- API は `0.0.0.0:8000` で待ち受け、CORS はすべてのオリジンを許可する実装である。公開ネットワークへ直接公開する用途は確認していない。
- FastAPI バックエンドの既定ポートも 8000 である。同一ホストに両方を置く場合のポート・プロキシ設定は未確認である。
- 実証済みなのは `raspi/2nddisp` ブランチであり、現在の `main` での動作確認は未実施である。
