# Pydantic Models for LiVraria API

from enum import Enum
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional

# Enum
class ChatStatus(str, Enum):
	active = "active"
	pause = "pause"
	closed = "closed"

class UserStatus(str, Enum):
	activate = "activate"
	logout = "logout"
	chatting = "chatting"

# Request/Response Models
class ChatRequest(BaseModel):
	message: str = Field(min_length=1, max_length=2000)
	session_id: Optional[str] = None

class NfcIdRequest(BaseModel):
	nfc_id: str = Field(min_length=1, max_length=64)

class PersonalUpdate(BaseModel):
	"""クライアントから変更可能なプロフィール項目（未指定の項目は変更しない）。"""
	model_config = ConfigDict(extra="forbid")
	name: Optional[str] = Field(None, max_length=50)
	gender: Optional[str] = Field(None, max_length=20)
	age: Optional[int] = Field(None, ge=0, le=150)
	live_pref: Optional[str] = Field(None, max_length=10)
	live_city: Optional[str] = Field(None, max_length=50)

class UserUpdate(BaseModel):
	"""PUT /users/{user_id} のリクエスト。status や ai_insights などは変更させない。"""
	model_config = ConfigDict(extra="forbid")
	personal: PersonalUpdate

class ChatResponse(BaseModel):
	response: str
	session_id: str
	recommended_books: List[dict] = Field(default_factory=list, description="推薦された書籍リスト")
	expression: str = Field("none", description="司書の表情ステータス")
	trace_id: Optional[str] = Field(None, description="このターンのトレース ID")
	failed: bool = Field(False, description="応答が失敗時の定型文なら True")

# Data Models
# Message Class : 廃止, LangChainの方へ合わせる

class NfcUser(BaseModel):
	nfc_id: str = Field(alias="_id", description="NFC ID")
	user_id: str = Field(description="User ID")

class BookData(BaseModel):
	isbn: str = Field(alias="_id", description="ISBN")
	title: str = Field(description="Book title")

class RecommendationLogEntry(BaseModel):
	reason: str = Field(description="Reason for recommendation")
	timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of recommendation")
	book_data: BookData = Field(description="Recommended book data")

class Personal(BaseModel):
	name: str = Field(description="Name")
	gender: str = Field(description="Gender")
	age: int = Field(description="Age")
	live_pref: Optional[str] = Field(None, description="Living preference")
	live_city: Optional[str] = Field(None, description="Living city")

class User(BaseModel):
	user_id: str = Field(alias="_id", description="User ID")
	ai_insights : str = Field("", description="AI Insights about the user")
	personal: Personal = Field(default_factory=Personal, description="Personal information (gender, age ...)")
	status: UserStatus = Field(default=UserStatus.logout, description="User status (activate/logout/chatting)")
	active_session: Optional[str] = Field(default=None, description="Active chat session ID")
	old_session: List[str] = Field(default_factory=list, description="Old chat session IDs")
	recommend_log: List[RecommendationLogEntry] = Field(default_factory=list, description="Recommendation log")
	lastlogin: datetime = Field(default_factory=datetime.now, description="Last login time")
	learning_enabled: bool = Field(True, description="False なら要約と AI Insights の更新を行わない(共有デモアカウント用)")

	model_config = ConfigDict(populate_by_name=True)

class Conversation(BaseModel):
	session_id: str = Field(alias="_id", description="Session ID")
	user_id: str = Field(description="User ID")
	status: ChatStatus = Field(default=ChatStatus.active, description="Chat status")
	messages: List[dict] = Field(default_factory=list, description="Chat messages")
	summary: Optional[str] = Field(None, description="AI-generated summary at session end")
	# 会話グラフ v2 用（v1 では使わない）。既存データでは空として読み込まれる
	profile: dict = Field(default_factory=dict, description="読書プロフィール（会話グラフ v2）")
	last_picks: List[dict] = Field(default_factory=list, description="前のターンで選んだ本（会話グラフ v2 の ask_book 用）")
	last_accessed: datetime = Field(default_factory=datetime.now, description="Last accessed time")

	model_config = ConfigDict(populate_by_name=True)

