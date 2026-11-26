<template>
  <div class="min-h-screen bg-slate-50 text-slate-800 text-sm">
    <!-- 管理者キー入力 -->
    <div v-if="!adminKey" class="max-w-md mx-auto mt-24 bg-white border border-slate-200 rounded-lg p-6 shadow-sm">
      <h1 class="text-lg font-bold mb-4">LiVraria Debug</h1>
      <form @submit.prevent="submitKey" class="space-y-3">
        <input v-model="keyInput" type="password" placeholder="LIVRARIA_ADMIN_KEY"
               class="w-full border border-slate-300 rounded px-3 py-2" autocomplete="off" />
        <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white rounded px-3 py-2">開く</button>
      </form>
    </div>

    <div v-else class="p-4 space-y-4">
      <!-- ヘッダー -->
      <div class="flex flex-wrap items-center gap-3">
        <h1 class="text-lg font-bold">LiVraria Debug</h1>
        <button @click="reloadAll" class="px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-700">更新</button>
        <button @click="clearKey" class="px-3 py-1 rounded bg-slate-200 hover:bg-slate-300">キーを消す</button>
        <form @submit.prevent="searchTrace" class="flex items-center gap-2 ml-auto">
          <input v-model="searchInput" type="text" placeholder="trace_id（先頭8文字で前方一致）"
                 class="w-72 border border-slate-300 rounded px-2 py-1 font-mono" />
          <button type="submit" class="px-3 py-1 rounded bg-slate-700 text-white hover:bg-slate-800">検索</button>
        </form>
      </div>
      <p v-if="errorMessage" class="bg-red-50 border border-red-300 text-red-700 rounded px-3 py-2">{{ errorMessage }}</p>
      <p v-if="searchMessage" class="text-slate-500">{{ searchMessage }}</p>

      <!-- 使用量 -->
      <div class="bg-white border border-slate-200 rounded-lg p-3">
        <div class="font-semibold mb-2">
          LLM 使用量
          <span v-if="usage" class="font-normal text-slate-500">（{{ usage.since }} から）</span>
        </div>
        <table class="w-full text-left">
          <thead class="text-slate-500">
            <tr>
              <th class="pr-3">役割</th><th class="pr-3">モデル</th>
              <th class="pr-3 text-right">calls</th><th class="pr-3 text-right">errors</th>
              <th class="pr-3 text-right">rate_limited</th>
              <th class="pr-3 text-right">入力トークン</th><th class="text-right">出力トークン</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in usageRows" :key="row.role" class="border-t border-slate-100">
              <td class="pr-3 font-mono">{{ row.role }}</td>
              <td class="pr-3 font-mono">{{ row.model }}</td>
              <td class="pr-3 text-right">{{ row.calls }}</td>
              <td class="pr-3 text-right" :class="row.errors ? 'text-red-600' : ''">{{ row.errors }}</td>
              <td class="pr-3 text-right">{{ row.rate_limited }}</td>
              <td class="pr-3 text-right">{{ row.input_tokens }}</td>
              <td class="text-right">{{ row.output_tokens }}</td>
            </tr>
            <tr v-if="!usageRows.length"><td colspan="7" class="text-slate-400 pt-1">データなし</td></tr>
          </tbody>
        </table>
      </div>

      <div class="flex gap-4 items-start">
        <!-- 左: セッションとターン -->
        <div class="w-1/3 space-y-4">
          <div class="bg-white border border-slate-200 rounded-lg">
            <div class="px-3 py-2 font-semibold border-b border-slate-100">セッション</div>
            <ul class="max-h-64 overflow-y-auto">
              <li v-for="s in sessions" :key="s.session_id" @click="selectSession(s.session_id)"
                  class="px-3 py-2 cursor-pointer border-b border-slate-100 hover:bg-slate-50"
                  :class="s.session_id === selectedSessionId ? 'bg-blue-50' : ''">
                <div class="font-mono">{{ (s.session_id || '(none)').slice(0, 8) }}
                  <span class="text-slate-500">{{ s.user_id || '-' }}</span></div>
                <div class="text-xs text-slate-500">{{ s.turns }} ターン / {{ s.last_at }}</div>
              </li>
              <li v-if="!sessions.length" class="px-3 py-2 text-slate-400">セッションなし</li>
            </ul>
          </div>
          <div class="bg-white border border-slate-200 rounded-lg">
            <div class="px-3 py-2 font-semibold border-b border-slate-100">ターン</div>
            <ul class="max-h-[32rem] overflow-y-auto">
              <li v-for="t in turns" :key="t.trace_id" @click="selectTurn(t.trace_id)"
                  class="px-3 py-2 cursor-pointer border-b border-slate-100 hover:bg-slate-50"
                  :class="t.trace_id === selectedTraceId ? 'bg-blue-50' : ''">
                <div class="text-xs font-mono" :class="t.failed ? 'text-red-600' : 'text-slate-500'">
                  {{ t.trace_id.slice(0, 8) }} {{ t.started_at }}<span v-if="t.graph"> [{{ t.graph }}]</span><span v-if="t.failed"> FAILED</span>
                </div>
                <div class="truncate">U: {{ t.user_message }}</div>
                <div class="truncate" :class="t.failed ? 'text-red-600' : 'text-slate-600'">AI: {{ t.response_text || '-' }}</div>
              </li>
              <li v-if="!turns.length" class="px-3 py-2 text-slate-400">ターンなし</li>
            </ul>
          </div>
        </div>

        <!-- 右: グラフとステップ詳細 -->
        <div class="flex-1 space-y-4 min-w-0">
          <div class="bg-white border border-slate-200 rounded-lg p-3">
            <div class="font-semibold mb-2">
              グラフ <span class="font-normal text-slate-500 font-mono">{{ shownGraphVersion }}</span>
              <span v-if="graphVersion" class="font-normal text-slate-400">（LIVRARIA_GRAPH={{ graphVersion }}）</span>
            </div>
            <div v-if="graphError" class="text-red-600">{{ graphError }}</div>
            <div ref="graphEl" class="overflow-x-auto" data-testid="graph"></div>
          </div>

          <div class="bg-white border border-slate-200 rounded-lg p-3 space-y-3" data-testid="detail">
            <div class="font-semibold">ステップ詳細</div>
            <template v-if="turn">
              <div class="text-xs font-mono text-slate-500">{{ turn.trace_id }}</div>
              <div><span class="text-slate-500">ユーザー:</span> {{ turn.user_message }}</div>
              <div><span class="text-slate-500">応答:</span> {{ turn.response_text || '-' }}</div>
              <!-- 会話グラフ v2 のターンの要約 -->
              <div v-if="turn.graph === 'v2'" class="bg-amber-50 border border-amber-200 rounded p-2 space-y-1" data-testid="v2-summary">
                <div>
                  <span class="text-slate-500">意図:</span> <span class="font-mono">{{ turn.intent || '-' }}</span>
                  <span class="text-slate-500 ml-3">振り分け:</span> <span class="font-mono">{{ turn.route || '-' }}</span>
                </div>
                <div><span class="text-slate-500">経路:</span> <span class="font-mono">{{ (turn.path || []).join(' → ') || '-' }}</span></div>
                <div class="text-xs">
                  <span class="font-semibold">読書プロフィール</span>
                  <pre class="whitespace-pre-wrap bg-white rounded p-1">{{ JSON.stringify(turn.profile || {}, null, 2) }}</pre>
                </div>
                <div class="text-xs">
                  <span class="font-semibold">レファ協の手がかり（内部用）</span>
                  <ul v-if="turn.crd_hints && turn.crd_hints.length" class="bg-white rounded p-1 space-y-1">
                    <li v-for="(h, i) in turn.crd_hints" :key="'h' + i">
                      <div>{{ h.question || '-' }}</div>
                      <div class="text-slate-500">キーワード: {{ (h.keywords || []).join('、') || '-' }} / NDC: {{ (h.ndc || []).join('、') || '-' }}</div>
                      <div v-if="h.process" class="text-slate-500">探し方: {{ h.process }}</div>
                    </li>
                  </ul>
                  <div v-else class="text-slate-400">なし</div>
                </div>
              </div>
              <div v-if="turn.error" class="bg-red-50 border border-red-300 rounded p-2 text-red-700">
                <div class="font-semibold">ターンのエラー: {{ turn.error.type }}: {{ turn.error.message }}</div>
                <div class="text-xs text-red-500">
                  <template v-if="turn.steps.length">最後のステップ（{{ turn.steps[turn.steps.length - 1].node }}）の次で発生</template>
                  <template v-else>最初のステップの前に発生</template>
                </div>
                <pre class="text-xs whitespace-pre-wrap mt-1">{{ turn.error.traceback }}</pre>
              </div>
              <div v-for="step in turn.steps" :key="step.index" class="border border-slate-200 rounded p-2 space-y-1">
                <div class="font-semibold">
                  #{{ step.index }} <span class="font-mono">{{ step.node }}</span>
                  <span class="font-normal text-slate-500">attempt {{ step.attempt }} / {{ step.duration_ms }} ms</span>
                </div>
                <div v-if="step.ai_text" class="whitespace-pre-wrap">AI: {{ step.ai_text }}</div>
                <div v-for="(c, i) in step.tool_calls" :key="'c' + i" class="text-xs">
                  <span class="font-mono font-semibold">call {{ c.name }}</span>
                  <pre class="whitespace-pre-wrap bg-slate-50 rounded p-1">{{ JSON.stringify(c.args, null, 2) }}</pre>
                </div>
                <div v-for="(r, i) in step.tool_results" :key="'r' + i" class="text-xs">
                  <span class="font-mono font-semibold">result {{ r.name }}</span>
                  <pre class="whitespace-pre-wrap bg-slate-50 rounded p-1">{{ r.content }}</pre>
                </div>
                <div v-if="step.usage" class="text-xs text-slate-500">
                  tokens: in {{ step.usage.input_tokens ?? '-' }} / out {{ step.usage.output_tokens ?? '-' }} / total {{ step.usage.total_tokens ?? '-' }}
                </div>
                <div v-if="step.error" class="bg-red-50 border border-red-300 rounded p-2 text-red-700">
                  <div class="font-semibold">{{ step.error.type }}: {{ step.error.message }}</div>
                  <pre class="text-xs whitespace-pre-wrap">{{ step.error.traceback }}</pre>
                </div>
              </div>
              <div v-if="!turn.steps.length" class="text-slate-400">ステップなし</div>
            </template>
            <div v-else class="text-slate-400">ターンを選んでください</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import mermaid from 'mermaid';
