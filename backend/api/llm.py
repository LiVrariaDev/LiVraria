# Standard Library
import os

from typing import Optional, List, Dict, Any, TypedDict, Annotated, Sequence
import logging

# LangChain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# User-defined
from backend import PROMPTS_DIR
from backend.search.rakuten_books import rakuten_search_books

# Logger
logger = logging.getLogger("uvicorn.error")


# State Definition

class AgentState(TypedDict):
	"""エージェントの状態"""
	messages: Annotated[Sequence[BaseMessage], add_messages]
	search_results: Dict[int, dict]  # 検索結果（番号 → 書籍データ）
	recommended_books: List[dict]  # 推薦された書籍


# グローバルステート（ツール間で共有）
_global_state = {
	"search_results": {},
	"recommended_books": []
}

# LLM Initialization

def get_llm(backend: str = None, temperature: float = 0.3, max_tokens: int = 512, system_prompt: Optional[str] = None):
	"""
	LLMインスタンスを取得
	
	Args:
		backend: LLMバックエンド（'gemini' または 'ollama'）
		temperature: 温度パラメータ
		max_tokens: 最大トークン数
		system_prompt: システムプロンプト（オプション）
		
	Returns:
		LangChain LLMインスタンス
	"""
	if backend is None:
		backend = os.getenv("LLM_BACKEND", "gemini")
	
	if backend == "gemini":
		# Geminiの場合、system_instructionとして渡す
		kwargs = {
			"model": "gemini-2.5-flash",
			"temperature": temperature,
			"max_tokens": max_tokens,
			"google_api_key": os.getenv("GEMINI_API_KEY")
		}
		if system_prompt:
			# LangChainのChatGoogleGenerativeAIはsystem_instructionをサポート
			# ただし、メッセージとして渡す必要がある場合もあるため、
			# ここでは含めずに、メッセージリストに追加する方式を採用
			pass
		return ChatGoogleGenerativeAI(**kwargs)
	else:  # ollama
		return ChatOllama(
			model=os.getenv("OLLAMA_MODEL", "llama3.2"),
			base_url=os.getenv("OLLAMA_API_URL", "http://localhost:11434"),
			temperature=temperature,
			num_predict=max_tokens
		)


# Tools Definition

@tool
def search_books(keywords: list[str], count: int = 30) -> str:
	"""
	楽天Books APIを使って書籍を検索
	
	検索結果は番号付きリストで返されます。
	推薦する本を選ぶ際は、この番号を使用してください。
	
	Args:
		keywords: 検索キーワードのリスト（例: ["SF", "初心者", "おすすめ"]）
		count: 取得する書籍数（デフォルト: 10）
		
	Returns:
		番号付き書籍リスト
	"""
	try:
		logger.info(f"[DEBUG] search_books called with keywords: {keywords}, count: {count}")
		
		# キーワードのバリデーション
		if not keywords or not isinstance(keywords, list):
			logger.error(f"[ERROR] Invalid keywords: {keywords}")
			return "検索キーワードが指定されていません。"
		
		# rakuten_search_booksは list[dict] を返す
		books = rakuten_search_books(keywords, count, orflag=0) # AND検索
		
		if not books:
			books = rakuten_search_books(keywords, count=max(count * 2, 30), orflag=1) # OR検索
			if not books:
				logger.error("No books found for keywords: %s", keywords)
				return "申し訳ございません。該当する書籍が見つかりませんでした。"
			
		# グローバルステートに保存（番号 → 書籍データ）
		_global_state["search_results"] = {i+1: book for i, book in enumerate(books)}
		
		# LLMには番号付きリストとして返す
		book_list = []
		for i, book in enumerate(books, 1):
			title = book.get("title", "不明")
			# authorsはリスト形式なので、最初の著者を取得
			authors = book.get("authors", [])
			author = authors[0] if authors else "不明"
			book_list.append(f"{i}. 『{title}』 - {author}")
		
		logger.info(f"[DEBUG] Found {len(books)} books")
		logger.info(f"[DEBUG] Found {len(books)} books")
		return f"検索結果（{len(books)}冊）:\n" + "\n".join(book_list) + "\n\nこれらの結果から、ユーザーに合った本を選び、必ず `recommend_books` を呼び出してください。テキストで検索結果を要約しないでください。もし推薦する本がない場合は、空のリスト `[]` を引数にして `recommend_books` を呼び出してください。"
		
	except Exception as e:
		logger.error(f"[ERROR] search_books error: {e}", exc_info=True)
		return f"検索中にエラーが発生しました: {str(e)}"


