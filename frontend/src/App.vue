<template>
    <div class="w-screen h-screen">

        <!-- ===== ホームページ表示 ===== -->
        <div v-if="currentPage === 'home'" class="relative flex w-full h-full p-8">
            <!-- 左側: アバターと会話エリア -->
            <div class="w-1/3 flex flex-col items-center justify-center">
                <div class="relative">
                    <div class="avatar-shape flex items-center justify-center">
                        <span class="text-gray-500 text-lg">アバター</span>
                    </div>
                    <div class="speech-bubble flex items-center justify-center text-center">
                        <p v-if="!isLoading" class="font-bold text-gray-800" v-html="homeConversationText"></p>
                        <p v-else class="font-bold text-gray-500 italic">考え中...</p>
                    </div>
                </div>
            </div>

            <!-- 右側: ボタンエリア -->
            <div class="w-2/3 flex flex-col justify-center pl-10">
                <div class="grid grid-cols-2 gap-6 max-w-lg">
                    <button v-for="button in mainButtons" :key="button.id" 
                            @click="handleHomeButtonClick(button.action)"
                            class="bg-blue-400 hover:bg-blue-500 text-white font-semibold py-6 px-4 rounded-lg shadow-md transition-transform transform hover:scale-105">
                        {{ button.text }}
                    </button>
                </div>
            </div>

            <!-- 下部: 入力とオプションエリア -->
            <div class="absolute bottom-0 left-0 right-0 bg-white/70 backdrop-blur-sm p-4 flex items-center shadow-t-lg">
                <div class="flex-grow mx-8">
                    <input type="text" v-model="userInput" @keydown.enter.prevent="sendHomeMessage" placeholder="テキストを入力してEnterキーを押してください"
                           class="w-full bg-gray-100 border-2 border-gray-300 rounded-lg py-3 px-4 focus:outline-none focus:border-blue-500">
                </div>
                <div class="flex space-x-4 mr-8">
                     <button v-for="button in utilityButtons" :key="button.id"
                             @click="handleHomeButtonClick(button.action)"
                             class="bg-gray-500 hover:bg-gray-600 text-white font-semibold py-3 px-8 rounded-lg shadow-md transition-colors">
                        {{ button.text }}
                    </button>
                </div>
            </div>
        </div>

        <!-- ===== 会話集中モード表示 ===== -->
        <div v-if="currentPage === 'chat_mode'" class="flex flex-col h-screen bg-gray-100">
            <!-- ヘッダー -->
            <header class="bg-white shadow-md p-4 flex justify-between items-center">
                <h1 class="text-2xl font-bold text-gray-800">会話集中モード</h1>
                <div>
                    <button @click="openSecondaryDisplay" class="bg-teal-500 hover:bg-teal-600 text-white font-bold py-2 px-4 rounded-lg transition-colors mr-4">
                        動画ウィンドウを再表示
                    </button>
                    <button @click="currentPage = 'home'" class="bg-indigo-500 hover:bg-indigo-600 text-white font-bold py-2 px-4 rounded-lg transition-colors">
                        ホームに戻る
                    </button>
                </div>
            </header>

            <!-- メインコンテンツ -->
            <div class="flex flex-1 overflow-hidden">
                <!-- 左側: チャット画面 -->
                <div class="w-1/2 flex flex-col p-4">
                    <div ref="chatHistoryEl" class="flex-1 bg-white rounded-lg p-4 overflow-y-auto custom-scrollbar">
                         <div v-for="(msg, index) in chatHistory" :key="index" class="mb-4 flex" :class="msg.sender === 'user' ? 'justify-end' : 'justify-start'">
                            <div class="chat-bubble rounded-lg px-4 py-2" :class="msg.sender === 'user' ? 'user-bubble' : 'ai-bubble'">
                                <p class="text-gray-800">{{ msg.text }}</p>
                            </div>
                        </div>
                    </div>
                    <div class="mt-4 flex">
                        <input type="text" v-model="userInput" @keydown.enter="sendChatMessage" placeholder="メッセージを入力..." class="flex-1 p-3 border-2 border-gray-300 rounded-l-lg focus:outline-none focus:border-indigo-500">
                        <button @click="sendChatMessage" class="bg-indigo-500 text-white px-6 rounded-r-lg font-semibold hover:bg-indigo-600">送信</button>
                    </div>
                </div>

                <!-- 右側: 書籍候補 -->
                <div class="w-1/2 p-4 flex flex-col">
                    <div class="bg-white rounded-lg shadow p-4 flex-1">
                        <h2 class="text-xl font-semibold mb-4 text-center">AIからのおすすめ書籍</h2>
                        <div class="grid grid-cols-3 gap-4">
                            <div v-for="book in suggestedBooks" :key="book.id" @click="selectBook(book.id)"
                                 class="book-card border-2 rounded-lg p-2 cursor-pointer bg-gray-50 hover:shadow-lg"
                                 :class="{ 'selected': selectedBook?.id === book.id }">
                                <img :src="book.cover" :alt="book.title" class="w-full h-40 object-cover rounded-md mb-2">
                                <h3 class="font-bold text-sm text-center">{{ book.title }}</h3>
                            </div>
                        </div>
                    </div>
                     <button @click="askAboutBook" :disabled="!selectedBook"
                            class="mt-4 w-full bg-green-500 text-white font-bold py-3 rounded-lg shadow-md hover:bg-green-600 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors">
                        この本について教えて
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue';

