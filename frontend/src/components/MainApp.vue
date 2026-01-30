<template>
    <div class="w-screen h-screen font-sans text-gray-800 bg-gray-900">

        <!-- ===== 診断用（画面には表示されませんが、裏で画像をチェックします） ===== -->
        <img 
            src="/bg.jpg" 
            style="display: none;" 
            @error="handleImageError" 
            @load="handleImageLoad"
        />

        <!-- ===== ホームページ表示 ===== -->
        <div v-if="currentPage === 'home'" class="relative flex w-full h-full overflow-hidden">
            <!-- 背景画像エリア -->
            <div class="absolute inset-0 z-0 bg-cover bg-center transition-all duration-700"
                 :style="{ backgroundImage: `linear-gradient(rgba(0, 0, 0, 0.6), rgba(0, 0, 0, 0.6)), url('/bg.jpg?v=2')` }">
            </div>

            <!-- 左側: アバターと会話エリア -->
            <div class="relative z-10 w-1/3 flex flex-col items-center justify-center p-8">
                <div class="relative group">
                    <!-- アバター本体 -->
                    <div class="avatar-container relative w-64 h-80 flex items-center justify-center transition-transform duration-500">
                        <div class="avatar-glow absolute inset-0 bg-gradient-to-tr from-blue-400 to-purple-400 rounded-[60%_40%_30%_70%/60%_30%_70%_40%] blur-xl opacity-30 animate-pulse-slow"></div>
                        <div class="avatar-shape w-full h-full bg-gradient-to-br from-white to-blue-50 border-4 border-blue-200 shadow-2xl flex items-center justify-center overflow-hidden relative animate-float">
                            <svg class="w-32 h-32 text-blue-300 opacity-50" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/>
                            </svg>
                        </div>
                    </div>
                    
                    <!-- 吹き出し -->
                    <div class="speech-bubble absolute -top-12 left-1/2 transform -translate-x-1/2 bg-white/90 backdrop-blur border border-blue-100 rounded-2xl p-6 shadow-lg min-w-[280px] text-center z-20 transition-all duration-300 hover:scale-105">
                        <p v-if="isRecording" class="font-bold text-red-500 animate-pulse">
                            🎤 お話しください...
                        </p>
                        <p v-else-if="!isLoading" class="font-medium text-gray-700 leading-relaxed" v-html="homeConversationText"></p>
                        <div v-else class="flex justify-center items-center space-x-2 h-6">
                            <div class="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></div>
                            <div class="w-2 h-2 bg-blue-400 rounded-full animate-bounce delay-75"></div>
                            <div class="w-2 h-2 bg-blue-400 rounded-full animate-bounce delay-150"></div>
                        </div>
                        <div class="absolute -bottom-3 left-1/2 transform -translate-x-1/2 w-6 h-6 bg-white border-b border-r border-blue-100 rotate-45"></div>
                    </div>
                </div>
            </div>

            <!-- 右側: ボタンエリア -->
            <div class="relative z-10 w-2/3 flex flex-col justify-center px-16">
                <h1 class="text-4xl font-bold text-white mb-8 tracking-tight drop-shadow-md">Main Menu</h1>
                <div class="grid grid-cols-2 gap-6 max-w-2xl">
                    <button v-for="button in mainButtons" :key="button.id" 
                            @click="handleHomeButtonClick(button.action)"
                            class="group relative overflow-hidden bg-white/90 backdrop-blur-sm p-6 rounded-2xl shadow-lg hover:shadow-2xl border border-white/50 transition-all duration-300 hover:-translate-y-1 text-left">
                        <div class="absolute top-0 right-0 w-24 h-24 bg-gradient-to-br from-blue-50 to-transparent rounded-bl-full opacity-50 transition-transform group-hover:scale-150"></div>
                        <div class="relative z-10 flex items-center space-x-4">
                            <div class="p-3 rounded-lg bg-blue-50 text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-colors duration-300">
                                <span v-if="button.icon === 'search'" v-html="icons.search"></span>
                                <span v-else-if="button.icon === 'chat'" v-html="icons.chat"></span>
                                <span v-else-if="button.icon === 'grid'" v-html="icons.grid"></span>
                                <span v-else v-html="icons.star"></span>
                            </div>
                            <span class="text-lg font-bold text-slate-700 group-hover:text-blue-600 transition-colors">{{ button.text }}</span>
                        </div>
                    </button>
                </div>
            </div>

            <!-- 下部: 入力とオプションエリア -->
            <div class="absolute bottom-0 left-0 right-0 bg-white/80 backdrop-blur-md border-t border-white/20 p-6 flex items-center shadow-lg z-20">
                <div class="flex-grow mx-8 relative flex items-center">
                    <button @click="toggleSpeechRecognition" 
                            class="mr-2 p-3 rounded-full transition-colors duration-200 focus:outline-none"
                            :class="isRecording ? 'bg-red-500 text-white hover:bg-red-600 animate-pulse' : 'bg-gray-200 text-gray-600 hover:bg-gray-300'">
                        <svg v-if="!isRecording" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"></path></svg>
                        <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"/></svg>
                    </button>

                    <input type="text" v-model="userInput" @keydown.enter.prevent="sendHomeMessage" 
                           placeholder="AI司書に話しかける..."
                           class="w-full bg-white/80 border border-slate-300 rounded-full py-4 px-6 pl-6 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all shadow-inner text-lg">
                </div>
                <div class="flex space-x-4 mr-8 items-center">
                      <!-- 動画ウィンドウボタン -->
                      <button @click="openSecondaryDisplay" class="flex items-center px-4 py-3 bg-teal-50 hover:bg-teal-100 text-teal-700 font-semibold rounded-full transition-colors duration-200 border border-teal-200 shadow-sm">
                        <span class="mr-2">📺</span> 動画ウィンドウ
                      </button>

                      <button @click="toggleSpeech" class="flex items-center px-4 py-3 mr-2 bg-white hover:bg-slate-100 text-slate-600 font-semibold rounded-full transition-colors duration-200 shadow-sm" :class="{'text-blue-500': isSpeechEnabled}">
                        <span v-if="isSpeechEnabled">🔊 ON</span>
                        <span v-else>🔇 OFF</span>
                      </button>

                      <button v-for="button in utilityButtons" :key="button.id"
                             @click="handleHomeButtonClick(button.action)"
                             class="flex items-center px-6 py-3 bg-white hover:bg-slate-100 text-slate-600 font-semibold rounded-full transition-colors duration-200 shadow-sm">
                        <span class="mr-2">⚙️</span> {{ button.text }}
                    </button>
                    <button @click="logout" class="flex items-center px-6 py-3 bg-red-50 hover:bg-red-100 text-red-600 font-semibold rounded-full transition-colors duration-200 border border-red-200 shadow-sm">
                        <span>🚪</span> ログアウト
                    </button>
                </div>
            </div>
        </div>

        <!-- ===== 会話集中モード表示 ===== -->
        <div v-if="currentPage === 'chat_mode'" class="flex flex-col h-screen bg-slate-50">
            <header class="bg-white/90 backdrop-blur border-b border-slate-200 p-4 px-8 flex justify-between items-center shadow-sm z-20">
                <div class="flex items-center space-x-3">
                    <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center text-white font-bold text-lg shadow">L</div>
                    <h1 class="text-xl font-bold text-slate-700">会話集中モード</h1>
                </div>
                <div class="flex space-x-3">
                    <button @click="openSecondaryDisplay" class="flex items-center space-x-2 bg-teal-50 hover:bg-teal-100 text-teal-700 font-semibold py-2 px-4 rounded-lg transition-colors border border-teal-200">
                        <span class="text-lg">📺</span> <span>動画ウィンドウ</span>
                    </button>
                    <button @click="currentPage = 'home'" class="flex items-center space-x-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold py-2 px-4 rounded-lg transition-colors">
                        <span>🏠</span> <span>ホームへ</span>
                    </button>
                </div>
            </header>

            <div class="flex flex-1 overflow-hidden">
                <!-- 左側: チャット画面 -->
                <div class="w-1/2 flex flex-col border-r border-slate-200 bg-white">
                    <div ref="chatHistoryEl" class="flex-1 p-6 overflow-y-auto custom-scrollbar space-y-6">
                         <div v-for="(msg, index) in chatHistory" :key="index" class="flex" :class="msg.sender === 'user' ? 'justify-end' : 'justify-start'">
                            <div class="max-w-[80%] rounded-2xl px-6 py-4 shadow-sm text-base leading-relaxed" 
                                 :class="msg.sender === 'user' ? 'bg-blue-600 text-white rounded-br-none' : 'bg-slate-100 text-slate-800 rounded-bl-none border border-slate-200'">
                                <p>{{ msg.text }}</p>
                            </div>
                        </div>
                        <div v-if="isLoading" class="flex justify-start">
                            <div class="bg-slate-100 rounded-2xl rounded-bl-none px-6 py-4 flex space-x-2 items-center">
                                <div class="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
                                <div class="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-75"></div>
                                <div class="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-150"></div>
                            </div>
                        </div>
                    </div>
                    <div class="p-6 bg-white border-t border-slate-100">
                        <div class="relative flex items-center">
                            <button @click="toggleSpeechRecognition" 
                                    class="mr-2 p-3 rounded-full transition-colors duration-200 focus:outline-none"
                                    :class="isRecording ? 'bg-red-500 text-white hover:bg-red-600 animate-pulse' : 'bg-gray-200 text-gray-600 hover:bg-gray-300'">
                                <svg v-if="!isRecording" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"></path></svg>
                                <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"/></svg>
                            </button>

                            <input type="text" v-model="userInput" @keydown.enter="sendChatMessage" placeholder="メッセージを入力..." 
                                   class="w-full bg-slate-50 border border-slate-300 rounded-xl py-4 pl-6 pr-32 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all">
                            <button @click="sendChatMessage" 
                                    class="absolute right-2 top-2 bottom-2 bg-blue-600 text-white px-6 rounded-lg font-semibold hover:bg-blue-700 transition-colors shadow-md">
                                送信
                            </button>
                        </div>
                        <div class="flex justify-end mt-2">
                             <button @click="toggleSpeech" class="text-sm font-semibold transition-colors duration-200" :class="isSpeechEnabled ? 'text-blue-500' : 'text-gray-400'">
                                <span v-if="isSpeechEnabled">🔊 読み上げ ON</span>
                                <span v-else>🔇 読み上げ OFF</span>
                             </button>
                        </div>
                    </div>
                </div>

                <div class="w-1/2 p-6 flex flex-col bg-slate-50">
                    <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 flex-1 flex flex-col overflow-hidden">
                        <h2 class="text-lg font-bold text-slate-700 mb-6 flex items-center">
                            <span class="mr-2 text-2xl">📚</span> AIからのおすすめ書籍
                        </h2>
                        <div class="flex-1 overflow-y-auto custom-scrollbar pr-2">
                            <div class="grid grid-cols-3 gap-6">
                                <div v-for="book in suggestedBooks" :key="book.id" @click="selectBook(book.id)"
                                     class="group cursor-pointer flex flex-col items-center"
                                     :class="{ 'scale-105': selectedBook?.id === book.id }">
                                    <div class="relative w-full aspect-[2/3] rounded-lg overflow-hidden shadow-md group-hover:shadow-xl transition-all duration-300 border-2"
                                         :class="selectedBook?.id === book.id ? 'border-blue-500 ring-4 ring-blue-100' : 'border-transparent'">
                                        <img :src="book.cover" :alt="book.title" class="w-full h-full object-cover transform group-hover:scale-110 transition-transform duration-500">
                                        <div class="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors"></div>
                                    </div>
                                    <h3 class="mt-3 font-bold text-sm text-slate-700 text-center group-hover:text-blue-600 transition-colors line-clamp-2">{{ book.title }}</h3>
                                </div>
                            </div>
                        </div>
                    </div>
                     <button @click="askAboutBook" :disabled="!selectedBook"
                            class="mt-6 w-full bg-gradient-to-r from-emerald-500 to-teal-500 text-white font-bold py-4 rounded-xl shadow-lg hover:shadow-xl hover:from-emerald-600 hover:to-teal-600 disabled:from-slate-300 disabled:to-slate-300 disabled:cursor-not-allowed transition-all transform active:scale-95 flex items-center justify-center">
                        <span class="mr-2 text-xl">📖</span> この本について詳しく聞く
                    </button>
                </div>
            </div>
        </div>

        <!-- ===== 蔵書検索モード表示 ===== -->
        <div v-if="currentPage === 'search_mode'" class="flex flex-col h-screen bg-slate-50">
            <header class="bg-white/90 backdrop-blur border-b border-slate-200 p-4 px-8 flex justify-between items-center shadow-sm z-20">
                <div class="flex items-center space-x-3">
                    <span class="text-2xl">📚</span>
                    <h1 class="text-xl font-bold text-slate-700">蔵書検索</h1>
                </div>
                <div class="flex space-x-3">
                    <button @click="currentPage = 'home'" class="flex items-center space-x-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold py-2 px-4 rounded-lg transition-colors">
                        <span>🏠</span> <span>ホームへ</span>
                    </button>
                </div>
            </header>
            
            <div class="flex-1 overflow-auto">
                <BookSearch />
            </div>
        </div>

    </div>
