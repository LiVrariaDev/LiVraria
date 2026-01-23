#!/bin/bash

# ==========================================
# Livraria 起動スクリプト (Dual Display Kiosk)
# ==========================================

# 設定: アプリのURL (ローカルサーバーのアドレス)
# ラズパイ自身でサーバーを動かす場合は localhost でOKですが、
# PCで動かしている場合は PCのIPアドレス (例: 192.168.1.10) を指定してください。
TARGET_URL="http://localhost:5173"

# 設定: ディスプレイ解像度 (一次ディスプレイの横幅)
# これを基準にセカンダリウィンドウの位置を決定します
PRIMARY_WIDTH=1920

# ------------------------------------------

echo "Starting Livraria..."

# マウスカーソルを消す (unclutterがインストールされていれば)
# unclutter -idle 0.1 -root &

# 1. メイン画面 (操作用) を起動
# --window-position=0,0 : 左上のディスプレイに表示
chromium-browser \
  --new-window "$TARGET_URL" \
  --window-position=0,0 \
  --start-fullscreen \
  --kiosk \
  --no-first-run \
  --noerrdialogs \
  --disable-infobars \
  --user-data-dir="/tmp/chrome_main_profile" &

echo "Main display launched."

# 少し待機して、ブラウザの競合を防ぐ
sleep 3

# 2. セカンダリ画面 (アバター用) を起動
# --window-position=$PRIMARY_WIDTH,0 : 右隣のディスプレイに表示
chromium-browser \
  --new-window "$TARGET_URL/?view=secondary" \
  --window-position=$PRIMARY_WIDTH,0 \
  --start-fullscreen \
  --kiosk \
  --no-first-run \
  --noerrdialogs \
  --disable-infobars \
  --user-data-dir="/tmp/chrome_secondary_profile" &

echo "Secondary display launched."

echo "Livraria system is running."
