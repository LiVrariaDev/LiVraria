# メモリ効率化とステータス再設計

## 概要

現在の実装では、サーバー起動時に全ユーザー・全会話をメモリに読み込んでおり、メモリ効率が悪い。また、`pause`ステータスがタイムアウトとサーバー停止の両方で使われており、役割が曖昧。

この計画では、遅延読み込み（Lazy Loading）を実装し、ステータスの役割を明確化する。

## 問題点

### 1. メモリ効率
- **現状**: `_load_from_files()`で全データを読み込み
- **問題**: ユーザー数が増えるとメモリ使用量が増大
- **影響**: スケーラビリティの問題

### 2. ステータスの曖昧さ
- **現状**: `pause`がタイムアウトとサーバー停止の両方で使用
- **問題**: 役割が不明確
- **影響**: 復元ロジックが複雑

## 改善案

### 1. ステータスの再定義

#### active
- **意味**: アクティブなセッション
- **場所**: メモリ上
- **遷移**: ユーザーがチャット中

#### pause
- **意味**: サーバー停止時の一時保存
- **場所**: ディスク（conversations.json）
- **遷移**: サーバー停止時に`active` → `pause`
- **復元**: サーバー起動時に`pause` → `active`（last_accessed更新）

#### closed
- **意味**: 完全終了
- **場所**: ディスク（conversations.json）
- **遷移**: 
  - 30分タイムアウト: `active` → `closed`
  - 明示的クローズ: `active` → `closed`
- **復元**: なし（summary/ai_insights生成済み）

### 2. 遅延読み込み（Lazy Loading）

#### 起動時（`__init__`）
```python
def __init__(self):
    # ファイルパスのみ設定
    self.users_file = DATA_DIR / "users.json"
    self.conversations_file = DATA_DIR / "conversations.json"
    self.nfc_users_file = DATA_DIR / "nfc_users.json"
    
    # メモリ上のデータ（最小限）
    self.users: Dict[str, User] = {}  # pauseセッションのユーザーのみ
    self.conversations: Dict[str, Conversation] = {}  # pauseのみ
    self.sessions: Dict[str, List] = {}  # pauseのみ
    self.nfc_users: Dict[str, NfcUser] = {}  # 全件（軽量）
    
    # pauseセッションとそのユーザーを復元
    self._restore_paused_sessions()
```

#### ユーザーログイン時
```python
def load_user(self, user_id: str) -> User:
    """
    ユーザーデータを遅延読み込み。
    既にメモリにある場合はそのまま返す。
    """
    if user_id in self.users:
        # lastloginを更新
        self.users[user_id].lastlogin = datetime.now()
        return self.users[user_id]
    
    # ディスクから読み込み
    all_users = self._read_json(self.users_file)
    if user_id in all_users:
        user_data = all_users[user_id]
        user = User(**user_data)
        # lastloginを更新
        user.lastlogin = datetime.now()
        self.users[user_id] = user
        return user
    
    raise KeyError(f"User {user_id} not found")
```

#### セッション読み込み
```python
def load_conversation(self, session_id: str) -> Conversation:
    """
    会話データを遅延読み込み。
    既にメモリにある場合はそのまま返す。
    """
    if session_id in self.conversations:
        return self.conversations[session_id]
    
    # ディスクから読み込み
    all_conversations = self._read_json(self.conversations_file)
    if session_id in all_conversations:
        conv_data = all_conversations[session_id]
        conv = Conversation(**conv_data)
        
        # closedセッションは読み込まない（メモリ節約）
        if conv.status == ChatStatus.closed:
            raise ValueError(f"Session {session_id} is closed")
        
        self.conversations[session_id] = conv
        # activeセッションのみメモリに展開
        if conv.status == ChatStatus.active:
            self.sessions[session_id] = conv.messages
        
        return conv
    
    raise KeyError(f"Session {session_id} not found")
```

#### メモリ解放（ユーザー単位）
```python
def unload_inactive_users(self):
    """
    非アクティブなユーザーをメモリから解放。
    lastloginを基準に判定（SESSION_TIMEOUT秒）。
    """
    timeout_threshold = datetime.now() - timedelta(seconds=SESSION_TIMEOUT)
    users_to_unload = []
    
    for user_id, user in list(self.users.items()):
        # lastloginがタイムアウトを超えている場合
        if user.lastlogin < timeout_threshold:
            # そのユーザーのアクティブセッションをすべてclose
            sessions_to_close = []
            for session_id, conv in list(self.conversations.items()):
                if conv.user_id == user_id and conv.status == ChatStatus.active:
                    sessions_to_close.append(session_id)
            
            # セッションをclose
            for session_id in sessions_to_close:
                conv = self.conversations[session_id]
                conv.status = ChatStatus.closed
                # メモリから削除
                if session_id in self.sessions:
                    del self.sessions[session_id]
                del self.conversations[session_id]
                logger.info(f"[INFO] Closed inactive session: {session_id}")
            
            # ユーザーをメモリから削除
            users_to_unload.append(user_id)
    
    for user_id in users_to_unload:
        del self.users[user_id]
        logger.info(f"[INFO] Unloaded inactive user: {user_id}")
    
    # 変更を保存
    if users_to_unload:
        self.save_file()
    
    return len(users_to_unload)
```

### 3. タイムアウト処理の変更（ユーザー単位）

#### 現在
```python
def check_session_timeout(self):
    # セッション単位でタイムアウトチェック
    # タイムアウト → pause
    self.pause_session(session_id)
```