import { debugApi } from '../services/debugApi';

const STORAGE_KEY = 'livraria_admin_key';
// /debug/graph の mermaid に現れるノード id（色付け対象）
const GRAPH_NODES = {
  v1: ['agent', 'tools', 'force_tool'],
  v2: ['understand', 'route', 'interview', 'crd', 'plan', 'search', 'select', 'answer'],
};

const readStoredKey = () => {
  try { return sessionStorage.getItem(STORAGE_KEY) || ''; } catch { return ''; }
};

const adminKey = ref(readStoredKey());
const keyInput = ref('');
const searchInput = ref('');
const searchMessage = ref('');
const errorMessage = ref('');
const graphError = ref('');

const usage = ref(null);
const sessions = ref([]);
const turns = ref([]);
const turn = ref(null);
const selectedSessionId = ref(null);
const selectedTraceId = ref(null);
const mermaidText = ref('');
const graphs = ref({});
const graphVersion = ref('');
const graphEl = ref(null);

let renderCount = 0;

const usageRows = computed(() => {
  if (!usage.value) return [];
  const roles = usage.value.roles || {};
  const models = usage.value.models || {};
  const names = [...new Set([...Object.keys(models), ...Object.keys(roles)])];
  return names.map((role) => ({
    role,
    model: models[role] || '-',
    calls: 0, errors: 0, rate_limited: 0, input_tokens: 0, output_tokens: 0,
    ...(roles[role] || {}),
  }));
});

