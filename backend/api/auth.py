
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth
import logging

logger = logging.getLogger("uvicorn.error")

oauth2_scheme = HTTPBearer()

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)) -> str:
    """
    HTTP Headerに含まれたTokenをFirebase Authで認証し
    認証に成功した場合はUser IDを返す
    """
    try:
        id_token = credentials.credentials
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token["uid"]
    except Exception as e:
        logger.error(f"[ERROR] Firebase authentication failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")
