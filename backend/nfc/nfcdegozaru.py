from smartcard.System import readers
from smartcard.util import toHexString
import time

def read_card_idm():
    try:
        # 接続されているリーダーのリストを取得
        reader_list = readers()
    except Exception as e:
        print(f"カードリーダーの取得中にエラーが発生しました: {e}")
        return

    if not reader_list:
        print("利用可能なカードリーダーが見つかりません。RC-S300が正しく接続・認識されているか確認してください。")
        return

    print("利用可能なカードリーダー:", reader_list)
    # 最初のリーダーを選択
    reader = reader_list[0]
    print(f"'{reader}' に接続を試みます...")
    
    # FelicaカードのIDm取得用APDUコマンド
    GET_IDM_APDU = [0xFF, 0xCA, 0x00, 0x00, 0x00]

    while True:
        try:
            connection = reader.createConnection()
            connection.connect()

            response, sw1, sw2 = connection.transmit(GET_IDM_APDU)
            
            if sw1 == 0x90 and sw2 == 0x00:
                idm_hex = toHexString(response)
                print(f"✅ カードのIDmが読み取られました: **{idm_hex}**")
                connection.disconnect()
                break 
            
            else:
                connection.disconnect()
                print("カードが検出されません。かざしてください... (ステータス: %02X %02X)" % (sw1, sw2))

        except Exception as e:
            # カードが離された、あるいは接続エラーが発生した場合
            print("カードが検出されません。かざしてください...")

        time.sleep(1)

if __name__ == "__main__":
    print("NFCカード（FeliCaなど）のIDm読み取りプログラムを開始します。")
    read_card_idm()
    print("プログラムを終了します。")