<template>
  <div class="flex items-center justify-center min-h-screen bg-gray-100">
    <div class="w-full max-w-md p-8 space-y-6 bg-white rounded-lg shadow-md">
      <h2 class="text-3xl font-bold text-center text-gray-900">Livraria ログイン</h2>
      
      <div v-if="errorMessage" class="p-3 text-sm text-red-700 bg-red-100 rounded-lg" role="alert">
        {{ errorMessage }}
      </div>

      <form class="space-y-6" @submit.prevent>
        <div>
          <label for="email" class="block text-sm font-medium text-gray-700">メールアドレス</label>
          <input v-model="email" id="email" type="email" required
                 class="w-full px-3 py-2 mt-1 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
        </div>

        <div>
          <label for="password" class="block text-sm font-medium text-gray-700">パスワード</label>
          <input v-model="password" id="password" type="password" required
                 class="w-full px-3 py-2 mt-1 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
        </div>

        <div class="flex flex-col space-y-4">
          <button @click="signIn"
                  class="w-full px-4 py-2 text-lg font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
            ログイン
          </button>
          <button @click="signUp"
                  class="w-full px-4 py-2 text-lg font-medium text-indigo-700 bg-indigo-100 rounded-md hover:bg-indigo-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
            新規登録
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { 
  createUserWithEmailAndPassword, 
  signInWithEmailAndPassword 
} from "firebase/auth";
// './firebaseConfig.js' ではなく、'../firebaseConfig.js' からインポートします
import { auth } from '../firebaseConfig'; 

const email = ref('');
const password = ref('');
const errorMessage = ref(''); // エラーメッセージ用

// 新規登録処理
const signUp = async () => {
  errorMessage.value = '';
  try {
    // 成功すると、App.vueのonAuthStateChangedが検知します
    await createUserWithEmailAndPassword(auth, email.value, password.value);
  } catch (error) {
    errorMessage.value = getFirebaseErrorMessage(error.code);
  }
};

// ログイン処理
const signIn = async () => {
  errorMessage.value = '';
  try {
    // 成功すると、App.vueのonAuthStateChangedが検知します
    await signInWithEmailAndPassword(auth, email.value, password.value);
  } catch (error) {
    errorMessage.value = getFirebaseErrorMessage(error.code);
  }
};

// Firebaseのエラーコードを日本語に変換するヘルパー関数
const getFirebaseErrorMessage = (errorCode) => {
  switch (errorCode) {
    case 'auth/invalid-email':
      return 'メールアドレスの形式が正しくありません。';
    case 'auth/user-not-found':
    case 'auth/wrong-password':
      return 'メールアドレスまたはパスワードが間違っています。';
    case 'auth/email-already-in-use':
      return 'このメールアドレスは既に使用されています。';
    case 'auth/weak-password':
      return 'パスワードは6文字以上で入力してください。';
    default:
      return 'エラーが発生しました。もう一度お試しください。';
  }
};
</script>