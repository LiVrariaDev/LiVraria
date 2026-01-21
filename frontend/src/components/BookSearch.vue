<script setup>
import { ref, onMounted } from 'vue';
import { getAuth } from 'firebase/auth';
import api from '../services/api';

// 状態管理用の変数
const query = ref('');
const semanticSearch = ref(true); // AI検索をデフォルトでONに変更
const books = ref([]);
const loading = ref(false);
const error = ref(null);

// 図書館関連の変数
const myLibraries = ref([]); // 住んでいる地域の図書館リスト
const availability = ref(null); // 選択した本の貸出状況
const checkingStock = ref(false); // 在庫確認中かどうか
const selectedBook = ref(null); // 現在在庫を確認している本

// ユーザーの居住地（都道府県）を取得して、近所の図書館リストを準備する
onMounted(async () => {
  try {
    const auth = getAuth();
    // ログイン待ち
    await new Promise(resolve => {
        const unsubscribe = auth.onAuthStateChanged(user => {
            if (user) resolve(user);
            else resolve(null); // 未ログイン
            unsubscribe();
        });
    });

    const user = auth.currentUser;
    if (user) {
        // 既存の getUser(userId, idToken) に合わせてトークンを取得して渡す
        const token = await user.getIdToken();
        const userData = await api.getUser(user.uid, token);
        
        // ※ ユーザーデータのどこに都道府県が入っているか確認してね
        // ここでは user.personal.prefecture だと仮定しているよ
        const pref = userData.personal?.address || userData.personal?.prefecture || '東京都'; 
        
        console.log(`User prefecture: ${pref}`);

        // 2. その地域の図書館を検索してリストアップしておく
        // limit=10 くらいで主要な図書館を取得
        const libs = await api.searchLibraries(pref, 10);
        myLibraries.value = libs;
        console.log("Libraries loaded:", myLibraries.value);
    }
  } catch (e) {
    console.error("Setup failed:", e);
    // エラーが出ても本の検索だけはできるようにエラーは表示しないでおく
  }
});

// 本を検索する関数
const searchBooks = async () => {
  if (!query.value) return;
  
  loading.value = true;
  error.value = null;
  books.value = [];
  availability.value = null;
  selectedBook.value = null;

  try {
    // APIを呼び出して本を検索
    // semanticSearch.value が true (デフォルト) なので常にAI検索が走る
    const result = await api.searchBooks(query.value, semanticSearch.value);
    
    // 楽天ブックスのレスポンス形式に合わせて調整
    // (Items配列の中にItemオブジェクトが入っている構造を想定)
    if (result.Items) {
        books.value = result.Items.map(item => item.Item);
    } else {
        books.value = [];
    }

    if (books.value.length === 0) {
        error.value = "本が見つかりませんでした。";
    }

  } catch (e) {
    console.error(e);
    error.value = "検索に失敗しました。";
  } finally {
    loading.value = false;
  }
};

// 特定の本の図書館在庫を確認する関数
const checkAvailability = async (book) => {
  if (myLibraries.value.length === 0) {
    alert("地域の図書館情報が取得できていません。");
    return;
  }

  selectedBook.value = book;
  checkingStock.value = true;
  availability.value = null;

  try {
    // 地域の図書館IDをカンマ区切りで結合 (例: "Tokyo_Minato,Tokyo_Shibuya")
    const systemIds = myLibraries.value.map(lib => lib.systemid).join(',');
    
    // APIを呼び出して在庫確認
    const result = await api.checkBookAvailability(book.isbn, systemIds);
    
    // カーリルのレスポンスを解析
    // result[isbn][systemid] = {status: 'OK', libkey: { ... }} のような構造
    // 使いやすい形に整形する
    const statusMap = [];
    const bookData = result[book.isbn]; // その本のデータ

    if (bookData) {
        myLibraries.value.forEach(lib => {
            const libStatus = bookData[lib.systemid];
            if (libStatus) {
                // 貸出状況のテキストを取得 (例: "貸出可", "貸出中", "蔵書なし")
                // libkeyの中に詳細があるが、statusでおおよそわかる
                let statusText = libStatus.status;
                let colorClass = 'text-gray-500';

                if (libStatus.status === 'OK') {
                    statusText = '貸出可';
                    colorClass = 'text-green-600 font-bold';
                } else if (libStatus.status === 'Cache') {
                    statusText = '確認中...'; // キャッシュなどの場合
                    colorClass = 'text-yellow-600';
                } else {
                    // libkeyの中身を見てみる（より詳細なステータス）
                    const libkeys = libStatus.libkey || {};
                    const values = Object.values(libkeys);
                    if (values.length > 0 && values.includes('貸出可')) {
                        statusText = '貸出可';
                        colorClass = 'text-green-600 font-bold';
                    } else if (values.length > 0) {
                        statusText = '貸出中など';
                        colorClass = 'text-red-500';
                    } else {
                        statusText = '蔵書なし';
                        colorClass = 'text-gray-400';
                    }
                }

                statusMap.push({
                    name: lib.formal, // 図書館の正式名称
                    status: statusText,
                    class: colorClass
                });
            }
        });
    }
    availability.value = statusMap;

  } catch (e) {
    console.error(e);
    alert("在庫確認に失敗しました。");
  } finally {
    checkingStock.value = false;
  }
};
</script>

