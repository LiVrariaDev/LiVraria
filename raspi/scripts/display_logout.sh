#!/bin/bash

# 環境変数の設定
export DISPLAY=:0
export XAUTHORITY=/home/livraria/.Xauthority

echo "[$(date)] Display Logout Script Started" >> /tmp/display_control.log
echo "User: $(whoami), Display: $DISPLAY" >> /tmp/display_control.log
wmctrl -l >> /tmp/display_control.log

MAX_WAIT=20 # 20秒待機
COUNTER=0

while [ $COUNTER -lt $MAX_WAIT ]; do
    # ウィンドウの存在確認
    SEC_ID=$(wmctrl -l | grep "Secondary Display" | awk '{print $1}')
    
    if [ -z "$SEC_ID" ]; then
        echo "Secondary Display is closed." >> /tmp/display_control.log
        exit 0
    fi

    # ウィンドウがあれば閉じる要求を送る
    wmctrl -c "Secondary Display"
    echo "Sent close request... ($COUNTER)" >> /tmp/display_control.log
    
    sleep 0.5
    COUNTER=$((COUNTER + 1))
done

echo "Timeout: Failed to close Secondary Display." >> /tmp/display_control.log
wmctrl -l >> /tmp/display_control.log
exit 1
