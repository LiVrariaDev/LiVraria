<template>
  <!-- 認証状態の読み込みが完了するまで「読み込み中...」を表示 -->
  <div v-if="isAuthReady">
    <!-- ユーザーがログインしているかどうかに基づいて表示を切り替える -->
    <MainApp v-if="user" />
    <Login v-else />
  </div>
  <div v-else class="flex items-center justify-center h-screen bg-gray-100">
      <p class="text-2xl font-semibold text-gray-700">読み込み中...</p>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { onAuthStateChanged } from "firebase/auth";
import { auth } from './firebaseConfig'; // 設定ファイルをインポート

// コンポーネントをインポート
import MainApp from './components/MainApp.vue';
import Login from './components/Login.vue';

const user = ref(null);
const isAuthReady = ref(false); // 認証状態の準備ができたか
let unsubscribe = null; // 監視を停止するための変数

// コンポーネントがマウントされた時に実行
onMounted(() => {
  // onAuthStateChangedは、ログイン、ログアウト、またはページの初回読み込み時に
  // ユーザーの認証状態をチェックするFirebaseの機能です
  unsubscribe = onAuthStateChanged(auth, (currentUser) => {
    user.value = currentUser; // ユーザー情報を更新
    isAuthReady.value = true; // 認証状態のチェックが完了したことを示す
  });
});

// コンポーネントが破棄される時に実行
onUnmounted(() => {
  // メモリリークを防ぐために、onAuthStateChangedの監視を停止します
  if (unsubscribe) {
    unsubscribe();
  }
});
</script>

<style>
/* グローバルなスタイル（フォントなど）はここに残します。
  MainApp.vue にもスタイルがありますが、Tailwindが重複を処理します。
*/
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
body {
    font-family: 'Inter', 'Noto Sans JP', sans-serif;
    overflow: hidden;
}
</style>