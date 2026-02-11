<template>
    <div class="w-screen h-screen font-sans text-gray-800 bg-gray-900">

        <!-- ===== 診断用 ===== -->
        <img 
            src="/bg.jpg" 
            style="display: none;" 
            @error="handleImageError" 
            @load="handleImageLoad"
        />

        <!-- ===== 会員情報ページ ===== -->
        <div v-if="currentPage === 'member_info'" class="w-full h-full">
            <MemberInfoPage :onBack="() => currentPage = 'home'" />
        </div>

        <!-- ===== ホームページ表示 ===== -->
        <div v-if="currentPage === 'home'" class="relative flex flex-col w-full h-full overflow-hidden">
            <!-- 背景画像エリア -->
            <div class="absolute inset-0 z-0 bg-cover bg-center transition-all duration-700"
                 :style="{ backgroundImage: `linear-gradient(rgba(0, 0, 0, 0.7), rgba(0, 0, 0, 0.7)), url('/bg.jpg?v=2')` }">
            </div>

            <!-- 
                メインコンテンツエリア (全画面使用) 
                修正: pb-72 (padding-bottom) を大きくして、コンテンツ全体を上に押し上げる
            -->
            <div class="relative z-10 flex-grow flex flex-col items-center justify-center w-full px-12 pt-12 pb-72">
                
                <!-- ステータス表示エリア (ボタンの上に配置) -->
                <div class="h-24 mb-8 flex items-center justify-center w-full">
                    <div v-if="isRecording" class="flex items-center space-x-6 animate-pulse bg-black/40 px-8 py-4 rounded-full border border-red-500/30 backdrop-blur-md">
                        <div class="p-3 bg-red-500 rounded-full shadow-[0_0_20px_rgba(239,68,68,0.8)]">
                            <svg class="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                            </svg>
                        </div>
                        <span class="text-3xl font-bold text-white tracking-widest drop-shadow-md">LISTENING...</span>
                    </div>
                    <div v-else-if="isLoading" class="flex items-center space-x-6 bg-black/40 px-8 py-4 rounded-full border border-blue-500/30 backdrop-blur-md">
                        <div class="p-3 bg-blue-500 rounded-full shadow-[0_0_20px_rgba(59,130,246,0.8)] animate-spin-slow">
                            <svg class="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                        </div>
                        <span class="text-3xl font-bold text-white tracking-widest drop-shadow-md animate-pulse">THINKING...</span>
                    </div>
                    <!-- 通常時はタイトルを表示 -->
                    <div v-else class="text-center opacity-80 hover:opacity-100 transition-opacity duration-500">
                        <h1 class="text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-200 to-purple-200 tracking-tight drop-shadow-sm">LiVraria Menu</h1>
                    </div>
                </div>

                <!-- 
                    ボタンエリア 
                    修正: max-h-[55vh] に少し縮めて間延びを防ぎつつ、上部に配置
                -->
                <div class="grid grid-cols-2 gap-8 w-full max-w-7xl flex-grow max-h-[55vh]">
                    <button v-for="button in mainButtons" :key="button.id" 
                            @click="handleHomeButtonClick(button.action)"
                            class="group relative overflow-hidden rounded-3xl shadow-xl transition-all duration-300 flex flex-col items-center justify-center h-full w-full
                                   bg-transparent border-2 border-white/50 backdrop-blur-sm
                                   hover:bg-white hover:border-white hover:shadow-[0_0_50px_rgba(255,255,255,0.4)] hover:-translate-y-2">
                        
                        <!-- コンテンツ -->
                        <div class="relative z-10 flex flex-col items-center space-y-6">
                            <!-- アイコン: 通常は白っぽく、ホバー時は青く -->
                            <div class="p-8 rounded-full bg-white/10 text-white group-hover:bg-blue-100 group-hover:text-blue-600 transition-colors duration-300 shadow-inner group-hover:shadow-lg group-hover:scale-110 transform transition-transform">
                                <span v-if="button.icon === 'search'" class="block transform scale-150" v-html="icons.search"></span>
                                <span v-else-if="button.icon === 'chat'" class="block transform scale-150" v-html="icons.chat"></span>
                                <span v-else-if="button.icon === 'grid'" class="block transform scale-150" v-html="icons.grid"></span>
                                <span v-else class="block transform scale-150" v-html="icons.star"></span>
                            </div>
                            <!-- テキスト: 通常は白、ホバー時は濃い色 -->
                            <span class="text-4xl font-bold text-white group-hover:text-slate-800 transition-colors tracking-wide drop-shadow-md group-hover:drop-shadow-none">{{ button.text }}</span>
                        </div>
                    </button>
                </div>
            </div>

            <!-- 下部: 入力とオプションエリア -->
            <div class="absolute bottom-0 left-0 right-0 bg-gray-900/95 backdrop-blur-md border-t border-white/10 p-6 flex items-center shadow-2xl z-20 h-24">
                <div class="flex-grow mx-8 relative flex items-center max-w-4xl">
                    <button @click="toggleSpeechRecognition" 
                            class="mr-4 p-4 rounded-full transition-all duration-200 focus:outline-none shadow-lg hover:scale-105 active:scale-95 border border-white/10"
                            :class="isRecording ? 'bg-red-600 text-white hover:bg-red-700 animate-pulse' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'">
                        <svg v-if="!isRecording" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"></path></svg>
                        <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"/></svg>
                    </button>

                    <input type="text" v-model="userInput" @keydown.enter.prevent="sendHomeMessage" 
                           placeholder="AI司書に話しかける..."
                           class="w-full bg-gray-800 border border-gray-600 rounded-full py-4 px-6 text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/50 transition-all shadow-inner text-lg">
                </div>
                
                <div class="flex-grow"></div> <!-- スペーサー -->

                <div class="flex space-x-4 mr-8 items-center">
                     <button @click="openSecondaryDisplay" class="flex items-center px-6 py-3 bg-teal-600/20 hover:bg-teal-600/40 text-teal-300 font-bold rounded-xl transition-colors duration-200 border border-teal-500/30">
                        <span class="mr-2 text-xl">📺</span> 動画ウィンドウ
                     </button>

                     <button @click="toggleSpeech" class="flex items-center px-6 py-3 bg-gray-800 hover:bg-gray-700 text-gray-300 font-bold rounded-xl transition-colors duration-200 border border-gray-600" :class="{'text-blue-400 border-blue-500/50': isSpeechEnabled}">
                        <span v-if="isSpeechEnabled">🔊 ON</span>
                        <span v-else>🔇 OFF</span>
                      </button>

                      <button v-for="button in utilityButtons" :key="button.id"
                             @click="handleHomeButtonClick(button.action)"
                             class="flex items-center px-6 py-3 bg-gray-800 hover:bg-gray-700 text-gray-300 font-bold rounded-xl transition-colors duration-200 border border-gray-600">
                        <span class="mr-2">⚙️</span> {{ button.text }}
                    </button>
                    <button @click="logout" class="flex items-center px-6 py-3 bg-red-900/30 hover:bg-red-900/50 text-red-400 font-bold rounded-xl transition-colors duration-200 border border-red-800/50">
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
                                <div v-if="suggestedBooks.length === 0" class="col-span-3 text-center text-gray-400 py-10">
                                    まだおすすめの本はありません
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
                    <h1 class="text-xl font-bold text-slate-700">蔵書検索</h1>
                </div>
                <div class="flex space-x-3">
                    <button @click="currentPage = 'home'" class="flex items-center space-x-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold py-2 px-4 rounded-lg transition-colors">
                        <span>ホームへ</span>
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

