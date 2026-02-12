<script setup>
import { ref, onMounted, computed, nextTick, watch } from 'vue';
import { getAuth } from 'firebase/auth';
import { api } from '../services/api';

// 既存の変数...
const query = ref(''); // 初期値は空にする（onMountedで設定）
const semanticSearch = ref(false);
const books = ref([]);
const loading = ref(false);
const error = ref(null);

// 図書館関連の変数
const myLibraries = ref([]); // 【検索対象】に選ばれた図書館リスト
const allLibraries = ref([]); // 【県内の全】公立図書館リスト（ここから選ぶ）

const availability = ref(null);
const checkingStock = ref(false);
const selectedBook = ref(null);

// ★追加：図書館設定モーダル用の変数
const showLibModal = ref(false); // 設定画面の開閉
const libFilter = ref(''); // 図書館検索用のキーワード

// ★追加：設定画面で表示する図書館リスト（検索＋ソート）
const filteredAllLibraries = computed(() => {
    let libs = allLibraries.value;
    
    // 1. キーワードで絞り込み
    if (libFilter.value) {
        const k = libFilter.value.toLowerCase();
        libs = libs.filter(lib => lib.formal.toLowerCase().includes(k));
    }
    
    // 2. 名前順（五十音順っぽい感じ）にソート
    // 日本語のソートは localeCompare を使うとそこそこ綺麗に並ぶよ
    return libs.slice().sort((a, b) => a.formal.localeCompare(b.formal, 'ja'));
});

// ★追加：図書館の選択・解除を切り替える関数
const toggleLibrary = (lib) => {
    const index = myLibraries.value.findIndex(l => l.systemid === lib.systemid);
    if (index >= 0) {
        myLibraries.value.splice(index, 1); // 登録解除
    } else {
        myLibraries.value.push(lib); // 登録
    }
};

// ★追加：その図書館が選択済みかどうか判定する関数
const isSelected = (lib) => {
    return myLibraries.value.some(l => l.systemid === lib.systemid);
};