#### 変更後
```python
def check_user_timeout(self):
    """
    非アクティブなユーザーのセッションをcloseする。
    lastloginを基準に判定（SESSION_TIMEOUT秒）。
    """
    timeout_threshold = datetime.now() - timedelta(seconds=SESSION_TIMEOUT)
    closed_sessions = []
    
    for user_id, user in list(self.users.items()):
        # lastloginがタイムアウトを超えている場合
        if user.lastlogin < timeout_threshold:
            # そのユーザーのアクティブセッションをすべてclose
            for session_id, conv in list(self.conversations.items()):
                if conv.user_id == user_id and conv.status == ChatStatus.active:
                    logger.info(f"[INFO] User timeout: {user_id}, closing session: {session_id}")
                    # active → closed
                    conv.status = ChatStatus.closed
                    # メモリから削除
                    if session_id in self.sessions:
                        del self.sessions[session_id]
                    closed_sessions.append(session_id)
            
            # ユーザーをメモリから削除
            del self.users[user_id]
            logger.info(f"[INFO] Unloaded inactive user: {user_id}")
    
    # 変更を保存
    if closed_sessions:
        self.save_file()
    
    return closed_sessions
```

**メリット:**
- チャット以外の機能（例: 本の検索、推薦履歴閲覧）を使った後、チャットに戻れる
- ユーザー単位で管理するため、複数セッションを持つ場合も一貫性がある
- `lastlogin`を更新することで、アクティブなユーザーは保持される


### 4. サーバー停止時の処理

#### shutdown_event
```python
@self.app.on_event("shutdown")
async def shutdown_event():
    """
    サーバー終了時に全アクティブセッションをpauseして保存。
    """
    logger.info("[INFO] Server shutdown: Pausing active sessions...")
    session_ids = list(self.data_store.sessions.keys())
    
    for session_id in session_ids:
        try:
            conv = self.data_store.conversations.get(session_id)
            if conv and conv.status == ChatStatus.active:
                # active → pause
                conv.status = ChatStatus.pause
                # メモリから削除
                if session_id in self.data_store.sessions:
                    del self.data_store.sessions[session_id]
        except Exception as e:
            logger.error(f"[ERROR] Session pause failed: {session_id}, Error: {e}")
    
    # 一括保存
    self.data_store.save_file()
    logger.info(f"[SUCCESS] Paused {len(session_ids)} session(s)")
```

### 5. 起動時の復元処理

```python
def _restore_paused_sessions(self):
    """
    pauseセッションを復元し、activeに戻す。
    last_accessedを現在時刻に更新。
    そのユーザーも読み込む。
    """
    all_conversations = self._read_json(self.conversations_file)
    all_users = self._read_json(self.users_file)
    restored_count = 0
    
    for session_id, conv_data in all_conversations.items():
        conv = Conversation(**conv_data)
        
        if conv.status == ChatStatus.pause:
            # pause → active
            conv.status = ChatStatus.active
            # last_accessedを現在時刻に更新（すぐにタイムアウトしないように）
            conv.last_accessed = datetime.now()
            
            # メモリに復元
            self.conversations[session_id] = conv
            self.sessions[session_id] = conv.messages
            
            # そのユーザーも読み込む
            user_id = conv.user_id
            if user_id not in self.users and user_id in all_users:
                user_data = all_users[user_id]
                user = User(**user_data)
                # lastloginを現在時刻に更新
                user.lastlogin = datetime.now()
                self.users[user_id] = user
                logger.info(f"[INFO] Loaded user for paused session: {user_id}")
            
            restored_count += 1
    
    if restored_count > 0:
        logger.info(f"[SUCCESS] Restored {restored_count} paused session(s)")
        # 復元後に保存（last_accessed, lastlogin更新を反映）
        self.save_file()
```

## 実装順序

1. **ステータス処理の変更**
   - `check_user_timeout()`: ユーザー単位でタイムアウトチェック（lastlogin基準）
   - `shutdown_event`: active → pause
   - `_restore_paused_sessions()`: pause → active（last_accessed, lastlogin更新、ユーザーも読み込み）

2. **遅延読み込みの実装**
   - `load_user()`: ユーザーデータの遅延読み込み（lastlogin更新）
   - `load_conversation()`: 会話データの遅延読み込み
   - `__init__()`: 最小限の初期化（pauseセッションとそのユーザーのみ）

3. **既存メソッドの修正**
   - `get_user()`: `load_user()`を呼ぶ
   - `has_session()`: `load_conversation()`を呼ぶ
   - `chat_prompt()`: `check_user_timeout()`を呼ぶ（check_session_timeout()から変更）
   - その他の読み込み処理


## 期待される効果

1. **メモリ効率**: 必要なデータのみメモリに保持
2. **スケーラビリティ**: ユーザー数が増えても対応可能
3. **明確なステータス**: pause/closedの役割が明確
4. **起動速度**: pauseセッションのみ読み込むため高速化

## 注意点

> [!WARNING]
> この変更は既存のテストに影響を与える可能性があります。特に以下のテストを更新する必要があります:
> - `test_session_timeout.py`: タイムアウト時の挙動（pause → closed）
> - `test_session_persistence.py`: サーバー再起動時の挙動

> [!IMPORTANT]
> 遅延読み込みにより、存在しないユーザー/セッションへのアクセス時の挙動が変わります。適切なエラーハンドリングが必要です。