import MemberInfoPage from './MemberInfoPage.vue';
// import bgImage from '../assets/bg.jpg';

const handleImageError = () => {
    alert("【画像読み込みエラー】\n publicフォルダに 'bg.jpg' が見つかりません。");
};
const handleImageLoad = () => {
    console.log("画像の読み込みに成功しました！");
};

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
    if (!text) return;

    if (!selectedVoice.value) loadVoices();

    const plainText = typeof text === 'string' ? text.replace(/<[^>]+>/g, '') : '';
    if (!plainText) return;

    const utterance = new SpeechSynthesisUtterance(plainText);
    if (selectedVoice.value) utterance.voice = selectedVoice.value;
    utterance.lang = 'ja-JP';
    utterance.rate = 1.0;
    
    // 発話終了時に「待機(idle)」ステートを送信
    utterance.onend = () => {
        sendMessageToSecondary(null, 'idle');
    };

    window.speechSynthesis.speak(utterance);
};

// アイコンサイズを w-12 h-12 に拡大
const icons = {
    search: `<svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>`,
    chat: `<svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>`,
    grid: `<svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg>`,
    star: `<svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"></path></svg>`
};

const currentPage = ref('home');
const userInput = ref('');
const isLoading = ref(false);
const secondaryWindow = ref(null);
const currentSessionId = ref(null); 
const mainButtons = ref([ 
    { id: 1, text: '書籍検索', action: 'search', icon: 'search' }, 
    { id: 2, text: '会話集中モード', action: 'focus_chat', icon: 'chat' }, 
    { id: 3, text: '会員情報', action: 'member_info', icon: 'grid' }, 
    { id: 4, text: 'グッドスナイパー', action: 'good_sniper', icon: 'star' }
]);
const utilityButtons = ref([ { id: 6, text: 'オプション', action: 'options' } ]); 
const chatHistory = ref([ 
    { sender: 'ai', text: 'こんにちは！AI司書です。本日はどのようなご用件でしょうか？' }
]);
const suggestedBooks = ref([]);
const selectedBook = ref(null);
const chatHistoryEl = ref(null);