// --- リアクティブな状態定義 ---
const currentPage = ref('home'); // 'home' or 'chat_mode'
const userInput = ref('');
const isLoading = ref(false);
const secondaryWindow = ref(null); // 二次ディスプレイのウィンドウを管理

// --- ホームページ用データ ---
const homeConversationText = ref('こんにちは！<br>何かお探しですか？');
const mainButtons = ref([
    { id: 1, text: '書籍検索ボタン', action: 'search' },
    { id: 2, text: '会話集中モード(?)', action: 'focus_chat' },
    { id: 3, text: 'ライブラリーサーフィン', action: 'library_surfing' },
    { id: 4, text: 'グッドスナイパー', action: 'good_sniper' },
]);
const utilityButtons = ref([
    { id: 5, text: 'ログイン', action: 'login' },
    { id: 6, text: 'オプション', action: 'options' },
]);

// --- 会話集中モード用データ ---
const chatHistory = ref([
    { sender: 'ai', text: 'こんにちは！ここでは、より詳しくお話を伺いながら、あなたにぴったりの本を探すお手伝いをします。' },
    { sender: 'ai', text: 'どんなことに興味がありますか？' },
]);
const suggestedBooks = ref(Array.from({ length: 6 }, (_, i) => ({
    id: i + 1,
    title: `本のタイトル ${i + 1}`,
    cover: `https://placehold.co/150x200/a3e635/ffffff?text=Book${i+1}`
})));
const selectedBook = ref(null);
const chatHistoryEl = ref(null); // チャット履歴のDOM要素への参照

// --- メソッド定義 ---

// ===== 二次ディスプレイ制御 =====
function openSecondaryDisplay() {
    if (secondaryWindow.value && !secondaryWindow.value.closed) {
        secondaryWindow.value.focus();
        return;
    }
    // ローカル環境では、publicフォルダ内のファイルを直接参照できます
    secondaryWindow.value = window.open('/secondary_display.html', 'LivrariaSecondaryDisplay', 'width=1280,height=720');
    
    if (!secondaryWindow.value) {
        alert('ポップアップウィンドウがブロックされました。ブラウザのポップアップブロックを解除してください。');
        homeConversationText.value = '動画ウィンドウが<br>ブロックされました。<br>ポップアップを許可してください。';
    }
}

