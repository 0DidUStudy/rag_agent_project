# backend/src/database/data_access.py
from typing import List, Optional, Dict, Any
from sqlalchemy import desc, or_, and_
from datetime import datetime, timedelta
import json

from database.db_manager import db_manager
from database.mysql_models import TextbookKnowledge, QAPair, ConversationHistory
from models.data_models import KnowledgeBase, QAPairModel, ConversationRecord


class DataAccessLayer:
    """数据访问层，处理所有数据库操作"""

    def __init__(self):
        self.db_manager = db_manager

    # ========== Textbook Knowledge 操作 ==========

    def create_knowledge(self, knowledge: KnowledgeBase) -> int:
        """创建知识记录"""
        with self.db_manager.mysql_session() as session:
            db_knowledge = TextbookKnowledge(
                title=knowledge.title,
                content=knowledge.content,
                chapter=knowledge.chapter,
                section=knowledge.section,
                tags=json.dumps(knowledge.tags, ensure_ascii=False),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(db_knowledge)
            session.flush()
            knowledge_id = db_knowledge.id

            # 更新FAISS索引
            self._update_faiss_index(knowledge.content)

            return knowledge_id

    def get_knowledge_by_id(self, knowledge_id: int) -> Optional[KnowledgeBase]:
        """根据ID获取知识"""
        with self.db_manager.mysql_session() as session:
            db_knowledge = session.query(TextbookKnowledge).get(knowledge_id)
            if db_knowledge:
                return self._convert_to_knowledge_model(db_knowledge)
        return None

    def search_knowledge(self,
                         query: str,
                         limit: int = 10,
                         offset: int = 0) -> List[KnowledgeBase]:
        """搜索知识"""
        with self.db_manager.mysql_session() as session:
            # 全文搜索
            if query:
                db_results = session.query(TextbookKnowledge).filter(
                    or_(
                        TextbookKnowledge.title.contains(query),
                        TextbookKnowledge.content.contains(query)
                    )
                ).order_by(desc(TextbookKnowledge.updated_at))
            else:
                db_results = session.query(TextbookKnowledge).order_by(
                    desc(TextbookKnowledge.updated_at)
                )

            db_results = db_results.limit(limit).offset(offset).all()
            return [self._convert_to_knowledge_model(item) for item in db_results]

    def update_knowledge(self, knowledge_id: int, updates: Dict[str, Any]) -> bool:
        """更新知识"""
        with self.db_manager.mysql_session() as session:
            db_knowledge = session.query(TextbookKnowledge).get(knowledge_id)
            if not db_knowledge:
                return False

            for key, value in updates.items():
                if hasattr(db_knowledge, key):
                    if key == 'tags' and isinstance(value, list):
                        setattr(db_knowledge, key, json.dumps(value, ensure_ascii=False))
                    else:
                        setattr(db_knowledge, key, value)

            db_knowledge.updated_at = datetime.utcnow()
            return True

    def delete_knowledge(self, knowledge_id: int) -> bool:
        """删除知识"""
        with self.db_manager.mysql_session() as session:
            db_knowledge = session.query(TextbookKnowledge).get(knowledge_id)
            if not db_knowledge:
                return False

            session.delete(db_knowledge)
            return True

    # ========== QA Pair 操作 ==========

    def create_qa_pair(self, qa_pair: QAPairModel) -> int:
        """创建问答对"""
        with self.db_manager.mysql_session() as session:
            db_qa = QAPair(
                question=qa_pair.question,
                answer=qa_pair.answer,
                source=qa_pair.source,
                difficulty=qa_pair.difficulty,
                subject=qa_pair.subject,
                tags=json.dumps(qa_pair.tags, ensure_ascii=False),
                created_at=datetime.utcnow()
            )
            session.add(db_qa)
            session.flush()
            return db_qa.id

    def get_qa_pair_by_id(self, qa_id: int) -> Optional[QAPairModel]:
        """根据ID获取问答对"""
        with self.db_manager.mysql_session() as session:
            db_qa = session.query(QAPair).get(qa_id)
            if db_qa:
                return self._convert_to_qa_model(db_qa)
        return None

    def search_qa_pairs(self,
                        query: str = None,
                        difficulty: str = None,
                        subject: str = None,
                        limit: int = 10,
                        offset: int = 0) -> List[QAPairModel]:
        """搜索问答对"""
        with self.db_manager.mysql_session() as session:
            query_filters = []

            if query:
                query_filters.append(
                    or_(
                        QAPair.question.contains(query),
                        QAPair.answer.contains(query)
                    )
                )

            if difficulty:
                query_filters.append(QAPair.difficulty == difficulty)

            if subject:
                query_filters.append(QAPair.subject == subject)

            db_results = session.query(QAPair)
            if query_filters:
                db_results = db_results.filter(and_(*query_filters))

            db_results = db_results.order_by(desc(QAPair.created_at))
            db_results = db_results.limit(limit).offset(offset).all()

            return [self._convert_to_qa_model(item) for item in db_results]

    # ========== Conversation History 操作 ==========

    def create_conversation(self, record: ConversationRecord) -> int:
        """创建对话记录"""
        with self.db_manager.mysql_session() as session:
            db_conv = ConversationHistory(
                user_id=record.user_id,
                session_id=record.session_id,
                query=record.query,
                response=record.response,
                context=json.dumps(record.context, ensure_ascii=False) if record.context else None,
                memory_used=json.dumps(
                    [mem.dict() for mem in record.memory_used] if record.memory_used else [],
                    ensure_ascii=False
                ),
                created_at=datetime.utcnow()
            )
            session.add(db_conv)
            session.flush()
            return db_conv.id

    def get_user_conversations(self,
                               user_id: str,
                               limit: int = 50,
                               offset: int = 0) -> List[ConversationRecord]:
        """获取用户对话历史"""
        with self.db_manager.mysql_session() as session:
            db_convs = session.query(ConversationHistory).filter(
                ConversationHistory.user_id == user_id
            ).order_by(desc(ConversationHistory.created_at))

            db_convs = db_convs.limit(limit).offset(offset).all()

            return [self._convert_to_conversation_model(conv) for conv in db_convs]

    def get_recent_conversations(self, hours: int = 24) -> List[ConversationRecord]:
        """获取最近对话"""
        time_threshold = datetime.utcnow() - timedelta(hours=hours)

        with self.db_manager.mysql_session() as session:
            db_convs = session.query(ConversationHistory).filter(
                ConversationHistory.created_at >= time_threshold
            ).order_by(desc(ConversationHistory.created_at)).all()

            return [self._convert_to_conversation_model(conv) for conv in db_convs]

    # ========== Memory Graph 操作 ==========

    def create_memory_node(self,
                           entity: str,
                           node_type: str,
                           properties: Dict[str, Any] = None) -> bool:
        """创建记忆节点"""
        try:
            with self.db_manager.neo4j_session() as session:
                query = """
                MERGE (n:Memory {entity: $entity})
                SET n.type = $type,
                    n.properties = $properties,
                    n.created_at = datetime(),
                    n.updated_at = datetime()
                RETURN n
                """

                session.run(query,
                            entity=entity,
                            type=node_type,
                            properties=properties or {})
                return True
        except Exception as e:
            logger.error(f"创建记忆节点失败: {e}")
            return False

    def create_memory_relation(self,
                               subject: str,
                               relation: str,
                               object: str,
                               properties: Dict[str, Any] = None) -> bool:
        """创建记忆关系"""
        try:
            with self.db_manager.neo4j_session() as session:
                query = """
                MATCH (a:Memory {entity: $subject})
                MATCH (b:Memory {entity: $object})
                MERGE (a)-[r:RELATION {type: $relation}]->(b)
                SET r.properties = $properties,
                    r.created_at = datetime()
                RETURN r
                """

                session.run(query,
                            subject=subject,
                            object=object,
                            relation=relation,
                            properties=properties or {})
                return True
        except Exception as e:
            logger.error(f"创建记忆关系失败: {e}")
            return False

    def get_related_memories(self,
                             entity: str,
                             relation_type: str = None,
                             limit: int = 10) -> List[Dict[str, Any]]:
        """获取相关记忆"""
        try:
            with self.db_manager.neo4j_session() as session:
                if relation_type:
                    query = """
                    MATCH (n:Memory {entity: $entity})-[r:RELATION]->(m:Memory)
                    WHERE r.type = $relation_type
                    RETURN m.entity as entity, m.type as type, 
                           m.properties as properties, r.type as relation_type,
                           r.properties as relation_properties,
                           r.created_at as relation_created
                    LIMIT $limit
                    """
                    result = session.run(query,
                                         entity=entity,
                                         relation_type=relation_type,
                                         limit=limit)
                else:
                    query = """
                    MATCH (n:Memory {entity: $entity})-[r:RELATION]->(m:Memory)
                    RETURN m.entity as entity, m.type as type,
                           m.properties as properties, r.type as relation_type,
                           r.properties as relation_properties,
                           r.created_at as relation_created
                    LIMIT $limit
                    """
                    result = session.run(query, entity=entity, limit=limit)

                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"获取相关记忆失败: {e}")
            return []

    def search_memories(self,
                        search_text: str,
                        limit: int = 10) -> List[Dict[str, Any]]:
        """搜索记忆"""
        try:
            with self.db_manager.neo4j_session() as session:
                query = """
                CALL db.index.fulltext.queryNodes('memory_search_index', $search_text) 
                YIELD node, score
                RETURN node.entity as entity, node.type as type,
                       node.properties as properties, score
                ORDER BY score DESC
                LIMIT $limit
                """

                result = session.run(query,
                                     search_text=f"*{search_text}*",
                                     limit=limit)
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"搜索记忆失败: {e}")
            return []

    def get_memory_subgraph(self,
                            entity: str,
                            depth: int = 2) -> Dict[str, Any]:
        """获取记忆子图"""
        try:
            with self.db_manager.neo4j_session() as session:
                query = """
                MATCH path = (n:Memory {entity: $entity})-[*1..$depth]-(m:Memory)
                WITH path, relationships(path) as rels, nodes(path) as nodes
                UNWIND nodes as node
                UNWIND rels as rel
                RETURN collect(DISTINCT {
                    entity: node.entity,
                    type: node.type,
                    properties: node.properties
                }) as nodes,
                collect(DISTINCT {
                    start: startNode(rel).entity,
                    type: rel.type,
                    end: endNode(rel).entity,
                    properties: rel.properties
                }) as relationships
                """

                result = session.run(query, entity=entity, depth=depth)
                record = result.single()

                if record:
                    return {
                        "nodes": record["nodes"],
                        "relationships": record["relationships"]
                    }
                return {"nodes": [], "relationships": []}
        except Exception as e:
            logger.error(f"获取记忆子图失败: {e}")
            return {"nodes": [], "relationships": []}

    # ========== 统计和监控 ==========

    def get_database_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        stats = {}

        # MySQL统计
        with self.db_manager.mysql_session() as session:
            # 知识库统计
            knowledge_count = session.query(TextbookKnowledge).count()
            qa_count = session.query(QAPair).count()
            conv_count = session.query(ConversationHistory).count()

            # 最近活动
            recent_conv = session.query(ConversationHistory).order_by(
                desc(ConversationHistory.created_at)
            ).first()

            stats['mysql'] = {
                'knowledge_count': knowledge_count,
                'qa_count': qa_count,
                'conversation_count': conv_count,
                'last_activity': recent_conv.created_at if recent_conv else None
            }

        # Neo4j统计
        try:
            with self.db_manager.neo4j_session() as session:
                # 节点统计
                node_count = session.run(
                    "MATCH (n) RETURN count(n) as count"
                ).single()["count"]

                # 关系统计
                rel_count = session.run(
                    "MATCH ()-[r]->() RETURN count(r) as count"
                ).single()["count"]

                # 类型统计
                node_types = session.run(
                    "MATCH (n) RETURN n.type as type, count(*) as count ORDER BY count DESC"
                ).data()

                rel_types = session.run(
                    "MATCH ()-[r]->() RETURN r.type as type, count(*) as count ORDER BY count DESC"
                ).data()

                stats['neo4j'] = {
                    'node_count': node_count,
                    'relationship_count': rel_count,
                    'node_types': node_types,
                    'relationship_types': rel_types
                }
        except Exception as e:
            logger.error(f"获取Neo4j统计失败: {e}")
            stats['neo4j'] = {'error': str(e)}

        return stats

    def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """清理旧数据"""
        cleanup_stats = {}
        time_threshold = datetime.utcnow() - timedelta(days=days)

        # 清理对话历史
        with self.db_manager.mysql_session() as session:
            deleted_convs = session.query(ConversationHistory).filter(
                ConversationHistory.created_at < time_threshold
            ).delete(synchronize_session=False)
            cleanup_stats['conversations_deleted'] = deleted_convs

        logger.info(f"清理了 {deleted_convs} 条旧对话记录")
        return cleanup_stats

    # ========== 私有方法 ==========

    def _convert_to_knowledge_model(self, db_knowledge) -> KnowledgeBase:
        """转换数据库对象到知识模型"""
        return KnowledgeBase(
            id=db_knowledge.id,
            title=db_knowledge.title,
            content=db_knowledge.content,
            chapter=db_knowledge.chapter,
            section=db_knowledge.section,
            tags=json.loads(db_knowledge.tags) if db_knowledge.tags else [],
            created_at=db_knowledge.created_at,
            updated_at=db_knowledge.updated_at
        )

    def _convert_to_qa_model(self, db_qa) -> QAPairModel:
        """转换数据库对象到QA模型"""
        return QAPairModel(
            id=db_qa.id,
            question=db_qa.question,
            answer=db_qa.answer,
            source=db_qa.source,
            difficulty=db_qa.difficulty,
            subject=db_qa.subject,
            tags=json.loads(db_qa.tags) if db_qa.tags else [],
            created_at=db_qa.created_at
        )

    def _convert_to_conversation_model(self, db_conv) -> ConversationRecord:
        """转换数据库对象到对话模型"""
        return ConversationRecord(
            id=db_conv.id,
            user_id=db_conv.user_id,
            session_id=db_conv.session_id,
            query=db_conv.query,
            response=db_conv.response,
            context=json.loads(db_conv.context) if db_conv.context else None,
            memory_used=json.loads(db_conv.memory_used) if db_conv.memory_used else None,
            created_at=db_conv.created_at
        )

    def _update_faiss_index(self, text: str):
        """更新FAISS索引（简化的实现）"""
        # 这里可以集成实际的向量索引更新逻辑
        # 比如：text_to_vector -> add_to_faiss_index
        pass


# 全局数据访问实例
data_access = DataAccessLayer()