// src/api/client.ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface QueryResponse {
  response: string
  retrieval_context: {
    knowledge: Array<{
      type: string
      content: string
      score: number
    }>
    memory: Array<{
      entity: string
      type: string
      properties: Record<string, any>
      score: number
    }>
    sub_questions: string[]
  }
  sub_questions: string[]
  timestamp: string
}

export const api = {
  async query(question: string, userId?: string): Promise<QueryResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question,
          user_id: userId
        })
      })

      if (!response.ok) {
        throw new Error('API请求失败')
      }

      return await response.json()
    } catch (error) {
      console.error('查询失败:', error)
      throw error
    }
  },

  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE_URL}/health`)
      return response.ok
    } catch {
      return false
    }
  }
}