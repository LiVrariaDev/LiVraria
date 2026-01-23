#!/bin/bash

# ==========================================
# Livraria 起動スクリプト (Dual Display Kiosk)
# ==========================================

# log file (1回ごと上書き, シンボリックリンク元で)
LOG_FILE="$(dirname "$0")/livraria_start.log"
exec > >(tee "$LOG_FILE") 2>&1

# ファイル実体へ移動
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
cd "$SCRIPT_DIR"

# .envファイルを読み込む
if [ -f .env ]; then
    source .env
else
    echo "Error: .env file not found."
    exit 1
fi

echo "Starting Livraria..."

# マウスカーソルを消す (unclutterがインストールされていれば)
# unclutter -idle 0.1 -root &

# 1. メイン画面 (操作用) を起動
# --window-position=0,0 : 左上のディスプレイに表示
chromium \
  --new-window "$SERVER_URL" \
  --window-position=0,0 \
  --start-fullscreen \
  --kiosk \
  --no-first-run \
  --noerrdialogs \
  --disable-infobars \
  --ozone-platform=x11 \
  --user-data-dir="/tmp/chrome_main_profile" &

echo "Main display launched."

# 少し待機して、ブラウザの競合を防ぐ
sleep 3
wmctrl -r "LiVraria Main" -e 0,0,0,-1,-1

# 2. セカンダリ画面 (アバター用) を起動
# --window-position=$$PRIMARY_WIDTH,0 : 右隣のディスプレイに表示
chromium \
  --new-window "$SERVER_URL/?view=secondary" \
  --window-position=$PRIMARY_WIDTH,0 \
  --start-fullscreen \
  --kiosk \
  --no-first-run \
  --noerrdialogs \
  --disable-infobars \
  --ozone-platform=x11 \
  --user-data-dir="/tmp/chrome_secondary_profile" &

echo "Secondary display launched."

sleep 3
wmctrl -r "Secondary Display" -e 0,$PRIMARY_WIDTH,0,-1,-1

echo "Livraria system is running."
