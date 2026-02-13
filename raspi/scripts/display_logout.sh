#!/bin/bash

echo "[$(date)] Display Logout Script Started" >> /tmp/display_control.log

# "Secondary Display" というウィンドウを閉じる
# wmctrl -c <WINDOW_TITLE> : Close the window cleanly
wmctrl -c "Secondary Display"

if [ $? -eq 0 ]; then
    echo "Sent close request to Secondary Display." >> /tmp/display_control.log
else
    echo "Failed to close Secondary Display (or not found)." >> /tmp/display_control.log
fi
