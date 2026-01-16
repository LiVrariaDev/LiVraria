<template>
  <!-- 
    URLに '?view=secondary' がついている時はセカンダリディスプレイを表示
    それ以外は通常のログイン・メイン画面を表示
  -->
  <SecondaryDisplay v-if="isSecondaryView" />
  
  <div v-else>
    <div v-if="isAuthReady">
      <MainApp v-if="user" />
      <Login v-else />
    </div>
    <div v-else class="flex items-center justify-center h-screen bg-gray-100">
      <p class="text-2xl font-semibold text-gray-700">読み込み中...</p>
    </div>
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

  // セカンダリ画面でない場合のみ、認証監視を行う
  if (!isSecondaryView.value) {
    unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      user.value = currentUser;
      isAuthReady.value = true;
    });
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
    overflow: hidden;
}
</style>