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
	"""
	expected = os.getenv("LIVRARIA_DEVICE_KEY", "")
	if not expected:
		raise HTTPException(status_code=503, detail="NFC login is disabled: LIVRARIA_DEVICE_KEY is not set on the server")
	if not hmac.compare_digest(x_device_key.encode(), expected.encode()):
		raise HTTPException(status_code=403, detail="Unknown device")
