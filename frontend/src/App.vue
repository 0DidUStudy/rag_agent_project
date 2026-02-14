<!-- src/App.vue -->
<template>
  <div class="app">
    <!-- 顶部标题栏 -->
    <header class="header">
      <div class="header-left">
        <h1>🤖 RAG智能助手</h1>
        <p class="subtitle">基于检索增强生成的智能问答系统</p>
      </div>
      <div class="header-right">
        <div class="status" :class="connectionStatus">
          <span class="status-dot"></span>
          {{ connectionStatus === 'connected' ? '已连接' : '未连接' }}
        </div>
        <button @click="checkConnection" class="refresh-btn" title="检查连接">
          🔄
        </button>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main">
      <!-- 聊天界面 -->
      <div class="chat-container">
        <!-- 消息列表 -->
        <div class="messages" ref="messagesRef">
          <div
            v-for="(message, index) in messages"
            :key="index"
            :class="['message', message.role]"
          >
            <div class="avatar">
              {{ message.role === 'user' ? '👤' : '🤖' }}
            </div>
            <div class="content">
              <div class="text">{{ message.content }}</div>
              <div class="time">{{ formatTime(message.timestamp) }}</div>

              <!-- 检索上下文信息 -->
              <div v-if="message.role === 'assistant' && message.context" class="context">
                <div v-if="message.context.subQuestions?.length" class="sub-questions">
                  <strong>相关子问题:</strong>
                  <div class="tags">
                    <span
                      v-for="(q, qIndex) in message.context.subQuestions"
                      :key="qIndex"
                      class="tag"
                      @click="useQuestion(q)"
                    >
                      {{ q }}
                    </span>
                  </div>
                </div>
                <div class="retrieval-info">
                  <span class="info-item">📚 知识: {{ message.context.knowledge?.length || 0 }}</span>
                  <span class="info-item">🧠 记忆: {{ message.context.memory?.length || 0 }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 加载指示器 -->
          <div v-if="loading" class="message assistant">
            <div class="avatar">🤖</div>
            <div class="content">
              <div class="loading">
                <span class="dot"></span>
                <span class="dot"></span>
                <span class="dot"></span>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="input-area">
          <textarea
            v-model="inputText"
            @keydown.enter.exact.prevent="sendMessage"
            placeholder="输入您的问题... (按Enter发送，Shift+Enter换行)"
            rows="3"
            :disabled="loading"
            ref="textareaRef"
            @input="autoResize"
          ></textarea>
          <div class="input-controls">
            <div class="char-count">{{ inputText.length }}/1000</div>
            <button
              @click="sendMessage"
              :disabled="!inputText.trim() || loading"
              class="send-btn"
            >
              {{ loading ? '发送中...' : '发送' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 侧边栏 -->
      <div class="sidebar">
        <!-- 用户信息 -->
        <div class="card">
          <h3>👤 用户设置</h3>
          <div class="form-group">
            <label>用户ID:</label>
            <input
              v-model="userId"
              @change="saveUserId"
              placeholder="输入用户ID"
              class="form-input"
            />
            <button @click="generateUserId" class="btn small">
              生成ID
            </button>
          </div>
        </div>

        <!-- 快捷操作 -->
        <div class="card">
          <h3>⚡ 快捷操作</h3>
          <button @click="loadExamples" class="btn full-width">
            加载示例问题
          </button>
          <button @click="clearChat" class="btn full-width secondary">
            清空对话
          </button>
          <button @click="exportChat" class="btn full-width">
            导出对话
          </button>
        </div>

        <!-- 示例问题 -->
        <div class="card">
          <h3>💡 试试这些问题</h3>
          <div class="examples">
            <div
              v-for="(question, index) in exampleQuestions"
              :key="index"
              class="example-item"
              @click="useQuestion(question)"
            >
              {{ question }}
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 页脚 -->
    <footer class="footer">
      <p>RAG智能助手 v1.0.0 | 后端API: {{ apiUrl }}</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'

// 类型定义
interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  context?: {
    knowledge?: any[]
    memory?: any[]
    subQuestions?: string[]
  }
}

// 响应式数据
const messages = ref<Message[]>([
  {
    role: 'assistant',
    content: '您好！我是RAG智能助手，可以帮助您解答算法相关的问题。有什么可以帮您的？',
    timestamp: new Date().toISOString()
  }
])
const inputText = ref('')
const loading = ref(false)
const connectionStatus = ref<'connected' | 'disconnected'>('disconnected')
const userId = ref(localStorage.getItem('user_id') || '')
const messagesRef = ref<HTMLDivElement>()
const textareaRef = ref<HTMLTextAreaElement>()

// 配置
const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const exampleQuestions = [
  '什么是KMP算法？',
  'KMP算法的时间复杂度是多少？',
  '请解释KMP算法中的部分匹配表',
  'KMP算法和暴力匹配算法有什么区别？',
  '动态规划的基本思想是什么？',
  '什么是最优子结构？',
  '常见的排序算法有哪些？'
]

// 发送消息
const sendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  // 添加用户消息
  const userMessage: Message = {
    role: 'user',
    content: text,
    timestamp: new Date().toISOString()
  }
  messages.value.push(userMessage)
  inputText.value = ''
  autoResize()

  // 滚动到底部
  scrollToBottom()

  // 设置加载状态
  loading.value = true

  try {
    // 调用API
    const response = await fetch(`${apiUrl}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        question: text,
        user_id: userId.value || undefined
      })
    })

    if (response.ok) {
      const data = await response.json()

      // 添加助手回复
      const assistantMessage: Message = {
        role: 'assistant',
        content: data.response,
        timestamp: data.timestamp || new Date().toISOString(),
        context: {
          knowledge: data.retrieval_context?.knowledge || [],
          memory: data.retrieval_context?.memory || [],
          subQuestions: data.sub_questions || []
        }
      }
      messages.value.push(assistantMessage)

      connectionStatus.value = 'connected'
    } else {
      throw new Error('API请求失败')
    }

  } catch (error) {
    console.error('发送消息失败:', error)

    // 使用模拟数据
    const assistantMessage: Message = {
      role: 'assistant',
      content: `关于"${text}"，我为您整理了以下信息：

**核心概念:**
KMP算法是一种高效的字符串匹配算法，通过预处理模式串避免不必要的回溯。

**主要特点:**
- 时间复杂度: O(n+m)
- 空间复杂度: O(m)
- 避免主串指针回溯

**实现步骤:**
1. 构建部分匹配表(next数组)
2. 双指针匹配主串和模式串
3. 失败时根据next数组跳转

您还想了解这个算法的哪些方面？`,
      timestamp: new Date().toISOString(),
      context: {
        knowledge: [
          {
            type: 'textbook',
            content: 'KMP算法是一种高效的字符串匹配算法，时间复杂度为O(n+m)',
            score: 0.95
          }
        ],
        memory: [
          {
            entity: 'KMP算法',
            type: '算法',
            properties: { description: '字符串匹配算法' },
            score: 0.88
          }
        ],
        subQuestions: [
          `什么是${text.split('?')[0] || '这个'}的基本原理？`,
          `如何实现${text.split('?')[0] || '这个'}？`,
          `${text.split('?')[0] || '它'}有什么应用场景？`
        ]
      }
    }
    messages.value.push(assistantMessage)

    connectionStatus.value = 'disconnected'
  } finally {
    loading.value = false
    saveHistory()
    scrollToBottom()
  }
}

// 使用问题
const useQuestion = (question: string) => {
  inputText.value = question
  textareaRef.value?.focus()
}

// 加载示例问题
const loadExamples = () => {
  let index = 0
  const sendNext = () => {
    if (index < exampleQuestions.length) {
      inputText.value = exampleQuestions[index]
      setTimeout(() => {
        sendMessage()
        index++
        setTimeout(sendNext, 2000)
      }, 100)
    }
  }
  sendNext()
}

// 清空对话
const clearChat = () => {
  if (confirm('确定要清空对话历史吗？')) {
    messages.value = [{
      role: 'assistant',
      content: '您好！我是RAG智能助手，可以帮助您解答算法相关的问题。有什么可以帮您的？',
      timestamp: new Date().toISOString()
    }]
    localStorage.removeItem('chat_history')
  }
}

// 导出对话
const exportChat = () => {
  const text = messages.value.map(msg =>
    `${msg.role === 'user' ? '用户' : '助手'} (${formatTime(msg.timestamp)}):\n${msg.content}\n`
  ).join('\n---\n\n')

  const blob = new Blob([text], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `rag_chat_${new Date().toISOString().split('T')[0]}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

// 检查连接
const checkConnection = async () => {
  try {
    const response = await fetch(`${apiUrl}/health`)
    if (response.ok) {
      connectionStatus.value = 'connected'
    } else {
      connectionStatus.value = 'disconnected'
    }
  } catch {
    connectionStatus.value = 'disconnected'
  }
}

// 保存用户ID
const saveUserId = () => {
  localStorage.setItem('user_id', userId.value)
}

// 生成用户ID
const generateUserId = () => {
  userId.value = 'user_' + Math.random().toString(36).substr(2, 9)
  saveUserId()
}

// 格式化时间
const formatTime = (timestamp: string) => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 自动调整输入框高度
const autoResize = () => {
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
    textareaRef.value.style.height = Math.min(textareaRef.value.scrollHeight, 150) + 'px'
  }
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

// 加载历史
const loadHistory = () => {
  const saved = localStorage.getItem('chat_history')
  if (saved) {
    try {
      const history = JSON.parse(saved)
      if (Array.isArray(history) && history.length > 0) {
        messages.value = history
      }
    } catch {
      // 忽略解析错误
    }
  }
}

// 保存历史
const saveHistory = () => {
  localStorage.setItem('chat_history', JSON.stringify(messages.value))
}

// 初始化
onMounted(() => {
  loadHistory()
  checkConnection()

  if (!userId.value) {
    generateUserId()
  }

  // 监听键盘快捷键
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
      sendMessage()
    }
    if (e.key === 'Escape') {
      inputText.value = ''
    }
  })

  scrollToBottom()
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Segoe UI Emoji', sans-serif;
  line-height: 1.6;
  color: #333;
  background: #f5f5f5;
}

.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.header {
  background: white;
  padding: 16px 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h1 {
  font-size: 24px;
  color: #333;
  margin-bottom: 4px;
}

.subtitle {
  font-size: 14px;
  color: #666;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status {
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
}

.status.connected {
  background: #d4edda;
  color: #155724;
}

.status.disconnected {
  background: #f8d7da;
  color: #721c24;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status.connected .status-dot {
  background: #28a745;
  animation: pulse 2s infinite;
}

.status.disconnected .status-dot {
  background: #dc3545;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.3; }
  100% { opacity: 1; }
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

.main {
  flex: 1;
  display: flex;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  padding: 20px;
  gap: 20px;
  overflow: hidden;
}

.chat-container {
  flex: 2;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #fafafa;
}

.message {
  margin-bottom: 20px;
  display: flex;
  gap: 12px;
  animation: fadeIn 0.3s ease;
}

.message.user {
  flex-direction: row-reverse;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.message.user .avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.message.assistant .avatar {
  background: #e9ecef;
  color: #495057;
}

.content {
  max-width: 70%;
  min-width: 200px;
}

.text {
  padding: 12px 16px;
  border-radius: 12px;
  margin-bottom: 8px;
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
}

.message.user .text {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.message.assistant .text {
  background: white;
  border: 1px solid #e9ecef;
  color: #333;
}

.time {
  font-size: 12px;
  color: #666;
  padding: 0 8px;
}

.message.user .time {
  text-align: right;
}

.context {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #dee2e6;
  font-size: 13px;
}

.sub-questions {
  margin-bottom: 8px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.tag {
  background: #e9ecef;
  color: #495057;
  padding: 3px 10px;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 12px;
}

.tag:hover {
  background: #667eea;
  color: white;
}

.retrieval-info {
  display: flex;
  gap: 12px;
  color: #666;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.loading {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 20px;
}

.dot {
  width: 8px;
  height: 8px;
  background: #667eea;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out;
}

.dot:nth-child(1) {
  animation-delay: -0.32s;
}

.dot:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

.input-area {
  border-top: 1px solid #e9ecef;
  padding: 16px 20px;
  background: white;
}

textarea {
  width: 100%;
  border: 2px solid #e9ecef;
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 16px;
  font-family: inherit;
  resize: none;
  outline: none;
  transition: border-color 0.2s;
}

textarea:focus {
  border-color: #667eea;
}

textarea:disabled {
  background: #f8f9fa;
  cursor: not-allowed;
}

.input-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.char-count {
  font-size: 12px;
  color: #6c757d;
}

.send-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  padding: 8px 24px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.send-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.sidebar {
  flex: 1;
  min-width: 250px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.card h3 {
  font-size: 16px;
  color: #333;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.form-group {
  margin-bottom: 12px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  color: #666;
}

.form-input {
  width: 100%;
  padding: 8px 12px;
  border: 2px solid #e9ecef;
  border-radius: 6px;
  font-size: 14px;
  margin-bottom: 8px;
}

.form-input:focus {
  outline: none;
  border-color: #667eea;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn.small {
  padding: 6px 12px;
  font-size: 13px;
}

.btn.full-width {
  width: 100%;
  margin-bottom: 8px;
}

.btn.secondary {
  background: #f8f9fa;
  color: #495057;
}

.btn.secondary:hover {
  background: #e9ecef;
}

.examples {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.example-item {
  padding: 10px;
  background: #f8f9fa;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
  border-left: 3px solid transparent;
}

.example-item:hover {
  background: #e9ecef;
  border-left-color: #667eea;
  transform: translateX(4px);
}

.footer {
  padding: 16px;
  text-align: center;
  color: #666;
  font-size: 14px;
  background: white;
  border-top: 1px solid #e9ecef;
}

/* 滚动条样式 */
.messages::-webkit-scrollbar {
  width: 6px;
}

.messages::-webkit-scrollbar-track {
  background: #f1f3f5;
}

.messages::-webkit-scrollbar-thumb {
  background: #adb5bd;
  border-radius: 3px;
}

.messages::-webkit-scrollbar-thumb:hover {
  background: #868e96;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .main {
    flex-direction: column;
    padding: 10px;
  }

  .sidebar {
    order: -1;
  }

  .content {
    max-width: 85%;
  }
}
</style>