<!-- frontend/src/components/ChatInterface.vue -->
<template>
  <div class="chat-container">
    <!-- 消息列表 -->
    <div class="messages" ref="messagesContainer">
      <div
        v-for="(message, index) in messages"
        :key="index"
        :class="['message', message.role]"
      >
        <div class="message-header">
          <span class="avatar">{{ message.role === 'user' ? '👤' : '🤖' }}</span>
          <span class="role">{{ message.role === 'user' ? '您' : 'RAG助手' }}</span>
          <span class="time">{{ formatTime(message.timestamp) }}</span>
        </div>

        <div class="message-content" v-html="formatContent(message.content)"></div>

        <!-- 助手消息的额外信息 -->
        <div v-if="message.role === 'assistant' && message.retrievalContext" class="extra-info">
          <div class="sub-questions" v-if="message.retrievalContext.subQuestions?.length">
            <div class="section-title">相关子问题:</div>
            <div class="tags">
              <span
                v-for="(q, qIndex) in message.retrievalContext.subQuestions"
                :key="qIndex"
                class="tag"
                @click="selectSubQuestion(q)"
              >
                {{ q }}
              </span>
            </div>
          </div>

          <div class="retrieval-info">
            <div class="section-title">检索信息:</div>
            <div class="stats">
              <span class="stat">📚 知识: {{ message.retrievalContext.knowledge?.length || 0 }} 条</span>
              <span class="stat">🧠 记忆: {{ message.retrievalContext.memory?.length || 0 }} 条</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 加载指示器 -->
      <div v-if="loading" class="message assistant">
        <div class="message-header">
          <span class="avatar">🤖</span>
          <span class="role">RAG助手</span>
        </div>
        <div class="message-content loading">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <textarea
        v-model="inputText"
        @keydown.enter.exact.prevent="sendMessage"
        placeholder="输入您的问题... (按Enter发送，Shift+Enter换行)"
        rows="1"
        ref="textarea"
        @input="autoResize"
        :disabled="loading"
      ></textarea>

      <div class="input-controls">
        <button
          @click="clearChat"
          class="btn secondary"
          :disabled="loading"
        >
          清空对话
        </button>

        <div class="right-controls">
          <span class="char-count">{{ inputText.length }}/1000</span>
          <button
            @click="sendMessage"
            :disabled="!inputText.trim() || loading"
            class="btn primary"
          >
            <span v-if="loading">发送中...</span>
            <span v-else>发送</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { api, type Message } from '@/api/client'

// Props
const props = defineProps<{
  userId?: string
}>()

// Emits
const emit = defineEmits<{
  'message-sent': [message: string]
  'message-received': [message: string]
}>()

// Refs
const messages = ref<Message[]>([])
const inputText = ref('')
const loading = ref(false)
const textarea = ref<HTMLTextAreaElement | null>(null)
const messagesContainer = ref<HTMLDivElement | null>(null)

// 初始化消息
const initialMessages: Message[] = [
  {
    role: 'assistant',
    content: '您好！我是RAG智能助手，可以帮助您解答算法相关的问题。请问您想了解什么？',
    timestamp: new Date().toISOString()
  }
]

// 加载历史消息
const loadHistory = () => {
  const saved = localStorage.getItem('chat_history')
  if (saved) {
    try {
      messages.value = JSON.parse(saved)
    } catch {
      messages.value = [...initialMessages]
    }
  } else {
    messages.value = [...initialMessages]
  }
}

// 保存消息
const saveHistory = () => {
  localStorage.setItem('chat_history', JSON.stringify(messages.value))
}

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

  // 清空输入框
  inputText.value = ''

  // 触发事件
  emit('message-sent', text)

  // 保存到本地存储
  saveHistory()

  // 滚动到底部
  scrollToBottom()

  // 设置加载状态
  loading.value = true

  try {
    // 发送到后端
    const response = await api.query({
      question: text,
      user_id: props.userId || 'anonymous',
      session_id: localStorage.getItem('session_id') || undefined
    })

    // 添加助手消息
    const assistantMessage: Message = {
      role: 'assistant',
      content: response.response,
      timestamp: response.timestamp || new Date().toISOString(),
      retrievalContext: {
        knowledge: response.retrieval_context?.knowledge || [],
        memory: response.retrieval_context?.memory || [],
        subQuestions: response.sub_questions || []
      }
    }

    messages.value.push(assistantMessage)

    // 触发事件
    emit('message-received', response.response)

  } catch (error) {
    console.error('发送消息失败:', error)

    // 添加错误消息
    const errorMessage: Message = {
      role: 'assistant',
      content: '抱歉，处理您的请求时出现了错误。请稍后再试。',
      timestamp: new Date().toISOString(),
      retrievalContext: {
        knowledge: [],
        memory: [],
        subQuestions: []
      }
    }
    messages.value.push(errorMessage)

  } finally {
    loading.value = false
    saveHistory()
    scrollToBottom()
  }
}