</template>

<script setup>
import { ref, onMounted, nextTick, onUnmounted } from 'vue';
import { signOut, getIdToken } from "firebase/auth";
import { auth } from '../firebaseConfig';
import { api } from '../services/api'; 
// ★追加: 蔵書検索コンポーネントをインポート
import BookSearch from './BookSearch.vue';

// --- 診断用関数 ---
const handleImageError = () => {
    alert("【画像読み込みエラー】\n publicフォルダに 'bg.jpg' が見つかりません。");
};
const handleImageLoad = () => {
    console.log("画像の読み込みに成功しました！");
};
// ----------------

// --- 音声合成の実装（女性ボイス固定） ---
const isSpeechEnabled = ref(true);
const selectedVoice = ref(null);

const loadVoices = () => {
    const voices = window.speechSynthesis.getVoices();
    if (voices.length > 0) {
        const jaVoices = voices.filter(voice => voice.lang.includes('ja'));
        if (jaVoices.length > 0) {
            const priorityNames = ['Google 日本語', 'Microsoft Nanami', 'Kyoko', 'O-Ren', 'Microsoft Haruka'];
            let bestVoice = null;
            for (const name of priorityNames) {
                bestVoice = jaVoices.find(v => v.name.includes(name));
                if (bestVoice) break;
            }
            selectedVoice.value = bestVoice || jaVoices[0];
        }
    }
};
window.speechSynthesis.onvoiceschanged = loadVoices;

