
import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append("/home/dryophytes/school/LiVraria")

from backend.api.datastore import DataStore
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Setup temporary file paths for testing
TEST_DIR = Path("/home/dryophytes/school/LiVraria/tmp_test_data")
TEST_DIR.mkdir(exist_ok=True)

# Monkey patch file paths in datastore module
# Note: We need to patch the imported variables in backend.api.datastore
import backend.api.datastore as ds
ds.DATA_DIR = TEST_DIR
ds.USERS_FILE = TEST_DIR / "users.json"
ds.CONVERSATIONS_FILE = TEST_DIR / "conversations.json"
ds.NFC_USERS_FILE = TEST_DIR / "nfc_users.json"

def test_message_persistence():
	print("--- Starting Message Persistence Test ---")
	
	# 1. Initialize DataStore
	store = DataStore()
	
	# 2. Create User and Session
	user_id = "test_user_001"
	personal = {"name": "TestUser", "gender": "unknown", "age": 20}
	store.create_user(user_id, personal)
	session_id = store.create_session(user_id)
	print(f"Created session: {session_id}")
	
	# 3. Add LangChain Messages directly to in-memory session
	messages = [
		SystemMessage(content="You are a helpful assistant."),
		HumanMessage(content="Hello, world!"),
		AIMessage(content="Hi there! How can I help you?"),
	]
	store.update_history(session_id, messages)
	print("Added 3 messages (System, Human, AI)")
	
	# Verify in-memory type
	current_history = store.get_history(session_id)
	print(f"In-memory history type: {type(current_history)}")
	print(f"First message type: {type(current_history[0])}")
	assert isinstance(current_history[0], SystemMessage)
	
	# 4. Pause Session (which persists to disk)
	store.pause_session(session_id)
	print("Paused session (saved to disk)")
	
	# 5. Verify JSON content
	with open(ds.CONVERSATIONS_FILE, "r") as f:
		data = json.load(f)
		saved_messages = data[session_id]["messages"]
		print(f"Saved JSON messages count: {len(saved_messages)}")
		print(f"First saved message structure: {saved_messages[0]}")
		
		# Check for LangChain structure
		if "type" in saved_messages[0] and saved_messages[0]["type"] == "system":
			print("[SUCCESS] correct LangChain 'type' field found in JSON")
		else:
			print(f"[FAILURE] Unexpected JSON structure: {saved_messages[0]}")
			
	# 6. Restore Session
	# Re-initialize DataStore to simulate server restart
	new_store = DataStore()
	# Resume session
	new_store.resume_session(session_id)
	
	restored_history = new_store.get_history(session_id)
	print(f"Restored history count: {len(restored_history)}")
	print(f"Restored first message type: {type(restored_history[0])}")
	
	assert len(restored_history) == 3
	assert isinstance(restored_history[0], SystemMessage)
	assert isinstance(restored_history[1], HumanMessage)
	assert isinstance(restored_history[2], AIMessage)
	assert restored_history[1].content == "Hello, world!"
	
	print("[SUCCESS] All persistence tests passed!")

if __name__ == "__main__":
	try:
		test_message_persistence()
	except Exception as e:
		print(f"[ERROR] Test failed: {e}")
		import traceback
		traceback.print_exc()