<template>
  <div class="p-6 max-w-4xl mx-auto">
    <h1 class="text-3xl font-bold mb-6 text-gray-800 flex items-center gap-2">
        <span>📚</span> 蔵書検索
    </h1>

    <!-- 検索フォームエリア -->
    <div class="bg-white p-6 rounded-lg shadow-md mb-8">
      <div class="flex flex-col gap-4">
        <div class="flex gap-2">
            <input 
            v-model="query" 
            @keyup.enter="searchBooks"
            type="text" 
            placeholder="本のタイトル、著者、または「元気が出る本」のようなキーワード" 
            class="flex-1 p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button 
            @click="searchBooks" 
            :disabled="loading"
            class="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors font-bold"
            >
            {{ loading ? '検索中...' : '検索' }}
            </button>
        </div>
        
        <!-- AI検索オプション（非表示）: semanticSearch は script setup で true に固定 -->
      </div>
    </div>

    <!-- エラー表示 -->
    <div v-if="error" class="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-6" role="alert">
      <p>{{ error }}</p>
    </div>

    <!-- 検索結果リスト -->
    <div v-if="books.length > 0" class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div v-for="book in books" :key="book.isbn" class="bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow p-4 flex gap-4 border border-gray-100">
        <!-- 本の表紙 -->
        <div class="w-24 flex-shrink-0">
            <img :src="book.mediumImageUrl || 'https://placehold.co/100x150?text=No+Image'" alt="表紙" class="w-full rounded shadow-sm">
        </div>
        
        <!-- 本の情報 -->
        <div class="flex-1 flex flex-col justify-between">
            <div>
                <h3 class="font-bold text-lg leading-tight mb-1 line-clamp-2">{{ book.title }}</h3>
                <p class="text-sm text-gray-600 mb-2">{{ book.author }}</p>
                <p class="text-xs text-gray-400">ISBN: {{ book.isbn }}</p>
            </div>
            
            <button 
                @click="checkAvailability(book)"
                class="mt-3 w-full bg-emerald-500 text-white py-2 px-4 rounded-md text-sm font-bold hover:bg-emerald-600 transition-colors flex items-center justify-center gap-1"
            >
                <span>🏢</span> 図書館で探す
            </button>
        </div>
      </div>
    </div>

    <!-- 在庫状況モーダル -->
    <div v-if="selectedBook" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" @click.self="selectedBook = null">
        <div class="bg-white rounded-xl shadow-2xl max-w-lg w-full overflow-hidden animate-fade-in-up">
            <div class="p-4 bg-gray-50 border-b flex justify-between items-center">
                <h3 class="font-bold text-lg truncate pr-4">「{{ selectedBook.title }}」の蔵書状況</h3>
                <button @click="selectedBook = null" class="text-gray-400 hover:text-gray-600">
                    ✕
                </button>
            </div>
            
            <div class="p-6">
                <div v-if="checkingStock" class="flex flex-col items-center justify-center py-8">
                    <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-emerald-500 mb-2"></div>
                    <p class="text-gray-500">図書館の棚を確認中...</p>
                </div>

                <div v-else-if="availability && availability.length > 0" class="space-y-3">
                    <p class="text-sm text-gray-500 mb-2">あなたの地域の図書館状況:</p>
                    <div v-for="(lib, index) in availability" :key="index" class="flex justify-between items-center p-3 bg-gray-50 rounded border border-gray-100">
                        <span class="font-medium text-gray-700">{{ lib.name }}</span>
                        <span :class="lib.class">{{ lib.status }}</span>
                    </div>
                </div>

                <div v-else class="text-center py-6 text-gray-500">
                    <p>この地域の図書館には蔵書情報が見つかりませんでした。</p>
                </div>
            </div>
            
            <div class="p-4 bg-gray-50 border-t text-right">
                <button @click="selectedBook = null" class="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300">閉じる</button>
            </div>
        </div>
    </div>

  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-clamp: 2; /* Standard property added */
  overflow: hidden;
}
@keyframes fade-in-up {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
.animate-fade-in-up {
    animation: fade-in-up 0.3s ease-out;
}
</style>