const toggleSpeech = () => {
    isSpeechEnabled.value = !isSpeechEnabled.value;
    if (!isSpeechEnabled.value) {
        window.speechSynthesis.cancel();
    }
};

const speakText = (text) => {
    if (!text) return;
    if (!isSpeechEnabled.value) return;
    if (!window.speechSynthesis) return;
    // 修正：テキストが空の場合は何もしない（undefinedエラー回避）
    if (!text) return;

    if (!selectedVoice.value) loadVoices();

    // 修正：文字列であることを確認してからreplaceする
    const plainText = typeof text === 'string' ? text.replace(/<[^>]+>/g, '') : '';
    
    if (!plainText) return; // 空なら終了

    const utterance = new SpeechSynthesisUtterance(plainText);
    if (selectedVoice.value) utterance.voice = selectedVoice.value;
    utterance.lang = 'ja-JP';
    utterance.rate = 1.0;
    utterance.pitch = 1.0; 
    utterance.volume = 1.0;
    window.speechSynthesis.speak(utterance);
};
// ---------------------

const icons = {
    search: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>`,
    chat: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>`,
    grid: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg>`,
    star: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"></path></svg>`
};

const currentPage = ref('home');
const userInput = ref('');
const isLoading = ref(false);
const secondaryWindow = ref(null);
const homeConversationText = ref('AI司書に接続中...');
const currentSessionId = ref(null); 
const mainButtons = ref([ 
    { id: 1, text: '書籍検索', action: 'search', icon: 'search' }, 
    { id: 2, text: '会話集中モード', action: 'focus_chat', icon: 'chat' }, 
    { id: 3, text: 'ライブラリーサーフィン', action: 'library_surfing', icon: 'grid' }, 
    { id: 4, text: 'グッドスナイパー', action: 'good_sniper', icon: 'star' }
]);
const utilityButtons = ref([ { id: 6, text: 'オプション', action: 'options' } ]); 
const chatHistory = ref([ 
    { sender: 'ai', text: 'こんにちは！AI司書です。本日はどのようなご用件でしょうか？' }
]);
const suggestedBooks = ref(Array.from({ length: 6 }, (_, i) => ({ id: i + 1, title: `未来の図書館 ${i + 1}`, cover: `https://placehold.co/150x220/3b82f6/ffffff?text=Book${i+1}` })));
const selectedBook = ref(null);
const chatHistoryEl = ref(null);

