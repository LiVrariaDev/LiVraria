<template>
  <div class="flex items-center justify-center min-h-screen bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500">
    <!-- 背景の装飾（ぼやけた円） -->
    <div class="absolute top-20 left-20 w-72 h-72 bg-white rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob"></div>
    <div class="absolute top-40 right-20 w-72 h-72 bg-yellow-200 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-2000"></div>
    <div class="absolute -bottom-8 left-40 w-72 h-72 bg-pink-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-4000"></div>

    <!-- ログインカード -->
    <div class="relative w-full max-w-md p-8 space-y-8 bg-white/90 backdrop-blur-sm rounded-2xl shadow-2xl">
      <div class="text-center">
        <h2 class="text-4xl font-extrabold text-gray-900 tracking-tight">Livraria</h2>
        <p class="mt-2 text-sm text-gray-600">AI司書との対話で、新しい本の世界へ</p>
      </div>
      
      <div v-if="errorMessage" class="p-4 text-sm text-red-700 bg-red-100 border-l-4 border-red-500 rounded" role="alert">
        <p class="font-bold">エラー</p>
        <p>{{ errorMessage }}</p>
      </div>

      <form class="space-y-6" @submit.prevent>
        <div class="space-y-1">
          <label for="email" class="block text-sm font-medium text-gray-700">メールアドレス</label>
          <input v-model="email" id="email" type="email" required placeholder="name@example.com"
                 class="w-full px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all outline-none">
        </div>

        <div class="space-y-1">
          <label for="password" class="block text-sm font-medium text-gray-700">パスワード</label>
          <input v-model="password" id="password" type="password" required placeholder="••••••••"
                 class="w-full px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all outline-none">
        </div>

        <div class="pt-4 flex flex-col space-y-4">
          <button @click="signIn"
                  class="w-full px-4 py-3 text-lg font-bold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transform hover:-translate-y-0.5 transition-all duration-200 shadow-lg hover:shadow-indigo-500/30 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
            ログイン
          </button>
          <div class="relative flex items-center justify-center">
            <span class="absolute px-3 bg-white/90 text-gray-500 text-sm">または</span>
            <div class="w-full border-t border-gray-300"></div>
          </div>
          <button @click="signUp"
                  class="w-full px-4 py-3 text-lg font-bold text-indigo-700 bg-indigo-50 border-2 border-indigo-100 rounded-lg hover:bg-indigo-100 hover:border-indigo-200 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
            新規アカウント作成
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { createUserWithEmailAndPassword, signInWithEmailAndPassword } from "firebase/auth";
import { auth } from '../firebaseConfig'; 

const email = ref('');
const password = ref('');
const errorMessage = ref('');

const signUp = async () => {
  errorMessage.value = '';
  try {
    await createUserWithEmailAndPassword(auth, email.value, password.value);
  } catch (error) {
    errorMessage.value = getFirebaseErrorMessage(error.code);
  }
};

const signIn = async () => {
  errorMessage.value = '';
  try {
    await signInWithEmailAndPassword(auth, email.value, password.value);
  } catch (error) {
    errorMessage.value = getFirebaseErrorMessage(error.code);
  }
};

const getFirebaseErrorMessage = (errorCode) => {
  switch (errorCode) {
    case 'auth/invalid-email': return 'メールアドレスの形式が正しくありません。';
    case 'auth/user-not-found':
    case 'auth/wrong-password': return 'メールアドレスまたはパスワードが間違っています。';
    case 'auth/email-already-in-use': return 'このメールアドレスは既に使用されています。';
    case 'auth/weak-password': return 'パスワードは6文字以上で入力してください。';
    default: return 'エラーが発生しました。もう一度お試しください。';
  }
};
</script>

<style scoped>
/* 背景のアニメーション定義 */
@keyframes blob {
  0% { transform: translate(0px, 0px) scale(1); }
  33% { transform: translate(30px, -50px) scale(1.1); }
  66% { transform: translate(-20px, 20px) scale(0.9); }
  100% { transform: translate(0px, 0px) scale(1); }
}
.animate-blob {
  animation: blob 7s infinite;
}
.animation-delay-2000 {
  animation-delay: 2s;
}
.animation-delay-4000 {
  animation-delay: 4s;
}
</style>