@tool
def update_expression(expression_type: str) -> str:
    """
    表情の更新

	司書アバターの表情（感情）を更新します。
    Args:
        expression_type: 'neutral'（通常）', happy'（良い本が見つかった時）, 'thinking'（検索中）, 'sorry'（見つからない時）
    Returns:
		表情の変更の有無のメッセージ
	"""
    # このツール自体はメッセージを返すだけで、
    # 実際のState更新はLangGraphのノード内、またはToolNodeの結果を反映して行います。
    return f"表情を{expression_type}に変更しました。"

@tool
def recommend_books(selections: list[dict]) -> str:
	"""
	検索結果から推薦する本を選択
	
	Args:
		selections: 推薦する本のリスト
			各要素は {"number": 番号, "reason": "推薦理由"} の形式
			例: [{"number": 1, "reason": "初心者向けで分かりやすい"}, {"number": 3, "reason": "実践的な内容"}]
		
	Returns:
		推薦完了メッセージ
	"""
	try:
		recommended = []
		search_results = _global_state.get("search_results", {})
		
		for selection in selections:
			num = selection.get("number")
			reason = selection.get("reason", "")
			
			if num in search_results:
				book = search_results[num].copy()
				book["recommendation_reason"] = reason
				recommended.append(book)
		
		_global_state["recommended_books"] = recommended
		
		if recommended:
			# LLMに返すメッセージを作成（番号を振り直して提示）
			msg_lines = [f"{len(recommended)}冊の本を推薦リストに追加しました。以下の番号と情報を使って、ユーザーに推薦してください。"]
			for i, book in enumerate(recommended, 1):
				msg_lines.append(f"{i}. 『{book['title']}』 (理由: {book['recommendation_reason']})")
			
			return "\n".join(msg_lines)
		else:
			return "推薦する本が選択されませんでした。ユーザーに「条件に合う本が見つかりませんでした」と報告してください。"
			
	except Exception as e:
		return f"推薦処理中にエラーが発生しました: {str(e)}"


# Prompt Management

def load_prompt_text(filepath: str) -> str:
	"""プロンプトファイルを読み込む"""
	with open(filepath, 'r', encoding='utf-8') as f:
		return f.read()


def create_system_prompt(base_prompt: str, ai_insight: Optional[str] = None) -> str:
	"""
	システムプロンプトを作成
	
	Args:
		base_prompt: ベースとなるプロンプト
		ai_insight: ユーザー情報（オプション）
		
	Returns:
		完成したシステムプロンプト
	"""
	# 書籍推薦の指示を追加
	recommendation_instruction = """

## 書籍推薦の手順

1. ユーザーの要望を理解し、適切なキーワードで `search_books` を実行（**20冊以上**検索すること）
2. 検索結果から、ユーザーに最適な本を3冊程度選択
3. `recommend_books` ツールを使って、選んだ本の番号と推薦理由を送信
4. 推薦理由を**簡潔に**説明（1冊あたり1文程度）。詳細は画面に表示されるので不要です。

**重要**: 書籍情報（タイトル、著者など）は検索結果の番号で参照してください。
書籍の詳細情報を自分で作成したり、変更したりしないでください。
"""
	
	full_prompt = base_prompt + recommendation_instruction
	
	if ai_insight and ai_insight.strip():
		full_prompt += f"""

## ユーザー情報
以下は、これまでの会話から学習したユーザーの傾向です。

{ai_insight}
"""
	
	return full_prompt

# LangGraph Workflow

