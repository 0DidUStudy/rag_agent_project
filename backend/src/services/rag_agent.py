# backend/src/services/rag_agent.py
from typing import Dict, Any, List
import yaml
from services.llm_service import LLMService
from services.retriever_service import RetrieverService
from database.neo4j_client import Neo4jClient


class RAGAgent:
    """RAG智能体"""

    def __init__(self):
        self.llm_service = LLMService()
        self.retriever = RetrieverService()
        self.neo4j_client = Neo4jClient()

    def process_query(self, query: str, user_id: str = None) -> Dict[str, Any]:
        """处理用户查询"""
        # 1. 检索阶段
        retrieval_results = self.retriever.retrieve(query)

        # 2. 格式化记忆为YAML
        memory_yaml = self._format_memory_to_yaml(retrieval_results["memory"])

        # 3. 组合知识
        combined_knowledge = self._combine_knowledge(
            memory_yaml,
            retrieval_results["knowledge"],
            {"current_query": query, "user_id": user_id}
        )

        # 4. 推理阶段
        response = self._generate_response(query, combined_knowledge)

        # 5. 更新阶段
        if user_id:
            self._update_memory(query, response, retrieval_results, user_id)

        return {
            "response": response,
            "retrieval_context": {
                "knowledge_used": retrieval_results["knowledge"],
                "memory_used": retrieval_results["memory"],
                "sub_questions": retrieval_results["sub_questions"]
            }
        }

    def _format_memory_to_yaml(self, memories: List[Dict]) -> str:
        """将记忆格式化为YAML"""
        memory_data = []
        for mem in memories:
            memory_data.append({
                "entity": mem.get("entity"),
                "type": mem.get("type"),
                "properties": mem.get("properties", {}),
                "score": mem.get("score", 0)
            })

        return yaml.dump({"memories": memory_data}, allow_unicode=True)

    def _combine_knowledge(self, memory_yaml: str, knowledge: List[Dict], state: Dict) -> str:
        """组合知识"""
        # 格式化知识
        knowledge_text = "\n".join([
            f"[{item.get('type', 'unknown')}]\n{item.get('content', '')}\n"
            for item in knowledge
        ])

        combined = f"""
        # 模型记忆
        {memory_yaml}

        # 检索到的知识
        {knowledge_text}

        # 当前状态
        用户ID: {state.get('user_id', 'anonymous')}
        当前查询: {state.get('current_query', '')}
        """

        return combined

    def _generate_response(self, query: str, context: str) -> str:
        """生成回答"""
        prompt = f"""
        基于以下上下文信息，回答用户的问题：

        上下文：
        {context}

        用户问题：{query}

        要求：
        1. 基于上下文提供准确、详细的回答
        2. 如果上下文信息不足，请说明哪些方面需要更多信息
        3. 回答要结构清晰，易于理解
        4. 如果涉及算法，可以提供伪代码或关键步骤
        """

        messages = [
            {"role": "system", "content": "你是一个专业的技术教学助手，擅长解释算法和技术概念。"},
            {"role": "user", "content": prompt}
        ]

        return self.llm_service.chat_completion(messages)

    def _update_memory(self, query: str, response: str, retrieval_results: Dict, user_id: str):
        """更新模型记忆"""
        # 提取实体和关系
        extraction_result = self.llm_service.extract_entities_relations(f"{query}\n{response}")

        # 更新到Neo4j
        with self.neo4j_client.driver.session() as session:
            # 添加实体
            for entity in extraction_result.get("entities", []):
                self.neo4j_client.create_memory_node(
                    session,
                    entity["entity"],
                    entity["type"],
                    {"user_id": user_id, "source_query": query}
                )

            # 添加关系
            for relation in extraction_result.get("relations", []):
                self.neo4j_client.create_relationship(
                    session,
                    relation["subject"],
                    relation["object"],
                    relation["relation"],
                    {"user_id": user_id, "timestamp": "2026-02-14"}
                )