// 清空对话
const clearChat = () => {
  if (confirm('确定要清空对话历史吗？')) {
    messages.value = [...initialMessages]
    localStorage.removeItem('chat_history')
    scrollToBottom()
  }
}

// 选择子问题
const selectSubQuestion = (question: string) => {
  inputText.value = question
  textarea.value?.focus()
}

// 格式化时间
const formatTime = (timestamp: string) => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 格式化内容
const formatContent = (content: string) => {
  return content
    .replace(/\n/g, '<br>')
    .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
}

// 自动调整输入框高度
const autoResize = () => {
  if (!textarea.value) return
  textarea.value.style.height = 'auto'
  textarea.value.style.height = Math.min(textarea.value.scrollHeight, 150) + 'px'
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 键盘快捷键
const handleKeyDown = (e: KeyboardEvent) => {
  // Ctrl+Enter 发送
  if (e.ctrlKey && e.key === 'Enter') {
    sendMessage()
  }

  // Escape 清空输入
  if (e.key === 'Escape') {
    inputText.value = ''
  }
}

// 生命周期
onMounted(() => {
  loadHistory()
  scrollToBottom()

  // 添加键盘事件监听
  document.addEventListener('keydown', handleKeyDown)

  // 生成会话ID
  if (!localStorage.getItem('session_id')) {
    localStorage.setItem('session_id', Date.now().toString())
  }

  // 检查后端健康状态
  api.healthCheck().then(health => {
    console.log('后端健康状态:', health)
  })
})

onUnmounted(() => {
  // 移除键盘事件监听
  document.removeEventListener('keydown', handleKeyDown)
})

// 导出方法
defineExpose({
  sendMessage,
  clearChat
})
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 800px;
  margin: 0 auto;
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: linear-gradient(135deg, #667eea10 0%, #764ba210 100%);
}

.message {
  margin-bottom: 20px;
  padding: 16px;
  border-radius: 12px;
  animation: fadeIn 0.3s ease;
}

.message.user {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  margin-left: 40px;
  border-bottom-right-radius: 4px;
}

.message.assistant {
  background: white;
  color: #333;
  margin-right: 40px;
  border-bottom-left-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
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

.message-header {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  font-size: 14px;
}

.message.user .message-header {
  color: rgba(255, 255, 255, 0.9);
}

.avatar {
  margin-right: 8px;
  font-size: 18px;
}

.role {
  font-weight: 600;
  margin-right: auto;
}

.time {
  font-size: 12px;
  opacity: 0.7;
}

.message-content {
  line-height: 1.6;
  word-break: break-word;
}

.message-content :deep(pre) {
  background: #f8f9fa;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
  border: 1px solid #e9ecef;
}

.message-content :deep(code) {
  background: #f1f3f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 0.9em;
}

.extra-info {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #e9ecef;
}

.section-title {
  font-size: 12px;
  color: #666;
  margin-bottom: 6px;
  font-weight: 500;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.tag {
  background: #e9ecef;
  color: #495057;
  padding: 4px 10px;
  border-radius: 16px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.tag:hover {
  background: #667eea;
  color: white;
  transform: translateY(-1px);
}

.stats {
  display: flex;
  gap: 16px;
}

.stat {
  font-size: 12px;
  color: #666;
  display: flex;
  align-items: center;
  gap: 4px;
}

.loading {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 24px;
}

.dot {
  width: 8px;
  height: 8px;
  background: #667eea;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
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
  min-height: 56px;
  max-height: 150px;
  overflow-y: auto;
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

.right-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.char-count {
  font-size: 12px;
  color: #6c757d;
  min-width: 60px;
  text-align: right;
}

.btn {
  padding: 8px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn.secondary {
  background: #f8f9fa;
  color: #495057;
}

.btn.secondary:hover:not(:disabled) {
  background: #e9ecef;
}

.btn.primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.btn.primary:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
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
</style>