def create_agent_workflow(llm, tools):
	"""エージェントワークフローを作成"""
	
	# ツールをLLMにバインド
	llm_with_tools = llm.bind_tools(tools)
	
	def agent_node(state: AgentState):
		"""エージェントノード: LLMで応答を生成"""
		messages = state["messages"]
		logger.info(f"[DEBUG] agent_node: Received {len(messages)} messages")
		if not messages:
			logger.error("[ERROR] agent_node: Empty messages list!")
			raise ValueError("Messages list is empty in agent_node")
		response = llm_with_tools.invoke(messages)
		return {"messages": [response]}

	def force_tool_node(state: AgentState):
		"""強制的にツール呼び出しを促すノード"""
		logger.info("[DEBUG] force_tool_node: Enforcing recommend_books call")
		message = HumanMessage(content="検索結果から本を選んで、必ず `recommend_books` を呼び出してください。もし推薦する本がない場合は、空のリスト `[]` を引数にしてください。")
		return {"messages": [message]}
	
	def should_continue(state: AgentState):
		"""次のノードを決定"""
		messages = state["messages"]
		last_message = messages[-1]
		
		# ツール呼び出しがある場合
		if hasattr(last_message, "tool_calls") and last_message.tool_calls:
			return "tools"
			
		# 直前が検索結果(ToolMessage)で、今回ツール呼び出しをしなかった場合
		if len(messages) >= 2:
			second_last = messages[-2]
			# ToolMessageかつ、search_booksの結果である場合（nameはToolNodeが設定する）
			if isinstance(second_last, ToolMessage) and second_last.name == "search_books":
				return "force_tool"
				
		return "end"
	
	# グラフ構築
	workflow = StateGraph(AgentState)
	
	# ノード追加
	workflow.add_node("agent", agent_node)
	workflow.add_node("tools", ToolNode(tools))
	workflow.add_node("force_tool", force_tool_node)
	
	# エントリーポイント設定
	workflow.set_entry_point("agent")
	
	# エッジ追加
	workflow.add_conditional_edges(
		"agent",
		should_continue,
		{
			"tools": "tools",
			"force_tool": "force_tool",
			"end": END
		}
	)
	workflow.add_edge("tools", "agent")
	workflow.add_edge("force_tool", "agent")
	
	return workflow.compile()


# Chat Functions

def llm_chat(
	prompt_file: str,
	message: str,
	history: Optional[List[BaseMessage]] = None,
	ai_insight: Optional[str] = None,
	model: Optional[str] = None,
	temperature: float = 0.3,
	max_tokens: int = 512
) -> tuple[str, List[BaseMessage], List[dict]]:
	"""
	LangGraphを使ったチャット対話
	
	Args:
		prompt_file: プロンプトファイルのパス
		message: ユーザーメッセージ
		history: 会話履歴 (List[BaseMessage])
		ai_insight: ユーザー情報
		model: 使用するLLMバックエンド
		temperature: 温度パラメータ
		max_tokens: 最大トークン数
		
	Returns:
		(応答テキスト, 更新された履歴(List[BaseMessage]), 推薦された書籍リスト)
	"""
	# グローバルステートをクリア
	_global_state["search_results"] = {}
	_global_state["recommended_books"] = []
	
	# プロンプト読み込み
	base_prompt = load_prompt_text(prompt_file)
	system_prompt = create_system_prompt(base_prompt, ai_insight)
	
	# LLM初期化
	llm = get_llm(backend=model, temperature=temperature, max_tokens=max_tokens)
	
	# ツール定義
	tools = [search_books, recommend_books]
	
	# ワークフロー作成
	app = create_agent_workflow(llm, tools)
	
	# メッセージ履歴を準備
	if history is None:
		history = []
	
	# historyは既にList[BaseMessage]なのでそのまま使用可能
	# ただし、Geminiの場合はSystemMessageの使用方法に注意が必要だが、
	# ここではHumanMessage/AIMessageのリストとして扱う
	
	# メッセージリストを構築
	if not history:
		# 履歴がない場合: システムプロンプトを最初のメッセージに含める
		first_message = f"{system_prompt}\n\n---\n\nユーザー: {message}"
		# HumanMessageオブジェクトを作成
		current_message = HumanMessage(content=first_message)
		messages = [current_message]
		logger.info(f"[DEBUG] No history, created first message with system prompt")
	else:
		# 履歴がある場合: システムプロンプトは最初の会話で既に送信済みなので、通常のメッセージのみ
		current_message = HumanMessage(content=message)
		messages = history + [current_message]
		logger.info(f"[DEBUG] With history, messages count: {len(messages)}")
	
	logger.info(f"[DEBUG] Final messages for LangGraph: {len(messages)} messages")
	
	# ワークフロー実行
	try:
		result = app.invoke({
			"messages": messages,
			"search_results": {},
			"recommended_books": []
		})
		
		# 最後のAIメッセージを取得
		ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
		if ai_messages:
			last_message = ai_messages[-1]
			# contentが文字列でない場合の処理
			if isinstance(last_message.content, str):
				response_text = last_message.content
			elif isinstance(last_message.content, list):
				# contentがリストの場合、テキスト部分を抽出
				text_parts = []
				for part in last_message.content:
					if isinstance(part, dict) and 'text' in part:
						text_parts.append(part['text'])
					elif isinstance(part, str):
						text_parts.append(part)
				response_text = ''.join(text_parts) if text_parts else str(last_message.content)
			else:
				response_text = str(last_message.content)
			
			# 空の応答の場合のフォールバック
			if not response_text.strip():
				logger.warning("[WARNING] Empty response from LLM")
				response_text = "申し訳ございません。応答を生成できませんでした（空の応答）。"
		else:
			response_text = "申し訳ございません。応答を生成できませんでした。"
			logger.error("No AI message found in result: %s", result)
		
		# ツール呼び出しから表情を取得（なければ none）  
		current_expression = "none"
		for msg in result["messages"]:
			if hasattr(msg, "tool_calls") and msg.tool_calls:
				for tool_call in msg.tool_calls:
					if tool_call["name"] == "update_expression":
						current_expression = tool_call["args"]["expression_type"]

		# 履歴を更新 (BaseMessageオブジェクトのリスト)
		# ユーザーメッセージ追加済みリスト + AI応答
		# 注意: messages は既に [history + current_message] なので、これにAI応答を追加する形にはならない
		# messages[-1] は最後のアクションの結果かもしれないので、
		# 単純に history + [current_message] + [ai_message] を返すのが安全
		
		# AI応答メッセージオブジェクト作成
		ai_message = AIMessage(content=response_text)

		# 応答に関数名が含まれる場合（ツール呼び出しの幻覚など）、エラーメッセージにする
		# 再帰呼び出しは無限ループのリスクがあるため、安全なフォールバックメッセージを返す
		if "search_books" in response_text or "recommend_books" in response_text:
			logger.warning("[WARNING] Response contains raw function name, replacing with fallback message.")
			response_text = "申し訳ございません。応答の生成中にエラーが発生しました。もう一度お試しください。"
			ai_message = AIMessage(content=response_text)
		
		updated_history = history + [current_message, ai_message]
		
		# 推薦された書籍を取得
		recommended_books = _global_state.get("recommended_books", [])
		
		return response_text, updated_history, recommended_books, current_expression
		
	except Exception as e:
		import traceback
		traceback.print_exc()
		
		error_message = "申し訳ございません。応答を生成できませんでした。"
		logger.error(f"Error in llm_chat: {e}")
		
		# エラー時も履歴オブジェクトを返す
		ai_message = AIMessage(content=error_message)
		if 'current_message' in locals():
			updated_history = history + [current_message, ai_message]
		else:
			updated_history = history + [AIMessage(content=error_message)]
			
		# errorログは別で保存する → クライアント側に返すと脆弱
		return error_message, updated_history, [], "none"


