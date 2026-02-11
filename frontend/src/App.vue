<template>
  <!-- 認証状態の読み込みが完了するまで「読み込み中...」を表示 -->
  <div v-if="isAuthReady">
    <!-- URLパラメータ '?view=secondary' がある場合はセカンダリディスプレイを表示 -->
    <SecondaryDisplay v-if="isSecondaryView" />
    
    <!-- 通常の画面 -->
    <div v-else>
      <MainApp v-if="user" />
      <Login v-else />
    </div>
  </div>
  <div v-else class="flex items-center justify-center h-screen bg-gray-100">
      <p class="text-2xl font-semibold text-gray-700">読み込み中...</p>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { onAuthStateChanged } from "firebase/auth";
import { auth } from './firebaseConfig';

// コンポーネント
import MainApp from './components/MainApp.vue';
import Login from './components/Login.vue';
import SecondaryDisplay from './components/SecondaryDisplay.vue';

const user = ref(null);
const isAuthReady = ref(false);
const isSecondaryView = ref(false);
let unsubscribe = null;

onMounted(() => {
  // URLパラメータをチェック (?view=secondary があるか？)
  const urlParams = new URLSearchParams(window.location.search);
  isSecondaryView.value = urlParams.get('view') === 'secondary';

  // タブ名（タイトル）を設定
  if (isSecondaryView.value) {
    document.title = "Secondary Display";
  } else {
    document.title = "LiVraria Main";
  }

  // セカンダリ画面でない場合のみ、認証監視を行う
  if (!isSecondaryView.value) {
    unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      user.value = currentUser;
      isAuthReady.value = true;
    });
  } else {
    isAuthReady.value = true; // セカンダリの場合は即表示
  }
});

onUnmounted(() => {
  if (unsubscribe) unsubscribe();
});
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

body {
    font-family: 'Inter', 'Noto Sans JP', sans-serif;
    /* 修正：overflow: hidden を削除し、スクロールを許可 */
    margin: 0;
    overflow-y: auto; 
}

/* --- スクロールバーのカスタマイズ --- */
/* 幅と高さ */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

/* トラック（背景） */
::-webkit-scrollbar-track {
    background: #f1f1f1; 
}

/* つまみ部分 */
::-webkit-scrollbar-thumb {
    background: #c1c1c1; 
    border-radius: 4px;
}

/* つまみのホバー時 */
::-webkit-scrollbar-thumb:hover {
    background: #a8a8a8; 
}
</style>