const showError = (e) => {
  if (e && (e.status === 401 || e.status === 403 || e.status === 503)) {
    errorMessage.value = `管理者キーのエラー (${e.message})`;
  } else {
    errorMessage.value = `取得に失敗しました: ${e?.message || e}`;
  }
};

const submitKey = () => {
  const key = keyInput.value.trim();
  if (!key) return;
  try { sessionStorage.setItem(STORAGE_KEY, key); } catch { /* 保存できなくても動かす */ }
  adminKey.value = key;
  keyInput.value = '';
  reloadAll();
};

const clearKey = () => {
  try { sessionStorage.removeItem(STORAGE_KEY); } catch { /* 無視 */ }
  adminKey.value = '';
  usage.value = null;
  sessions.value = [];
  turns.value = [];
  turn.value = null;
  selectedSessionId.value = null;
  selectedTraceId.value = null;
  mermaidText.value = '';
  graphs.value = {};
  graphVersion.value = '';
  errorMessage.value = '';
};

const loadUsage = async () => { usage.value = await debugApi.getUsage(adminKey.value); };
const loadSessions = async () => { sessions.value = (await debugApi.getSessions(adminKey.value)).sessions; };
const loadTurns = async () => {
  if (selectedSessionId.value == null) { turns.value = []; return; }
  turns.value = (await debugApi.getTurns(adminKey.value, selectedSessionId.value)).turns;
};
const loadGraph = async () => {
  const data = await debugApi.getGraph(adminKey.value);
  mermaidText.value = data.mermaid;
  graphs.value = data.graphs || {};
  graphVersion.value = data.version || '';
};