def llm_summary(
	prompt_file: str,
	message: str,
	ai_insight: Optional[str] = None,
	model: Optional[str] = None,
	temperature: float = 0.3,
	max_tokens: int = 512
) -> str:
	"""
	LangChainを使った要約生成（履歴なし）
	
	Args:
		prompt_file: プロンプトファイルのパス
		message: ユーザーメッセージ
		ai_insight: ユーザー情報
		model: 使用するLLMバックエンド
		temperature: 温度パラメータ
		max_tokens: 最大トークン数
		
	Returns:
		要約テキスト
	"""
	# プロンプト読み込み
	base_prompt = load_prompt_text(prompt_file)
	system_prompt = create_system_prompt(base_prompt, ai_insight)
	
	# LLM初期化
	llm = get_llm(backend=model, temperature=temperature, max_tokens=max_tokens)
	
	# メッセージ作成
	messages = [
		SystemMessage(content=system_prompt),
		HumanMessage(content=message)
	]
	
	# LLM実行
	try:
		response = llm.invoke(messages)
		return response.content
	except Exception as e:
		print(f"Error in llm_summary: {e}")
		return f"エラーが発生しました: {str(e)}"


# Main (for testing)

if __name__ == "__main__":
	# テスト用
	test_message = "Pythonの機械学習に関する本を教えてください"
	
	# プロンプトファイルのパスを設定（適宜変更）
	from backend import PROMPT_LIBRARIAN
	
	print("Testing LangGraph LLM chat...")
	# historyはBaseMessageのリスト
	response, history, recommended_books = llm_chat(
		prompt_file=str(PROMPT_LIBRARIAN),
		message=test_message,
		history=[]
	)
	
	print(f"\nResponse:\n{response}")
	print(f"\nHistory length: {len(history)}")
	print(f"\nRecommended books: {len(recommended_books)}")
	
	if recommended_books:
		print("\n推薦された書籍:")
		for book in recommended_books:
			print(f"  - {book.get('title')} ({book.get('recommendation_reason')})")
