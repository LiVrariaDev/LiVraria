import time
import os
import pyautogui
from smartcard.System import readers
from smartcard.util import toHexString

# SSH経由でもメインディスプレイを操作できるように設定
os.environ["DISPLAY"] = ":0"

def read_card_and_type():
    # IDm取得用のAPDUコマンド (PC/SC規格)
    GET_IDM_APDU = [0xFF, 0xCA, 0x00, 0x00, 0x00]

    print("NFCカードリーダー待機中... (Ctrl+Cで終了)")

    while True:
        try:
            reader_list = readers()
            if not reader_list:
                print("リーダーが見つかりません...")
                time.sleep(2)
                continue

            reader = reader_list[0]
            connection = reader.createConnection()
            connection.connect()

            response, sw1, sw2 = connection.transmit(GET_IDM_APDU)

            if sw1 == 0x90 and sw2 == 0x00:
                # IDmを16進数の文字列に変換
                idm_hex = toHexString(response).replace(" ", "")
                print(f"✅ IDm読み取り成功: {idm_hex}")

                # --- 自動入力処理 ---
                # ブラウザのフォームに入力（intervalで少し速度を落とすと確実です）
                pyautogui.write(idm_hex, interval=0.05)
                # Enterキーを押下
                pyautogui.press('enter')
                
                print("入力完了。連打防止のため5秒間スリープします。")
                connection.disconnect()
                
                # カードを離す時間を考慮した待機
                time.sleep(5) 
            
            else:
                connection.disconnect()

        except Exception:
            # カードが置かれていない時は例外が発生するため無視してループ
            pass

        time.sleep(0.5)

if __name__ == "__main__":
    try:
        read_card_and_type()
    except KeyboardInterrupt:
        print("\nプログラムを終了します。")