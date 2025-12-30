# Pydantic Models for LiVraria API

from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
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
	message: str
	session_id: str = None

class ChatResponse(BaseModel):
	response: str
	session_id: str
	recommended_books: List[dict] = Field(default_factory=list, description="推薦された書籍リスト")

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

	class Config:
		populate_by_name = True

class Conversation(BaseModel):
	session_id: str = Field(alias="_id", description="Session ID")
	user_id: str = Field(description="User ID")
	status: ChatStatus = Field(default=ChatStatus.active, description="Chat status")
	messages: List[Message] = Field(default_factory=list, description="Chat messages")
	summary: Optional[str] = Field(None, description="AI-generated summary at session end")
	last_accessed: datetime = Field(default_factory=datetime.now, description="Last accessed time")

	class Config:
		populate_by_name = True

