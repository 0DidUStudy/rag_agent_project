# backend/src/services/retriever_service.py
from typing import List, Dict, Any
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
from database.mysql_models import SessionLocal, TextbookKnowledge, QAPair
from database.neo4j_client import Neo4jClient
from services.llm_service import LLMService


class RetrieverService:
    """检索服务"""

    def __init__(self):
        self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.llm_service = LLMService()
        self.neo4j_client = Neo4jClient()

        # 初始化FAISS索引
        self.text_index = None
        self.text_data = []
        self._init_faiss_index()

    def _init_faiss_index(self):
        """初始化FAISS索引"""
        dimension = 384  # 模型维度
        self.text_index = faiss.IndexFlatL2(dimension)

    def index_texts(self, texts: List[str]):
        """索引文本"""
        embeddings = self.embedding_model.encode(texts)
        if len(self.text_data) == 0:
            self.text_index.add(embeddings)
        else:
            # 增量添加
            self.text_index.add(embeddings)
        self.text_data.extend(texts)

    def retrieve_from_knowledge(self, query: str, top_k: int = 5) -> List[Dict]:
        """从知识库检索"""
        # 1. 从MySQL检索
        db_session = SessionLocal()
        try:
            # 全文搜索
            knowledge_results = db_session.query(TextbookKnowledge).filter(
                TextbookKnowledge.content.contains(query)
            ).limit(top_k).all()

            # QA对搜索
            qa_results = db_session.query(QAPair).filter(
                QAPair.question.contains(query) | QAPair.answer.contains(query)
            ).limit(top_k).all()

            results = []
            for item in knowledge_results + qa_results:
                results.append({
                    "type": "textbook" if isinstance(item, TextbookKnowledge) else "qa_pair",
                    "content": item.content if isinstance(item,
                                                          TextbookKnowledge) else f"Q: {item.question}\nA: {item.answer}",
                    "score": 1.0  # 简单匹配分数
                })

            return results
        finally:
            db_session.close()

    def retrieve_from_memory(self, query: str, top_k: int = 5) -> List[Dict]:
        """从模型记忆检索"""
        # 1. 生成候选问题
        sub_questions = self.llm_service.generate_sub_questions(query)

        all_memories = []
        with self.neo4j_client.driver.session() as session:
            for sub_q in sub_questions:
                # 从Neo4j检索相关记忆
                memories = self.neo4j_client.search_similar_memories(session, sub_q, limit=3)
                for record in memories:
                    all_memories.append({
                        "entity": record["entity"],
                        "type": record["type"],
                        "properties": record["properties"],
                        "score": record["score"],
                        "query": sub_q
                    })

        # 按分数排序并取top_k
        all_memories.sort(key=lambda x: x["score"], reverse=True)
        return all_memories[:top_k]

    def retrieve(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """综合检索"""
        # 生成子问题
        sub_questions = self.llm_service.generate_sub_questions(query)

        # 并行检索
        knowledge_results = []
        memory_results = []

        for sub_q in sub_questions:
            # 检索知识库
            knowledge = self.retrieve_from_knowledge(sub_q, top_k=3)
            knowledge_results.extend(knowledge)

            # 检索记忆
            memories = self.retrieve_from_memory(sub_q, top_k=3)
            memory_results.extend(memories)

        # 去重和排序
        knowledge_results = self._deduplicate_and_sort(knowledge_results)
        memory_results = self._deduplicate_and_sort(memory_results)

        return {
            "knowledge": knowledge_results[:top_k],
            "memory": memory_results[:top_k],
            "sub_questions": sub_questions
        }

    def _deduplicate_and_sort(self, items: List[Dict]) -> List[Dict]:
        """去重和排序"""
        seen = set()
        unique_items = []
        for item in items:
            key = item.get("content") or item.get("entity")
            if key not in seen:
                seen.add(key)
                unique_items.append(item)

        unique_items.sort(key=lambda x: x.get("score", 0), reverse=True)
        return unique_items