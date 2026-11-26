"""認証まわりの共通処理（server.py とルーターで共有）。"""

import hmac
import logging
import os

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth

logger = logging.getLogger("uvicorn.error")

oauth2_scheme = HTTPBearer()


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)) -> str:
	"""Authorization ヘッダーの Firebase ID トークンを検証し、User ID を返す。"""
	try:
		decoded_token = auth.verify_id_token(credentials.credentials)
		return decoded_token["uid"]
	except Exception as e:
		logger.error(f"[ERROR] Firebase authentication failed: {e}")
		raise HTTPException(status_code=401, detail="Invalid authentication token")


def device_key_configured() -> bool:
	return bool(os.getenv("LIVRARIA_DEVICE_KEY"))


def verify_device_key(x_device_key: str = Header(default="")) -> None:
	"""
	端末共有キー（X-Device-Key ヘッダー）を検証する。
	NFC ログインのように Firebase トークンを持たない段階の API を、
	登録済みの端末以外から呼べないようにするために使う。

	LIVRARIA_DEVICE_KEY が空なら確認せずに通す（応急対応。会場の LAN が閉じている前提で、
	どの端末からでも呼べる。起動時に警告を出す）。設定されていて値が違うときは 403。
	"""
	expected = os.getenv("LIVRARIA_DEVICE_KEY", "")
	if not expected:
		return
	if not hmac.compare_digest(x_device_key.encode(), expected.encode()):
		raise HTTPException(status_code=403, detail="Unknown device")


def verify_admin_key(x_admin_key: str = Header(default="")) -> None:
	"""
	デバッグ API 用の管理者キー（X-Admin-Key ヘッダー）を検証する。
	LIVRARIA_DEVICE_KEY とは別のキーを使う。
	"""
	expected = os.getenv("LIVRARIA_ADMIN_KEY", "")
	if not expected:
		raise HTTPException(status_code=503, detail="Debug API is disabled: LIVRARIA_ADMIN_KEY is not set")
	if not x_admin_key:
		raise HTTPException(status_code=401, detail="Admin key required")
	if not hmac.compare_digest(x_admin_key.encode(), expected.encode()):
		raise HTTPException(status_code=403, detail="Invalid admin key")
