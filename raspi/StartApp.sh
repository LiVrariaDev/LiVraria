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

# メインとサブは BroadcastChannel で通信するため、同じプロファイルで起動する
PROFILE_DIR="/tmp/chrome_livraria_profile"
MAX_WAIT=30  # ウィンドウ検出の最大待ち秒数

# place_window <タイトル> <x> <最大待ち秒>
# タイトルのウィンドウを探し、指定位置へ移動してフルスクリーン化する
place_window() {
    local title="$1" x="$2" max_wait="$3"
    local id="" counter=0

    while [ "$counter" -lt "$max_wait" ]; do
        id=$(wmctrl -l | grep "$title" | awk '{print $1}' | head -n 1)
        if [ -n "$id" ]; then
            sleep 0.5  # ウィンドウが完全に表示されるまで少し待つ
            wmctrl -i -r "$id" -e 0,"$x",0,-1,-1
            wmctrl -i -r "$id" -b add,fullscreen
            echo "Window '$title' placed at x=$x and set to fullscreen."
            return 0
        fi
        sleep 1
        counter=$((counter + 1))
    done

    echo "Warning: Window '$title' not detected within ${max_wait}s."
    return 1
}

# 1. メイン画面 (操作用)
chromium \
  --app="$SERVER_URL" \
  --window-position=0,0 \
  --force-device-scale-factor=0.8 \
  --autoplay-policy=no-user-gesture-required \
  --ozone-platform=x11 \
  --user-data-dir="$PROFILE_DIR" \
  --touch-events=enabled \
  --disable-touch-drag-drop \
  --unsafely-treat-insecure-origin-as-secure="$SERVER_URL" \
  --overscroll-history-navigation=0 &

echo "Main display launched."
sleep 3

# 2. サブ画面 (同じプロファイルへ新しいウィンドウとして渡される)
chromium \
  --app="$SERVER_URL/?view=secondary" \
  --user-data-dir="$PROFILE_DIR" \
  --autoplay-policy=no-user-gesture-required \
  --ozone-platform=x11 \
  --unsafely-treat-insecure-origin-as-secure="$SERVER_URL" &

echo "Secondary display launched."

# 3. ウィンドウを配置
place_window "LiVraria Main" 0 "$MAX_WAIT"
place_window "Secondary Display" "$PRIMARY_WIDTH" "$MAX_WAIT"

echo "Livraria system is running."
