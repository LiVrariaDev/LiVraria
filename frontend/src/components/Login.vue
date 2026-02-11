<template>
  <!-- 修正：上下に十分な余白(py-12)を追加してスクロールしやすくする -->
  <div class="flex items-center justify-center min-h-screen py-12 bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 font-sans">
    
    <!-- 背景装飾（スクロールしても位置が固定されるように fixed に変更） -->
    <div class="fixed top-20 left-20 w-72 h-72 bg-white rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob"></div>
    <div class="fixed top-40 right-20 w-72 h-72 bg-yellow-200 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-2000"></div>
    <div class="fixed -bottom-8 left-40 w-72 h-72 bg-pink-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-4000"></div>

    <!-- カードコンテナ（z-indexを指定して背景より手前に表示） -->
    <div class="relative w-full max-w-lg p-8 bg-white/90 backdrop-blur-sm rounded-2xl shadow-2xl transition-all duration-500 z-10 my-4 mx-4">
      
      <!-- ヘッダー -->
      <div class="text-center mb-8">
        <h2 class="text-4xl font-extrabold text-gray-900 tracking-tight">LiVraria</h2>
        <p class="mt-2 text-sm text-gray-600">
          {{ isRegisterMode ? 'アカウントを作成して始める' : 'AI司書との対話へようこそ' }}
        </p>
      </div>
      
      <!-- エラーメッセージ -->
      <div v-if="errorMessage" class="mb-6 p-4 text-sm text-red-700 bg-red-100 border-l-4 border-red-500 rounded" role="alert">
        <p class="font-bold">エラー</p>
        <p>{{ errorMessage }}</p>
      </div>

      <!-- フォーム -->
      <form @submit.prevent="handleSubmit" class="space-y-5">
        
        <!-- ログイン/登録 共通項目 -->
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">メールアドレス</label>
            <input v-model="email" type="email" required placeholder="name@example.com"
                   class="w-full px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all outline-none">
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">パスワード</label>
            <input v-model="password" type="password" required placeholder="••••••••"
                   class="w-full px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all outline-none">
          </div>
        </div>

        <!-- 新規登録モードのみ表示する追加項目 -->
        <div v-if="isRegisterMode" class="space-y-4 pt-2 animate-fade-in">
          <div class="border-t border-gray-200 pt-4">
            <p class="text-xs text-gray-500 mb-4 text-center">- プロフィール情報 -</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">お名前 (ニックネーム可)</label>
            <input v-model="profile.name" type="text" required placeholder="例: 読書 太郎"
                   class="w-full px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all outline-none">
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">性別</label>
              <select v-model="profile.gender" required class="w-full px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all outline-none">
                <option value="" disabled>選択してください</option>
                <option value="male">男性</option>
                <option value="female">女性</option>
                <option value="other">その他</option>
                <option value="none">回答しない</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">年齢</label>
              <input v-model="profile.age" type="number" required min="0" max="120" placeholder="20"
                     class="w-full px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all outline-none">
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">お住まいの都道府県</label>
              <select v-model="profile.live_pref" required class="w-full px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all outline-none">
                <option value="" disabled>選択</option>
                <option v-for="pref in prefectures" :key="pref" :value="pref">{{ pref }}</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">市区町村 (任意)</label>
              <input v-model="profile.live_city" type="text" placeholder="例: 千代田区"
                     class="w-full px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all outline-none">
            </div>
          </div>
        </div>
        
        <!-- アクションボタン -->
        <div class="pt-2 flex flex-col space-y-4">
          <!-- 1. 通常のログイン/登録ボタン -->
          <button type="submit" 
                :disabled="isLoading"
                class="w-full px-4 py-3 text-lg font-bold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transform hover:-translate-y-0.5 transition-all duration-200 shadow-lg hover:shadow-indigo-500/30 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed">
            <span v-if="isLoading">処理中...</span>
            <span v-else>{{ isRegisterMode ? '登録してはじめる' : 'ログイン' }}</span>
          </button>
        
          <!-- 2. NFCログインボタン (ログインモード時のみ表示) -->
          <div v-if="!isRegisterMode" class="w-full pt-2">
            <div class="relative flex items-center justify-center mb-4">
              <div class="w-full border-t border-gray-300"></div>
              <span class="absolute px-3 bg-white/90 text-xs text-gray-400">または</span>
            </div>

            <button
              type="button"
              @click="startNfcLogin"
              :disabled="isLoading || isReadingNfc"
              class="w-full px-4 py-3 text-lg font-bold text-white bg-purple-600 rounded-lg hover:bg-purple-700 transform hover:-translate-y-0.5 transition-all duration-200 shadow-lg hover:shadow-purple-500/30 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
            >
              <span v-if="!isReadingNfc">💳 NFCでログイン</span>
              <span v-else class="animate-pulse">📡 カードをかざしてください...</span>
            </button>
          </div>

          <!-- 3. 新規登録/ログイン切り替えリンク (一番下) -->
          <div class="pt-2">
             <button type="button" @click="toggleMode"
                  class="w-full text-sm text-indigo-600 hover:text-indigo-800 font-semibold focus:outline-none underline text-center">
              {{ isRegisterMode ? 'すでにアカウントをお持ちの方はログイン' : 'アカウントをお持ちでない方は新規登録' }}
            </button>
          </div>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue';
