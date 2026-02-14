<!-- frontend/src/views/HomeView.vue -->
<template>
  <div class="home-container">
    <!-- 顶部标题栏 -->
    <header class="header">
      <div class="logo">
        <h1>🤖 RAG智能助手</h1>
        <p class="subtitle">基于检索增强生成的智能问答系统</p>
      </div>

      <div class="status-info">
        <div class="status-item" :class="systemStatus">
          <span class="status-dot"></span>
          {{ statusText }}
        </div>
        <button @click="refreshStatus" class="refresh-btn" title="刷新状态">
          🔄
        </button>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 聊天界面 -->
      <ChatInterface
        ref="chatRef"
        :user-id="userId"
        class="chat-interface"
      />

      <!-- 侧边栏 -->
      <aside class="sidebar">
        <!-- 用户信息 -->
        <div class="card user-card">
          <h3>👤 用户信息</h3>
          <input
            v-model="userId"
            placeholder="输入用户ID（可选）"
            class="user-input"
            @change="saveUserId"
          />
          <button @click="generateUserId" class="btn small">
            生成ID
          </button>
        </div>

        <!-- 系统信息 -->
        <div class="card system-card">
          <h3>⚙️ 系统信息</h3>
          <div class="info-item">
            <span class="label">后端状态:</span>
            <span :class="['value', systemStatus]">
              {{ systemStatus === 'connected' ? '已连接' : '未连接' }}
            </span>
          </div>
          <div class="info-item">
            <span class="label">对话数:</span>
            <span class="value">{{ messageCount }}</span>
          </div>
          <div class="info-item">
            <span class="label">版本:</span>
            <span class="value">v1.0.0</span>
          </div>
        </div>

        <!-- 快捷操作 -->
        <div class="card actions-card">
          <h3>🚀 快捷操作</h3>
          <div class="quick-actions">
            <button @click="loadExampleQuestions" class="action-btn">
              加载示例问题
            </button>
            <button @click="exportChat" class="action-btn">
              导出对话
            </button>
            <button @click="clearAll" class="action-btn danger">
              清空所有
            </button>
          </div>
        </div>

        <!-- 示例问题 -->
        <div class="card examples-card">
          <h3>💡 试试这些问题</h3>
          <div class="examples">
            <div
              v-for="(question, index) in exampleQuestions"
              :key="index"
              class="example-question"
              @click="sendExampleQuestion(question)"
            >
              {{ question }}
            </div>
          </div>
        </div>
      </aside>
    </main>

    <!-- 页脚 -->
    <footer class="footer">
      <p>RAG智能助手 &copy; 2024 | 基于DeepSeek API + MySQL + Neo4j</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import ChatInterface from '@/components/ChatInterface.vue'
import { api } from '@/api/client'

// Refs
const chatRef = ref<InstanceType<typeof ChatInterface> | null>(null)
const userId = ref(localStorage.getItem('user_id') || '')
const systemStatus = ref('checking')
const statusText = ref('检查连接...')
const messageCount = ref(0)

// 示例问题
const exampleQuestions = [
  '什么是KMP算法？',
  'KMP算法的时间复杂度是多少？',
  '请解释KMP算法中的部分匹配表',
  'KMP算法和暴力匹配算法有什么区别？',
  '如何实现KMP算法的next数组？'
]

// 保存用户ID
const saveUserId = () => {
  localStorage.setItem('user_id', userId.value)
}

// 生成用户ID
const generateUserId = () => {
  const randomId = 'user_' + Math.random().toString(36).substr(2, 9)
  userId.value = randomId
  saveUserId()
}

// 刷新系统状态
const refreshStatus = async () => {
  systemStatus.value = 'checking'
  statusText.value = '检查连接...'

  try {
    const health = await api.healthCheck()
    if (health.status === 'healthy') {
      systemStatus.value = 'connected'
      statusText.value = '系统正常'
    } else {
      systemStatus.value = 'disconnected'
      statusText.value = '连接异常'
    }
  } catch {
    systemStatus.value = 'disconnected'
    statusText.value = '连接失败'
  }
}

// 发送示例问题
const sendExampleQuestion = (question: string) => {
  if (chatRef.value) {
    // 直接调用聊天组件的方法发送消息
    const textarea = document.querySelector('textarea')
    if (textarea) {
      textarea.value = question
      textarea.dispatchEvent(new Event('input'))
      chatRef.value.sendMessage()
    }
  }
}