// ===== ホームページ用メソッド =====
function handleHomeButtonClick(action) {
    console.log(`Action: '${action}' button was clicked.`);
    if (action === 'focus_chat') {
        currentPage.value = 'chat_mode';
    } else {
        homeConversationText.value = `「${action}」ですね。了解しました！`;
    }
}
async function sendHomeMessage() {
    console.log("Home message sent:", userInput.value);
    homeConversationText.value = 'API設定後、会話が可能になります。';
    userInput.value = '';
}

// ===== 会話集中モード用メソッド =====
function sendChatMessage() {
    if (!userInput.value.trim()) return;
    chatHistory.value.push({ sender: 'user', text: userInput.value });
    
    isLoading.value = true;
    setTimeout(() => {
        const aiResponse = `「${userInput.value}」についてですね。承知いたしました。何かおすすめの本をお探ししますね。`;
        chatHistory.value.push({ sender: 'ai', text: aiResponse });
        isLoading.value = false;
        scrollToBottom();
    }, 1000);
    
    userInput.value = '';
    scrollToBottom();
}
function selectBook(bookId) {
    selectedBook.value = suggestedBooks.value.find(b => b.id === bookId);
    console.log(`Book ${bookId} selected.`);
}
function askAboutBook() {
    if (!selectedBook.value) return;
    const book = selectedBook.value;
    const question = `「${book.title}」についてですね。AIが詳細を調べてお答えします。`;
    chatHistory.value.push({ sender: 'ai', text: question });
    scrollToBottom();
}
async function scrollToBottom() {
    // DOMの更新を待ってからスクロールを実行
    await nextTick();
    if(chatHistoryEl.value) {
       chatHistoryEl.value.scrollTop = chatHistoryEl.value.scrollHeight;
    }
}

// ===== ライフサイクルフック =====
onMounted(() => {
    // アプリケーションがマウントされた時に二次ディスプレイを開く
    openSecondaryDisplay();
});

</script>

<style>
/* フォントの読み込み */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
body {
    font-family: 'Inter', 'Noto Sans JP', sans-serif;
    overflow: hidden;
}

/* --- 共通スタイル --- */
.grid-background {
    background-color: #f0f4f8;
    background-image:
        linear-gradient(rgba(17, 24, 39, 0.1) 1px, transparent 1px),
        linear-gradient(90deg, rgba(17, 24, 39, 0.1) 1px, transparent 1px);
    background-size: 20px 20px;
}

/* --- ホームページ用スタイル --- */
.avatar-shape {
    width: 200px;
    height: 350px;
    background-color: #e0e7ff;
    border: 3px solid #6366f1;
    border-radius: 50% 50% 30% 30% / 60% 60% 40% 40%;
    position: relative;
}
.speech-bubble {
    position: absolute; top: -20px; left: 50%; transform: translateX(-50%);
    background: #ffffff; border-radius: .4em; padding: 15px 25px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: max-content;
    max-width: 300px; min-height: 58px;
}
.speech-bubble:after {
    content: ''; position: absolute; bottom: 0; left: 50%;
    width: 0; height: 0; border: 20px solid transparent;
    border-top-color: #ffffff; border-bottom: 0; border-left: 0;
    margin-left: -10px; margin-bottom: -20px;
}

/* --- 会話集中モード用スタイル --- */
.chat-bubble { max-width: 80%; }
.user-bubble { background-color: #dbeafe; }
.ai-bubble { background-color: #e5e7eb; }
.book-card { transition: all 0.2s ease-in-out; }
.book-card.selected {
    transform: scale(1.05);
    box-shadow: 0 0 0 4px #60a5fa;
    border-color: #60a5fa;
}
/* スクロールバーのスタイル */
.custom-scrollbar::-webkit-scrollbar { width: 8px; }
.custom-scrollbar::-webkit-scrollbar-track { background: #f1f1f1; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #888; border-radius: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #555; }
</style>