const channel = new BroadcastChannel('livraria_channel'); 

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
    } else if (action === 'member_info') {
        currentPage.value = 'member_info';
        const msg = "会員情報モードへ切り替えました。";
        homeConversationText.value = msg;
        speakText(msg);
        sendMessageToSecondary(msg);
    } else {
        const msg = `「${action}」機能は準備中です。`;
        speakText(msg);
        sendMessageToSecondary(msg, 'neutral');
    }
};

const updateSuggestedBooks = (books) => {
    if (books && books.length > 0) {
        suggestedBooks.value = books.map((book, index) => ({
            id: book.isbn || index, // ISBNがあればそれ、なければインデックス
            title: book.title,
            cover: book.image_url || `https://placehold.co/150x220/3b82f6/ffffff?text=NoImage`,
            ...book
        }));
    }
};

const sendHomeMessage = async () => {
    const user = auth.currentUser;
    if (!user) {
        const msg = 'エラー：ログインしてください。';
        speakText(msg);
        sendMessageToSecondary(msg, 'neutral');
        return;
    }
    const message = userInput.value;
    userInput.value = '';
    isLoading.value = true;

    // 1. 送信直後：思考中ステートを送信 (テキストは空でOK、セカンダリ側で消去される)
    sendMessageToSecondary('', 'thinking');

    try {
        const token = await getIdToken(user);
        const data = await api.sendMessage(currentSessionId.value, message, token, 'default');
        
        if (data.session_id) currentSessionId.value = data.session_id;
        
        const aiResponse = data.response || data.reply || data.message || '';
        // 2. 受信時：表情フラグと回答を送信
        const expression = data.expression || 'neutral';
        
        speakText(aiResponse);
        sendMessageToSecondary(aiResponse, expression);

        // 推薦図書の更新
        updateSuggestedBooks(data.recommended_books);
        
    } catch (error) {
        console.error(error);
        const msg = 'エラーが発生しました。';
        speakText(msg);
        sendMessageToSecondary(msg, 'sorry');
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

    // 1. 送信直後：思考中ステートを送信
    sendMessageToSecondary('', 'thinking');

    try {
        const token = await getIdToken(user);
        const data = await api.sendMessage(currentSessionId.value, message, token, 'default');
        
        if (data.session_id) currentSessionId.value = data.session_id;
        
        const aiResponse = data.response || data.reply || data.message || '';
        const expression = data.expression || 'neutral';
        
        chatHistory.value.push({ sender: 'ai', text: aiResponse });
        speakText(aiResponse);
        sendMessageToSecondary(aiResponse, expression);

        // 推薦図書の更新
        updateSuggestedBooks(data.recommended_books);
        
    } catch (error) {
        console.error(error);
        chatHistory.value.push({ sender: 'ai', text: 'エラーが発生しました。' });
        sendMessageToSecondary('エラーです', 'sorry');
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
    sendMessageToSecondary('', 'thinking'); 

    try {
        const token = await getIdToken(user);
        const data = await api.sendMessage(currentSessionId.value, question, token, 'default');
        
        if (data.session_id) currentSessionId.value = data.session_id;
        
        const aiResponse = data.response || data.reply || data.message || '';
        const expression = data.expression || 'neutral';
        
        chatHistory.value.push({ sender: 'ai', text: aiResponse });
        speakText(aiResponse);
        sendMessageToSecondary(aiResponse, expression);

        // 推薦図書の更新
        updateSuggestedBooks(data.recommended_books);

    } catch (error) {
        console.error(error);
        chatHistory.value.push({ sender: 'ai', text: 'エラーが発生しました。' });
        sendMessageToSecondary('エラーです', 'sorry');
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
        
        const userName = userData.name || user.email || 'ゲスト';
        const greeting = `ようこそ、${userName}さん！<br>今日はどんな本をお探しですか？`;
        
        isLoading.value = false;
        
        let attempts = 0;
        const speakGreeting = () => {
            if (selectedVoice.value || attempts > 10) {
                speakText(greeting);
                sendMessageToSecondary(greeting, 'neutral');
            } else {
                attempts++;
                setTimeout(speakGreeting, 100);
            }
        };
        speakGreeting();

    } catch (error) {
        console.error('挨拶情報の取得に失敗しました:', error);
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
.animate-spin-slow {
  animation: spin 3s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
</style>