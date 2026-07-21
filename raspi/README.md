# Raspberry Pi

このディレクトリには、Raspberry Pi 上のブラウザ起動と NFC カード読み取りに関するファイルがある。NFC API サーバーの詳細は [nfc/README.md](nfc/README.md) を参照する。

## 確認済みの範囲

Raspberry Pi とセカンドディスプレイを使った実証は `raspi/2nddisp` ブランチの内容で行われた。現在の `main` で同じ手順・表示・NFC 連携を再現できるかは確認していない。

このため、ここでは現在のファイルから確認できる NFC API サーバーのセットアップ方法だけを扱う。ディスプレイ設定、Chromium の常駐起動、セカンドディスプレイの制御は確認待ちである。

## NFC サーバー

NFC API サーバーは `raspi/nfc/` にある。カードリーダーに必要な `pcscd`、`pcsc-tools`、`libpcsclite-dev` と Python 依存関係を使う。

```bash
cd raspi/nfc
./setup.sh
```

このスクリプトは `sudo` で直接実行してはならない。内部で必要なシステムパッケージをインストールし、pyenv と Python 3.11.13、`.venv`、Python 依存関係をセットアップする。

手動でのカードリーダー確認と API の起動は次のとおり。

```bash
pcsc_scan
source .venv/bin/activate
python nfc_api_server.py
curl http://localhost:8000/health
```

NFC API サーバーはポート 8000 を使用する。FastAPI バックエンドも既定でポート 8000 を使用するため、同じホストで両方を同時に起動する構成はそのままでは成立しない。ネットワーク構成またはポート変更の方針は未確認である。

## systemd

`./setup.sh --systemd` は `nfc-api.service` を登録する。ただし、サービス定義には `WorkingDirectory=/home/livraria/LiVraria/raspi/nfc` などの固定パスがある。実機の設置先と一致するよう確認・修正してから有効化する。

## 確認待ち

- `raspi/2nddisp` の変更を `main` に統合する時期と手順
- ブラウザ、NFC API、FastAPI の配置と相互通信
- セカンドディスプレイ、音声、Chromium 自動起動の再現手順
- 使用する Raspberry Pi OS、カードリーダー、ディスプレイの機種
