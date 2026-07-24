# NFC API サーバー

NFC API サーバーは Flask で動く Raspberry Pi 向けのローカル API である。PC/SC 経由で Sony RC-S380 / PaSoRi 4.0 から FeliCa IDm を取得する。

## 現稼働機の構成

2026-07-24 時点の `livraria` では、次の構成で稼働している。

- カードリーダー: Sony RC-S380 / PaSoRi 4.0（USB ID `054c:0dc9`）
- システムサービス: `pcscd.service` と `pcscd.socket` を有効化
- Python 環境: `/home/livraria/LiVraria/raspi/.venv`
- 実行プログラム: `/home/livraria/LiVraria/raspi/raspi_api_server.py`
- systemd サービス: `raspi-api.service`、root ユーザーで実行
- 待受ポート: `0.0.0.0:8000`

NFC の読み取り処理は `pyscard` の `smartcard.System.readers()` と PC/SC を使い、APDU `FF CA 00 00 00` で IDm を取得する。

## 依存関係と確認

必要なシステムパッケージは `pcscd`、`pcsc-tools`、`libpcsclite-dev` である。カードリーダーと PC/SC の認識は次で確認できる。

```bash
systemctl status pcscd.service
pcsc_scan
```

Python 依存関係には少なくとも `pyscard==2.3.1`、`Flask`、`flask-cors` が含まれる。現在の API は音声認識・音声合成も提供するため、実機のサービスには `VOSK_MODEL_PATH=/opt/vosk-model-ja` が設定されている。

## systemd

現稼働機の `raspi-api.service` は `pcscd.service` に依存し、ネットワーク起動後に API を起動する。主要な設定は次のとおりである。

```ini
[Unit]
After=network.target pcscd.service
Requires=pcscd.service

[Service]
User=root
WorkingDirectory=/home/livraria/LiVraria/raspi
ExecStart=/home/livraria/LiVraria/raspi/.venv/bin/python3 /home/livraria/LiVraria/raspi/raspi_api_server.py
Restart=always
RestartSec=10
Environment="PYTHONUNBUFFERED=1"
Environment="VOSK_MODEL_PATH=/opt/vosk-model-ja"
```

リポジトリの `nfc-api.service` と `setup.sh --systemd` は `raspi/nfc/` 配下を前提とし、実機とはサービス名・実行パスが異なる。稼働中の `raspi-api.service` を置き換えないよう、そのまま実行せず、適用前にサービス定義を照合する。

## エンドポイント

| メソッド | パス | 用途 |
| --- | --- | --- |
| `GET` | `/health` | ヘルスチェック。VOSK の利用可否も返す。 |
| `POST` | `/start-nfc` | 非同期の NFC 読み取りを開始する。本文の `timeout` は秒数で、既定は 20。 |
| `GET` | `/check-nfc` | 読み取り状態を返す。`idle`、`reading`、`success`、`timeout` を使用する。 |
| `GET` | `/read-nfc` | 直近の読み取り結果を返す。 |
| `POST` | `/speak` | テキスト音声合成・再生を行う。 |
| `POST` | `/display/login` | 画面ログイン用スクリプトを実行する。 |
| `POST` | `/display/logout` | 画面ログアウト用スクリプトを実行する。 |

`/check-nfc` の成功時は `idm` を返す。成功した結果は約 5 秒後にリセットされる。

## 注意事項

- API は `0.0.0.0:8000` で待ち受け、CORS はすべてのオリジンを許可する実装である。公開ネットワークへ直接公開する用途は確認していない。
- FastAPI バックエンドの既定ポートも 8000 である。同一ホストに両方を置く場合のポート・プロキシ設定は未確認である。
- `.env` の内容や認証情報はこの文書に記載しない。
