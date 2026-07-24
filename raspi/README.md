# Raspberry Pi

このディレクトリには、Raspberry Pi 上のブラウザ起動と NFC カード読み取りに関するファイルがある。NFC API サーバーの詳細は [nfc/README.md](nfc/README.md) を参照する。

## 現稼働機の構成

以下は 2026-07-24 にホスト `livraria` で確認した構成である。過去の構成や `raspi/2nddisp` ブランチの再現性は対象外とする。

- OS: Debian GNU/Linux 13 (trixie)、`6.12.47+rpt-rpi-v8`、arm64
- デスクトップ: Labwc。`livraria` は tty1 で自動ログインする。
- 画面: HDMI-A-1 と HDMI-A-2 が接続されている。
- NFC: Sony RC-S380 / PaSoRi 4.0（USB ID `054c:0dc9`）を使用する。

## ディスプレイとタッチパネル

`/boot/firmware/config.txt` には、次の実機固有の設定がある。

```ini
enable_uart=1
hdmi_force_hotplug=1
hdmi_cvt 1024 600 60 3 0 0 0
hdmi_group=2
hdmi_mode=87
```

カーネル起動引数では HDMI-A-1 を `1024x600@60`、HDMI-A-2 を `1920x1080@60` に指定している。

```text
video=HDMI-A-1:1024x600M@60D video=HDMI-A-2:1920x1080M@60D
```

タッチパネルは USB HID デバイス（`27c0:0818`、`Paperlike HD-FT`）として自動認識されている。専用のキャリブレーション、座標変換、udev ルールは確認できなかったため、再構築時はまずこの状態で動作を確認する。

## 自動ログイン

`/etc/systemd/system/getty@tty1.service.d/autologin.conf` で tty1 の getty に `livraria` ユーザーの自動ログインを設定している。

```ini
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin livraria --noclear %I $TERM
```

Chromium の常駐起動やセカンドディスプレイ制御については、現稼働機で実機固有の追加設定を確認できていない。

## NFC サーバー

現稼働機では `/home/livraria/LiVraria/raspi/raspi_api_server.py` が `raspi-api.service` として起動している。NFC の構成と API の詳細は [nfc/README.md](nfc/README.md) を参照する。

リポジトリ内の `raspi/nfc/setup.sh` と `nfc-api.service` はセットアップ用の既存ファイルであり、実機のサービス名・配置先とは異なる。実機へ適用する前に、サービス定義と実行パスを必ず照合する。
