# backend/src/services/llm_service.py
import requests
import json
from typing import List, Dict, Any
from config.settings import settings


class LLMService:
    """大语言模型服务"""

    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.api_url = settings.DEEPSEEK_API_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def chat_completion(self, messages: List[Dict], temperature=0.7, max_tokens=2000):
        """调用DeepSeek API"""
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"LLM API Error: {e}")
            return None

    def generate_sub_questions(self, question: str, context: str = None) -> List[str]:
        """生成子问题"""
        prompt = f"""
        根据以下主问题，生成3-5个相关的子问题：
        主问题：{question}
        {f'上下文：{context}' if context else ''}

        请返回JSON格式的列表，例如：["子问题1", "子问题2", "子问题3"]
        """

        messages = [
            {"role": "system", "content": "你是一个专业的AI助手，擅长将复杂问题分解为子问题。"},
            {"role": "user", "content": prompt}
        ]

        response = self.chat_completion(messages)
        try:
            return json.loads(response)
        except:
            # 如果JSON解析失败，尝试提取问题
            questions = []
            for line in response.split('\n'):
                if '?' in line and len(line.strip()) > 10:
                    questions.append(line.strip().strip('"').strip("'"))
            return questions or [question]

    def extract_entities_relations(self, text: str) -> Dict[str, Any]:
        """提取实体和关系"""
        prompt = f"""
        从以下文本中提取实体和关系：
        文本：{text}

        要求：
        1. 识别所有重要实体
        2. 提取实体之间的关系
        3. 返回JSON格式：
        {{
            "entities": [
                {{"entity": "实体名", "type": "实体类型"}}
            ],
            "relations": [
                {{"subject": "主体实体", "relation": "关系类型", "object": "客体实体"}}
            ]
        }}
        """

        messages = [
            {"role": "system", "content": "你是信息抽取专家，擅长识别文本中的实体和关系。"},
            {"role": "user", "content": prompt}
        ]

        response = self.chat_completion(messages)
        try:
            return json.loads(response)
        except:
            return {"entities": [], "relations": []}