const channel = new BroadcastChannel('livraria_channel'); // チャンネル作成

const openSecondaryDisplay = () => {
    if (secondaryWindow.value && !secondaryWindow.value.closed) {
        secondaryWindow.value.focus();
        return;
    }
    const leftPosition = window.screen.width; 
    const width = window.screen.availWidth;
    const height = window.screen.availHeight;
    const features = `left=${leftPosition},top=0,width=${width},height=${height},menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=no`;
    secondaryWindow.value = window.open('/?view=secondary', 'LivrariaSecondaryDisplay', features);
};

const sendMessageToSecondary = (text, state = 'speaking') => {
    channel.postMessage({ type: 'chat', text, state });
};

const handleHomeButtonClick = (action) => {
    if (action === 'focus_chat') {
        currentPage.value = 'chat_mode';
    } else if (action === 'search') {
        // ★修正: 書籍検索モードへ切り替え
        currentPage.value = 'search_mode';
        const msg = "蔵書検索を開始します。";
        homeConversationText.value = msg;
        speakText(msg);
    } else {
        const msg = `「${action}」機能は準備中です。`;
        homeConversationText.value = msg;
        speakText(msg);
        sendMessageToSecondary(msg);
    }
};

const sendHomeMessage = async () => {
    const user = auth.currentUser;
    if (!user) {
        const msg = 'エラー：ログインしてください。';
        homeConversationText.value = msg;
        speakText(msg);
        sendMessageToSecondary(msg);
        return;
    }
    const message = userInput.value;
    userInput.value = '';
    isLoading.value = true;

    try {
        const token = await getIdToken(user);
        const data = await api.sendMessage(currentSessionId.value, message, token, 'default');
        
        if (data.session_id) currentSessionId.value = data.session_id;
        
        // 修正：APIレスポンスのキー名の不一致に対応
        const aiResponse = data.response || data.reply || data.message || '';
        
        homeConversationText.value = aiResponse;
        speakText(aiResponse);
        sendMessageToSecondary(aiResponse);
        
    } catch (error) {
        console.error(error);
        const msg = 'エラーが発生しました。';
        homeConversationText.value = msg;
        speakText(msg);
        sendMessageToSecondary(msg);
    } finally {
        isLoading.value = false;
    }
};