// ユーザーの居住地を取得してリストを準備
onMounted(async () => {
  console.log("BookSearch component mounted.");
  
  // SessionStorageから初期クエリを取得
  const initialQ = sessionStorage.getItem('livraria_search_query');
  
  if (initialQ) {
      query.value = initialQ;
      // 読み込んだら消す（リロード時などに残らないように）
      sessionStorage.removeItem('livraria_search_query');
  }

  try {
    const auth = getAuth();
    // ... (認証待ちのロジックはそのまま) ...
    await new Promise(resolve => {
        const unsubscribe = auth.onAuthStateChanged(user => {
            if (user) resolve(user);
            else resolve(null);
            unsubscribe();
        });
    });

    // 認証完了後に検索を実行 (初期クエリがある場合のみ)
    // 自動検索は行わない（ユーザー要望）
    /*
    if (query.value) {
        console.log("BookSearch executing initial search for:", query.value);
        searchBooks(); // awaitしない（並列実行）
    }
    */

    const user = auth.currentUser;
    if (user) {
        const token = await user.getIdToken();
        const userData = await api.getUser(user.uid, token);
        const pref = userData.personal?.live_pref || userData.personal?.address || userData.personal?.prefecture || '東京都'; 
        
        console.log(`User prefecture: ${pref}`);

        // 一気に2000件とってくる
        const libs = await api.searchLibraries(pref, 2000, token);
        
        if (Array.isArray(libs)) {
            // 重複排除などはそのまま
            const uniqueLibsMap = new Map();
            libs.forEach(lib => {
                if (!uniqueLibsMap.has(lib.systemid)) {
                    uniqueLibsMap.set(lib.systemid, lib);
                }
            });
            const uniqueLibs = Array.from(uniqueLibsMap.values());

            // 公立図書館だけに絞る
            const publicLibs = uniqueLibs.filter(lib => 
                !lib.systemid.startsWith('Special_') && 
                !lib.systemid.startsWith('Univ_')
            );

            // ★変更点：
            // ここでいきなり slice(0, 10) せず、まずは全リストに保存する
            allLibraries.value = publicLibs;

            // 初期値として、とりあえず上位5件だけを「検索対象」に入れておく（空だと困るから）
            // ユーザーがあとで変更できる
            myLibraries.value = publicLibs.slice(0, 5);
            
            console.log("All Public Libraries:", allLibraries.value);
        }
    }
  } catch (e) {
    console.error("Setup failed:", e);
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
    // ★追加: 現在のユーザーを取得してトークンを発行する
    const auth = getAuth();
    const user = auth.currentUser;
    if (!user) {
        throw new Error("ログインが必要です");
    }
    const token = await user.getIdToken();

    // APIを呼び出して本を検索
    const result = await api.searchBooks(query.value, token, semanticSearch.value);
    
    // ★ここを追加：コンソールで中身を見てみる（F12のConsoleタブで確認してね）
    console.log("検索結果の生データ:", result);

    // ★修正：データの構造に合わせて取り出し方を変える
    if (Array.isArray(result)) {
        // パターンA: Python側ですでにリストに整形されている場合（こっちの可能性が高い）
        books.value = result;
    } else if (result.Items) {
        // パターンB: 楽天APIの生の構造の場合
        books.value = result.Items.map(item => item.Item);
    } else {
        // パターンC: それ以外（エラーなど）
        console.warn("予期しないデータ形式です", result);
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
  // ★追加: もし図書館リストがまだ空なら、ここで再取得を試みる（保険）
  if (myLibraries.value.length === 0) {
      console.log("図書館リストが空のため、再取得を試みます...");
      try {
          const auth = getAuth();
          const user = auth.currentUser;
          if (user) {
              const token = await user.getIdToken();
              const userData = await api.getUser(user.uid, token);
              // 都道府県の場所が合っているか確認（address か prefecture か live_pref か）
              const pref = userData.personal?.live_pref || userData.personal?.address || userData.personal?.prefecture || '東京都';
              
              console.log(`Retry fetching libraries for: ${pref}`);
              
              // 範囲を広げて検索
              const allLibs = await api.searchLibraries(pref, 50, token);
              
              // 公立図書館だけに絞る
              const publicLibs = allLibs.filter(lib => !lib.systemid.startsWith('Special_'));
              myLibraries.value = publicLibs.slice(0, 10);
          }
      } catch (e) {
          console.error("再取得に失敗:", e);
      }
  }

  // それでもダメならアラートを出す
  if (myLibraries.value.length === 0) {
    alert("地域の図書館情報が取得できませんでした。\nユーザー設定の「居住地」が正しく登録されているか確認してください。");
    return;
  }

  selectedBook.value = book;
  checkingStock.value = true;
  availability.value = null;

  try {
    const auth = getAuth();
    const user = auth.currentUser;
    // ...以下、既存のコードのまま（トークン取得など）...
    if (!user) throw new Error("ログインが必要です");
    const token = await user.getIdToken();

    const systemIds = myLibraries.value.map(lib => lib.systemid).join(',');
    
    const result = await api.checkBookAvailability(book.isbn, systemIds, token);
    
    // カーリルのレスポンスを解析
    const statusMap = [];
    
    // ★修正: result.books の中から ISBN を探すように変更
    // (念のため result.books があるかチェックを入れています)
    const bookData = result.books ? result.books[book.isbn] : result[book.isbn]; 

    if (bookData) {
        myLibraries.value.forEach(lib => {
            const libStatus = bookData[lib.systemid];
            if (libStatus) {
                let statusText = '';
                let colorClass = '';

                // ★ここを修正: status='OK' だけで判断せず、必ず libkey の中身を見る
                const libkeys = libStatus.libkey || {};
                const values = Object.values(libkeys);

                if (values.length === 0) {
                    // libkeyが空っぽ = その図書館には本がない
                    statusText = '蔵書なし';
                    colorClass = 'text-gray-400';
                } else {
                    // 何かしらのデータがある場合
                    if (values.some(v => v === '貸出可')) {
                        // ひとつでも「貸出可」があればOK
                        statusText = '貸出可';
                        colorClass = 'text-green-600 font-bold';
                    } else {
                        // 本はあるけど、全部貸出中や館内閲覧のみの場合
                        statusText = '貸出中など';
                        colorClass = 'text-red-500';
                    }
                }

                // (補足) もしバックエンドの処理がタイムアウトして 'Running' のまま返ってきた場合の保険
                if (libStatus.status === 'Running') {
                    statusText = '確認中...';
                    colorClass = 'text-yellow-600';
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
        蔵書検索
    </h1>

    <div class="bg-white p-6 rounded-lg shadow-md mb-8">
        <div class="flex gap-2 mb-4">
            <input 
            v-model="query" 
            @keyup.enter="searchBooks"
            type="text" 
            placeholder="本のタイトル、著者など" 
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
 
        <div class="flex items-center justify-between bg-blue-50 p-3 rounded text-sm text-blue-800">
            <div>
                <span class="font-bold">検索対象の図書館:</span>
                <span v-if="myLibraries.length > 0" class="ml-2">
                    {{ myLibraries[0].formal }} など {{ myLibraries.length }}館
                </span>
                <span v-else class="ml-2 text-red-500 font-bold">
                    選択されていません
                </span>
            </div>
            <button 
                @click="showLibModal = true"
                class="text-blue-600 underline hover:text-blue-800 cursor-pointer font-bold"
            >
                設定を変更
            </button>
        </div>
    </div>

    <div v-if="error" class="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-6" role="alert">
      <p>{{ error }}</p>
    </div>
    <div v-if="books.length > 0" class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div v-for="book in books" :key="book.isbn" class="bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow p-4 flex gap-4 border border-gray-100">
             <div class="w-24 flex-shrink-0">
                <img :src="book.mediumImageUrl || 'https://placehold.co/100x150?text=No+Image'" alt="表紙" class="w-full rounded shadow-sm">
            </div>
            <div class="flex-1 flex flex-col justify-between">
                <div>
                    <h3 class="font-bold text-lg leading-tight mb-1 line-clamp-2">{{ book.title }}</h3>
                    <p class="text-sm text-gray-600 mb-2">{{ book.author }}</p>
                </div>
                <button 
                    @click="checkAvailability(book)"
                    class="mt-3 w-full bg-emerald-500 text-white py-2 px-4 rounded-md text-sm font-bold hover:bg-emerald-600 transition-colors flex items-center justify-center gap-1"
                >
                    図書館で探す
                </button>
            </div>
        </div>
    </div>


    <div v-if="showLibModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" @click.self="showLibModal = false">
        <div class="bg-white rounded-xl shadow-2xl max-w-2xl w-full h-[80vh] flex flex-col animate-fade-in-up">
            <div class="p-4 border-b flex justify-between items-center bg-gray-50 rounded-t-xl">
                <h3 class="font-bold text-lg">検索する図書館を選ぶ</h3>
                <button @click="showLibModal = false" class="text-gray-400 hover:text-gray-600 font-bold text-xl">✕</button>
            </div>

            <div class="p-4 border-b bg-white">
                <input 
                    v-model="libFilter" 
                    type="text" 
                    placeholder="図書館名で絞り込み（例: 長泉、沼津...）" 
                    class="w-full p-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
            </div>

            <div class="flex-1 overflow-y-auto p-4 bg-gray-50">
                <div v-if="filteredAllLibraries.length === 0" class="text-center text-gray-500 py-8">
                    該当する図書館が見つかりません
                </div>
                <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div 
                        v-for="lib in filteredAllLibraries" 
                        :key="lib.systemid"
                        @click="toggleLibrary(lib)"
                        class="p-3 rounded border cursor-pointer transition-colors flex items-center justify-between"
                        :class="isSelected(lib) ? 'bg-blue-100 border-blue-500 text-blue-900' : 'bg-white border-gray-200 hover:bg-gray-100'"
                    >
                        <span class="text-sm font-medium">{{ lib.formal }}</span>
                        <span v-if="isSelected(lib)" class="text-blue-600 font-bold">✓</span>
                    </div>
                </div>
            </div>

            <div class="p-4 border-t bg-white rounded-b-xl flex justify-between items-center">
                <span class="text-sm text-gray-600">
                    現在 {{ myLibraries.length }} 館を選択中
                </span>
                <button 
                    @click="showLibModal = false" 
                    class="px-6 py-2 bg-blue-600 text-white font-bold rounded hover:bg-blue-700"
                >
                    完了
                </button>
            </div>
        </div>
    </div>

    <div v-if="selectedBook" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" @click.self="selectedBook = null">
        <div class="bg-white rounded-xl shadow-2xl max-w-lg w-full overflow-hidden animate-fade-in-up">
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