// 選んだターンの版のグラフを表示する（ターンを選ぶ前は今の LIVRARIA_GRAPH の版）
const shownGraphVersion = computed(() => turn.value?.graph || graphVersion.value || 'v1');
const shownMermaid = computed(() => graphs.value[shownGraphVersion.value] || mermaidText.value);

const reloadAll = async () => {
  errorMessage.value = '';
  const results = await Promise.allSettled([loadUsage(), loadSessions(), loadTurns(), loadGraph()]);
  const failed = results.find((r) => r.status === 'rejected');
  if (failed) showError(failed.reason);
};

const selectSession = async (sessionId) => {
  selectedSessionId.value = sessionId;
  try { await loadTurns(); } catch (e) { showError(e); }
};

const selectTurn = async (traceId) => {
  selectedTraceId.value = traceId;
  try {
    turn.value = await debugApi.getTurn(adminKey.value, traceId);
  } catch (e) { showError(e); }
};

// 読み込み済みのターンから先頭一致で探し、なければ全文一致のときだけ API で取る
const searchTrace = async () => {
  const q = searchInput.value.trim().toLowerCase();
  searchMessage.value = '';
  if (!q) return;
  const hit = turns.value.find((t) => t.trace_id.toLowerCase().startsWith(q));
  if (hit) { await selectTurn(hit.trace_id); return; }
  try {
    await selectTurn(q);
    if (turn.value?.trace_id !== q) searchMessage.value = '見つかりませんでした';
  } catch {
    searchMessage.value = '見つかりませんでした';
  }
};

// 選んだターンの nodes に含まれるノードだけを色付けして描き直す
const visitedIds = computed(() => {
  const nodes = turn.value?.steps?.map((s) => s.node) || [];
  return (GRAPH_NODES[shownGraphVersion.value] || GRAPH_NODES.v1).filter((id) => nodes.includes(id));
});

const renderGraph = async () => {
  if (!shownMermaid.value || !graphEl.value) return;
  let text = shownMermaid.value;
  if (visitedIds.value.length) {
    text += `\n\tclassDef visited fill:#fde68a,stroke:#d97706;\n\tclass ${visitedIds.value.join(',')} visited;\n`;
  }
  try {
    const { svg } = await mermaid.render(`debug-graph-${++renderCount}`, text);
    graphEl.value.innerHTML = svg;
    graphError.value = '';
  } catch (e) {
    graphError.value = `グラフの描画に失敗しました: ${e?.message || e}`;
  }
};

watch([shownMermaid, visitedIds], () => nextTick(renderGraph));

onMounted(() => {
  mermaid.initialize({ startOnLoad: false });
  if (adminKey.value) reloadAll();
});
</script>