const sendChatMessage = async () => {
    if (!userInput.value.trim()) return;
    const user = auth.currentUser;
    if (!user) return;

    const message = userInput.value;
    userInput.value = '';
    
    chatHistory.value.push({ sender: 'user', text: message });
    scrollToBottom();
    isLoading.value = true;

    try {
        const token = await getIdToken(user);
        const data = await api.sendMessage(currentSessionId.value, message, token, 'default');
        
        if (data.session_id) currentSessionId.value = data.session_id;
        
        // 修正：APIレスポンスのキー名の不一致に対応
        const aiResponse = data.response || data.reply || data.message || '';
        
        chatHistory.value.push({ sender: 'ai', text: aiResponse });
        speakText(aiResponse);
        sendMessageToSecondary(aiResponse);
        
    } catch (error) {
        console.error(error);
        chatHistory.value.push({ sender: 'ai', text: 'エラーが発生しました。' });
    } finally {
        isLoading.value = false;
        scrollToBottom();
    }
};

const selectBook = (bookId) => {
    selectedBook.value = suggestedBooks.value.find(b => b.id === bookId);
};

const askAboutBook = async () => {
    if (!selectedBook.value) return;
    const question = `「${selectedBook.value.title}」について教えてください。`;
    chatHistory.value.push({ sender: 'user', text: question });
    scrollToBottom();
    const user = auth.currentUser;
    if (!user) return;
    
    isLoading.value = true;

    try {
        const token = await getIdToken(user);
        const data = await api.sendMessage(currentSessionId.value, question, token, 'default');
        
        if (data.session_id) currentSessionId.value = data.session_id;
        
        // 修正：APIレスポンスのキー名の不一致に対応
        const aiResponse = data.response || data.reply || data.message || '';
        
        chatHistory.value.push({ sender: 'ai', text: aiResponse });
        speakText(aiResponse);
        sendMessageToSecondary(aiResponse);

    } catch (error) {
        console.error(error);
        chatHistory.value.push({ sender: 'ai', text: 'エラーが発生しました。' });
    } finally {
        isLoading.value = false;
        scrollToBottom();
    }
};

