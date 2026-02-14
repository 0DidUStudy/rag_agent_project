# backend/src/services/data_synthesizer.py
from typing import List, Dict, Any
import json
from database.mysql_models import SessionLocal, TextbookKnowledge, QAPair
from services.llm_service import LLMService


class DataSynthesizer:
    """数据合成框架"""

    def __init__(self):
        self.llm_service = LLMService()

    def synthesize_qa_pairs(self, textbook_title: str, num_agents: int = 3) -> List[Dict]:
        """合成问答对"""
        # 1. 从知识库查询相关资料
        db_session = SessionLocal()
        try:
            textbook_content = db_session.query(TextbookKnowledge).filter(
                TextbookKnowledge.title.contains(textbook_title)
            ).all()

            if not textbook_content:
                return []

            # 2. 生成初始大纲
            initial_outline = self._generate_initial_outline(textbook_title, textbook_content)

            # 3. 生成不同视角的智能体对话
            conversations = []
            for i in range(num_agents):
                conversation = self._generate_agent_conversation(
                    textbook_title,
                    textbook_content,
                    f"视角{i + 1}",
                    initial_outline
                )
                conversations.append(conversation)

            # 4. 生成细化大纲和最终答案
            refined_outline = self._refine_outline(initial_outline, conversations)

            # 5. 填充大纲生成问答对
            qa_pairs = self._fill_outline_with_qa(refined_outline, conversations)

            # 6. 存储回知识库
            self._store_qa_pairs(qa_pairs)

            return qa_pairs

        finally:
            db_session.close()

    def _generate_initial_outline(self, title: str, content: List[TextbookKnowledge]) -> str:
        """生成初始大纲"""
        content_text = "\n".join([item.content[:500] for item in content[:3]])

        prompt = f"""
        基于以下教材内容，生成一个学习大纲：

        教材标题：{title}
        内容摘要：{content_text}

        请生成一个包含主要章节和关键概念的JSON格式大纲。
        """

        messages = [
            {"role": "system", "content": "你是课程设计专家，擅长创建教学大纲。"},
            {"role": "user", "content": prompt}
        ]

        response = self.llm_service.chat_completion(messages)
        return response

    def _generate_agent_conversation(self, title: str, content: List, perspective: str, outline: str) -> List[Dict]:
        """生成智能体对话"""
        content_text = "\n".join([item.content[:300] for item in content[:2]])

        prompt = f"""
        作为{perspective}的提问者，基于以下内容与回答者进行对话：

        教材：{title}
        内容：{content_text}
        大纲：{outline}

        生成3-5轮有深度的问答对话，涵盖不同难度的问题。
        返回JSON格式：[{{"role": "提问者", "content": "问题"}}, {{"role": "回答者", "content": "回答"}}]
        """

        messages = [
            {"role": "system", "content": "你是一个好奇的学习者，擅长提出有深度的问题。"},
            {"role": "user", "content": prompt}
        ]

        response = self.llm_service.chat_completion(messages)
        try:
            return json.loads(response)
        except:
            return []

    def _refine_outline(self, initial_outline: str, conversations: List) -> str:
        """细化大纲"""
        conv_text = ""
        for i, conv in enumerate(conversations):
            conv_text += f"对话{i + 1}:\n"
            for turn in conv[:3]:
                conv_text += f"{turn['role']}: {turn['content']}\n"

        prompt = f"""
        基于以下初始大纲和对话历史，生成一个更详细、更有深度的细化大纲：

        初始大纲：{initial_outline}
        对话历史：{conv_text}

        返回JSON格式的细化大纲。
        """

        messages = [
            {"role": "system", "content": "你是教学大纲优化专家。"},
            {"role": "user", "content": prompt}
        ]

        response = self.llm_service.chat_completion(messages)
        return response

    def _fill_outline_with_qa(self, outline: str, conversations: List) -> List[Dict[str, str]]:
        """基于大纲和对话生成问答对"""
        conv_text = ""
        for conv in conversations:
            for turn in conv:
                conv_text += f"{turn['role']}: {turn['content']}\n"

        prompt = f"""
        基于以下细化大纲和对话历史，生成10个高质量的问答对：

        细化大纲：{outline}
        对话历史：{conv_text}

        返回JSON格式：[{{"question": "问题", "answer": "答案", "difficulty": "难度", "tags": ["标签1", "标签2"]}}]
        """

        messages = [
            {"role": "system", "content": "你是教育内容创作者，擅长创建教学问答对。"},
            {"role": "user", "content": prompt}
        ]

        response = self.llm_service.chat_completion(messages)
        try:
            return json.loads(response)
        except:
            return []

    def _store_qa_pairs(self, qa_pairs: List[Dict]):
        """存储问答对到数据库"""
        db_session = SessionLocal()
        try:
            for qa in qa_pairs:
                qa_record = QAPair(
                    question=qa.get("question", ""),
                    answer=qa.get("answer", ""),
                    source="synthetic",
                    difficulty=qa.get("difficulty", "medium"),
                    tags=qa.get("tags", []),
                    subject="算法"  # 可以根据内容分类
                )
                db_session.add(qa_record)

            db_session.commit()
        except Exception as e:
            db_session.rollback()
            print(f"存储QA对失败: {e}")
        finally:
            db_session.close()