import { createUserWithEmailAndPassword, signInWithEmailAndPassword } from "firebase/auth";
import { auth } from '../firebaseConfig'; 
import { api } from '../services/api'; 

const isRegisterMode = ref(false); 
const isLoading = ref(false);
const errorMessage = ref('');

const email = ref('');
const password = ref('');

const profile = reactive({
  name: '',
  gender: '',
  age: null,
  live_pref: '',
  live_city: ''
});

const isReadingNfc = ref(false);

import { readNfcCard } from '../services/nfc';
import { signInWithCustomToken } from "firebase/auth";

const startNfcLogin = async () => {
  errorMessage.value = '';
  isReadingNfc.value = true;

  try {
    await readNfcCard(async (idm) => {
      isReadingNfc.value = false;
      
      // 1. バックエンドでNFC認証 -> Custom Token取得
      const result = await api.authenticateNfc(idm);
      if (!result.custom_token) {
        throw new Error('認証トークンの取得に失敗しました');
      }

      // 2. FirebaseにCustom Tokenでログイン
      await signInWithCustomToken(auth, result.custom_token);
      console.log('NFCログイン完了');
    });
  } catch (error) {
    console.error('NFCログインエラー:', error);
    if (error.message.includes('NFC ID not registered')) {
      errorMessage.value = 'このカードは未登録です。';
    } else {
      errorMessage.value = `NFCログインエラー: ${error.message}`;
    }
    isReadingNfc.value = false;
  }
};

// BroadcastChannelを作成（MainAppと同じ名前を使うことで通信可能）
const channel = new BroadcastChannel('livraria_channel');

// 画面が表示された時に実行
onMounted(() => {
  // アプリ起動時（ログイン画面表示時）に、セカンダリディスプレイを「待機状態」にする
  setTimeout(() => {
    channel.postMessage({ 
      type: 'chat', 
      text: 'いらっしゃいませ。\nログインしてください。', 
      state: 'idle' 
    });
  }, 1000); 
});

onUnmounted(() => {
  channel.close();
});

const prefectures = [
  "北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県",
  "茨城県","栃木県","群馬県","埼玉県","千葉県","東京都","神奈川県",
  "新潟県","富山県","石川県","福井県","山梨県","長野県","岐阜県",
  "静岡県","愛知県","三重県","滋賀県","京都府","大阪府","兵庫県",
  "奈良県","和歌山県","鳥取県","島根県","岡山県","広島県","山口県",
  "徳島県","香川県","愛媛県","高知県","福岡県","佐賀県","長崎県",
  "熊本県","大分県","宮崎県","鹿児島県","沖縄県"
];

const toggleMode = () => {
  isRegisterMode.value = !isRegisterMode.value;
  errorMessage.value = '';
};

const handleSubmit = async () => {
  if (isRegisterMode.value) {
    await signUp();
  } else {
    await signIn();
  }
};

const signUp = async () => {
  errorMessage.value = '';
  isLoading.value = true;
  
  try {
    const userCredential = await createUserWithEmailAndPassword(auth, email.value, password.value);
    const user = userCredential.user;
    const token = await user.getIdToken();

    const userData = {
        name: profile.name,
        gender: profile.gender,
        age: profile.age,
        live_pref: profile.live_pref,
        live_city: profile.live_city || 'unknown'
    };

    await api.createUser(userData, token);
    console.log('ユーザー登録完了');

  } catch (error) {
    console.error('Registration error:', error);
    if (error.message.includes('Failed to create user')) {
        errorMessage.value = '認証には成功しましたが、プロフィールの保存に失敗しました。';
    } else {
        errorMessage.value = getFirebaseErrorMessage(error.code);
    }
  } finally {
    isLoading.value = false;
  }
};

const signIn = async () => {
  errorMessage.value = '';
  isLoading.value = true;
  try {
    await signInWithEmailAndPassword(auth, email.value, password.value);
    console.log('ログイン完了');
  } catch (error) {
    errorMessage.value = getFirebaseErrorMessage(error.code);
  } finally {
    isLoading.value = false;
  }
};

const getFirebaseErrorMessage = (errorCode) => {
  switch (errorCode) {
    case 'auth/invalid-email': return 'メールアドレスの形式が正しくありません。';
    case 'auth/user-not-found':
    case 'auth/wrong-password': return 'メールアドレスまたはパスワードが間違っています。';
    case 'auth/email-already-in-use': return 'このメールアドレスは既に使用されています。';
    case 'auth/weak-password': return 'パスワードは6文字以上で入力してください。';
    default: return `エラーが発生しました。(${errorCode})`;
  }
};
</script>

<style scoped>
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
.animate-fade-in {
  animation: fadeIn 0.3s ease-out forwards;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>