const scrollToBottom = async () => {
    await nextTick();
    if(chatHistoryEl.value) chatHistoryEl.value.scrollTop = chatHistoryEl.value.scrollHeight;
};

const logout = () => {
  signOut(auth).catch(error => console.error('Logout failed', error));
};

const fetchUserGreeting = async () => {
    const user = auth.currentUser;
    if (!user) return;
    
    try {
        const token = await getIdToken(user);
        const userData = await api.getUser(user.uid, token);
        
        // バックエンドがデータを返さなかった場合のフォールバック
        const userName = userData.name || user.email || 'ゲスト';
        const greeting = `ようこそ、${userName}さん！<br>今日はどんな本をお探しですか？`;
        
        homeConversationText.value = greeting;
        isLoading.value = false;
        
        let attempts = 0;
        const speakGreeting = () => {
            if (selectedVoice.value || attempts > 10) {
                speakText(greeting);
                sendMessageToSecondary(greeting);
            } else {
                attempts++;
                setTimeout(speakGreeting, 100);
            }
        };
        speakGreeting();

    } catch (error) {
        console.error('挨拶情報の取得に失敗しました:', error);
        homeConversationText.value = '接続エラー';
        isLoading.value = false;
    }
};

// --- 音声認識の実装 ---
const isRecording = ref(false);
let recognition = null;
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.lang = 'ja-JP'; recognition.interimResults = false; recognition.continuous = false; 
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        if (userInput.value) userInput.value += ' ' + transcript; else userInput.value = transcript;
    };
    recognition.onend = () => { isRecording.value = false; };
    recognition.onerror = (event) => { console.error('音声認識エラー:', event.error); isRecording.value = false; alert('音声認識でエラーが発生しました: ' + event.error); };
}
const toggleSpeechRecognition = () => {
    if (!recognition) return alert('音声認識未対応です');
    if (isRecording.value) { recognition.stop(); } else { recognition.start(); isRecording.value = true; }
};

onMounted(() => {
    // OSコマンドで開く場合は自動オープンしない
    // openSecondaryDisplay(); 
    fetchUserGreeting();
    loadVoices();
    setTimeout(loadVoices, 500);
});

onUnmounted(() => {
    channel.close();
    if (recognition && isRecording.value) recognition.stop();
    window.speechSynthesis.cancel();
});
</script>

<style>
/* アニメーション定義 */
.avatar-shape { border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%; }
@keyframes float { 0%, 100% { transform: translateY(0px); border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%; } 50% { transform: translateY(-15px); border-radius: 30% 60% 70% 40% / 50% 60% 30% 60%; } }
.animate-float { animation: float 6s ease-in-out infinite; }
@keyframes pulse-slow { 0%, 100% { transform: scale(1); opacity: 0.3; } 50% { transform: scale(1.1); opacity: 0.5; } }
.animate-pulse-slow { animation: pulse-slow 4s ease-in-out infinite; }
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
</style>