// 加载示例问题
const loadExampleQuestions = () => {
  exampleQuestions.forEach((q, index) => {
    setTimeout(() => {
      sendExampleQuestion(q)
    }, index * 2000)
  })
}

// 导出对话
const exportChat = () => {
  const messages = JSON.parse(localStorage.getItem('chat_history') || '[]')
  const text = messages.map((msg: any) =>
    `${msg.role === 'user' ? '用户' : '助手'} (${new Date(msg.timestamp).toLocaleString()}):\n${msg.content}\n`
  ).join('\n---\n\n')

  const blob = new Blob([text], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `rag_chat_${new Date().toISOString().split('T')[0]}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

// 清空所有
const clearAll = () => {
  if (confirm('确定要清空所有对话数据和设置吗？')) {
    localStorage.clear()
    location.reload()
  }
}

// 更新消息计数
const updateMessageCount = () => {
  const messages = JSON.parse(localStorage.getItem('chat_history') || '[]')
  messageCount.value = messages.filter((msg: any) => msg.role === 'user').length
}

// 监听消息变化
const handleMessageSent = () => {
  setTimeout(updateMessageCount, 100)
}

// 初始化
onMounted(() => {
  // 检查系统状态
  refreshStatus()

  // 更新消息计数
  updateMessageCount()

  // 如果没有用户ID，生成一个
  if (!userId.value) {
    generateUserId()
  }
})
</script>

<style scoped>
.home-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: white;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
  z-index: 10;
}

.logo h1 {
  margin: 0;
  font-size: 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  margin: 4px 0 0;
  color: #6c757d;
  font-size: 14px;
}

.status-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
}

.status-item.connected {
  background: #d4edda;
  color: #155724;
}

.status-item.disconnected {
  background: #f8d7da;
  color: #721c24;
}

.status-item.checking {
  background: #fff3cd;
  color: #856404;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-item.connected .status-dot {
  background: #28a745;
  animation: pulse 2s infinite;
}

.status-item.disconnected .status-dot {
  background: #dc3545;
}

.status-item.checking .status-dot {
  background: #ffc107;
  animation: blink 1s infinite;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.3; }
  100% { opacity: 1; }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.refresh-btn {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  padding: 8px;
  border-radius: 50%;
  transition: all 0.2s;
}

.refresh-btn:hover {
  background: #f8f9fa;
  transform: rotate(90deg);
}

.main-content {
  display: grid;
  grid-template-columns: 1fr 300px;
  flex: 1;
  overflow: hidden;
  gap: 20px;
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

.chat-interface {
  grid-column: 1;
  height: 100%;
}

.sidebar {
  grid-column: 2;
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow-y: auto;
}

.card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.card h3 {
  margin: 0 0 16px;
  font-size: 16px;
  color: #333;
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-input {
  width: 100%;
  padding: 10px;
  margin: 12px 0;
  border: 2px solid #e9ecef;
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.user-input:focus {
  outline: none;
  border-color: #667eea;
}

.btn.small {
  padding: 6px 16px;
  font-size: 13px;
  width: 100%;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 10px 0;
  font-size: 14px;
}

.label {
  color: #6c757d;
}

.value {
  font-weight: 500;
}

.value.connected {
  color: #28a745;
}

.value.disconnected {
  color: #dc3545;
}

.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.action-btn {
  padding: 10px;
  border: none;
  border-radius: 8px;
  background: #f8f9fa;
  color: #495057;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}

.action-btn:hover {
  background: #e9ecef;
  transform: translateY(-1px);
}

.action-btn.danger {
  background: #fff5f5;
  color: #dc3545;
}

.action-btn.danger:hover {
  background: #ffe3e3;
}

.examples {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.example-question {
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
  font-size: 14px;
  color: #495057;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.example-question:hover {
  background: #e9ecef;
  border-color: #667eea;
  transform: translateY(-2px);
}

.footer {
  padding: 16px;
  text-align: center;
  color: #6c757d;
  font-size: 14px;
  background: white;
  border-top: 1px solid #e9ecef;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .main-content {
    grid-template-columns: 1fr;
  }

  .sidebar {
    display: none;
  }
}
</style>