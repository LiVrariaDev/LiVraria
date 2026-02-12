<template>
  <!-- 認証状態の読み込みが完了するまで「読み込み中...」を表示 -->
  <div v-if="isAuthReady" class="select-none">
    <!-- URLパラメータ '?view=secondary' がある場合はセカンダリディスプレイを表示 -->
    <SecondaryDisplay v-if="isSecondaryView" />
    
    <!-- 通常の画面 -->
    <div v-else>
      <MainApp v-if="user" />
      <Login v-else />
    </div>

    <!-- 自動ログアウト警告モーダル -->
    <transition name="fade">
      <div v-if="showLogoutModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
        <div class="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl border-4 border-red-500 text-center animate-pulse-border">
          <div class="mb-6">
            <svg class="w-16 h-16 mx-auto text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 class="text-2xl font-bold text-gray-800 mb-4">自動ログアウトします</h3>
          <p class="text-gray-600 mb-6">
            一定時間操作がなかったため、セキュリティ保護のためログアウトします。<br>
            継続するには画面を操作してください。
          </p>
          <div class="text-5xl font-mono font-bold text-red-600 mb-8">
            {{ countdownValue }}
          </div>
          <button @click="resetTimer" class="bg-gray-200 hover:bg-gray-300 text-gray-800 font-bold py-3 px-8 rounded-full transition-colors w-full">
            キャンセル
          </button>
        </div>
      </div>
    </transition>
  </div>
  <div v-else class="flex items-center justify-center h-screen bg-gray-100">
      <p class="text-2xl font-semibold text-gray-700">読み込み中...</p>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { onAuthStateChanged, signOut } from "firebase/auth";
import { auth } from './firebaseConfig';

// コンポーネント
import MainApp from './components/MainApp.vue';
import Login from './components/Login.vue';
import SecondaryDisplay from './components/SecondaryDisplay.vue';

const user = ref(null);
const isAuthReady = ref(false);
const isSecondaryView = ref(false);
let unsubscribe = null;

// --- 自動ログアウト設定 ---
// 本番設定: トータル3分 (2分50秒待機 + 10秒カウントダウン)
const IDLE_TIMEOUT = 170 * 1000; // 警告が出るまでの時間 (ミリ秒)
const COUNTDOWN_DURATION = 10;  // カウントダウンする秒数

const showLogoutModal = ref(false);
const countdownValue = ref(COUNTDOWN_DURATION);
let idleTimer = null;
let countdownInterval = null;

// タイマーリセット（ユーザーの操作があった時に呼ぶ）
const resetTimer = () => {
  // ログインしていない、またはセカンダリ画面なら何もしない
  if (!user.value || isSecondaryView.value) return;

  // 既存のタイマーをクリア
  if (idleTimer) clearTimeout(idleTimer);
  if (countdownInterval) clearInterval(countdownInterval);

  // モーダルを閉じてカウントダウンをリセット
  showLogoutModal.value = false;
  countdownValue.value = COUNTDOWN_DURATION;

  // 新しい放置タイマーをセット
  idleTimer = setTimeout(() => {
    startCountdown();
  }, IDLE_TIMEOUT);
};

// カウントダウン開始
const startCountdown = () => {
  showLogoutModal.value = true;
  countdownValue.value = COUNTDOWN_DURATION;

  countdownInterval = setInterval(() => {
    countdownValue.value--;
    if (countdownValue.value <= 0) {
      performLogout();
    }
  }, 1000);
};

// ログアウト実行
const performLogout = () => {
  clearInterval(countdownInterval);
  showLogoutModal.value = false;
  signOut(auth).catch(error => console.error('Auto logout failed', error));
  // タイマーのクリアは watch(user) 側で行われます
};

// イベントリスナーの登録/解除
const setupActivityListeners = () => {
  window.addEventListener('mousemove', resetTimer);
  window.addEventListener('mousedown', resetTimer);
  window.addEventListener('keydown', resetTimer);
  window.addEventListener('scroll', resetTimer);
  window.addEventListener('touchstart', resetTimer);
};

const removeActivityListeners = () => {
  window.removeEventListener('mousemove', resetTimer);
  window.removeEventListener('mousedown', resetTimer);
  window.removeEventListener('keydown', resetTimer);
  window.removeEventListener('scroll', resetTimer);
  window.removeEventListener('touchstart', resetTimer);
};

// ユーザー状態の監視とタイマー制御
watch(user, (newUser) => {
  if (newUser && !isSecondaryView.value) {
    // ログイン時: 監視開始
    setupActivityListeners();
    resetTimer();
    
    // ログイン成功時、Secondaryディスプレイを自動で開く
    setTimeout(() => {
      const width = 1920;
      const height = 1080;
      const left = window.screen.width;
      const top = 0;
      
      window.open(
        `${window.location.origin}/?view=secondary`,
        'SecondaryDisplay',
        `width=${width},height=${height},left=${left},top=${top}`
      );
      console.log('[App] Secondary display auto-opened after login');
    }, 1000); // 1秒遅延でUIの安定化を待つ
  } else {
    // ログアウト時: 監視終了
    removeActivityListeners();
    if (idleTimer) clearTimeout(idleTimer);
    if (countdownInterval) clearInterval(countdownInterval);
    showLogoutModal.value = false;
  }
});

onMounted(() => {
  // URLパラメータをチェック
  const params = new URLSearchParams(window.location.search);
  isSecondaryView.value = params.get('view') === 'secondary';
  
  // SecondaryView の場合は認証チェックをスキップ（表示専用のため）
  if (isSecondaryView.value) {
    isAuthReady.value = true;
    return;
  }

  // 通常の認証チェック
  unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
    if (firebaseUser) {
      user.value = firebaseUser;
      resetTimer(); // ログイン時にタイマー開始
    } else {
      user.value = null;
      // ログアウト時はタイマーをクリア
      if (idleTimer) clearTimeout(idleTimer);
      if (countdownInterval) clearInterval(countdownInterval);
    }
    isAuthReady.value = true;
  });
});

onUnmounted(() => {
  if (unsubscribe) unsubscribe();
  removeActivityListeners();
  if (idleTimer) clearTimeout(idleTimer);
  if (countdownInterval) clearInterval(countdownInterval);
});
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

body {
    font-family: 'Inter', 'Noto Sans JP', sans-serif;
    margin: 0;
    overflow-y: auto; 
}

/* スクロールバー設定 */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: #f1f1f1; }
::-webkit-scrollbar-thumb { background: #c1c1c1; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #a8a8a8; }

/* タッチデバイス用: テキスト選択を完全に無効化 */
* {
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  user-select: none;
  -webkit-touch-callout: none;
  -webkit-tap-highlight-color: transparent;
}

/* 入力フィールドのみ選択を許可 */
input, textarea {
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
  user-select: text;
}

/* Kiosk端末用: 1024x600ディスプレイに最適化 */
@media (max-width: 1024px) and (max-height: 768px) {
  #app {
    transform: scale(0.8);
    transform-origin: top left;
    width: 125%; /* 100% / 0.8 = 125% */
    height: 125%;
  }
}



/* フェードアニメーション */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 赤枠のパルスアニメーション（警告用） */
@keyframes pulse-border {
  0% { border-color: rgba(239, 68, 68, 0.5); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
  70% { border-color: rgba(239, 68, 68, 1); box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
  100% { border-color: rgba(239, 68, 68, 0.5); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}
.animate-pulse-border {
  animation: pulse-border 2s infinite;
}
</style>