# backend/src/database/neo4j_client.py
from neo4j import GraphDatabase
from config.settings import settings


class Neo4jClient:
    """Neo4j图数据库客户端"""

    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

    def close(self):
        self.driver.close()

    def create_memory_node(self, session, entity, entity_type, properties=None):
        """创建记忆节点"""
        query = """
        MERGE (n:Memory {entity: $entity, type: $entity_type})
        SET n += $properties
        RETURN n
        """
        return session.run(query,
                           entity=entity,
                           entity_type=entity_type,
                           properties=properties or {})

    def create_relationship(self, session, entity1, entity2, relation_type, properties=None):
        """创建关系"""
        query = """
        MATCH (a:Memory {entity: $entity1})
        MATCH (b:Memory {entity: $entity2})
        MERGE (a)-[r:RELATION {type: $relation_type}]->(b)
        SET r += $properties
        RETURN r
        """
        return session.run(query,
                           entity1=entity1,
                           entity2=entity2,
                           relation_type=relation_type,
                           properties=properties or {})

    def get_related_memories(self, session, entity, relation_type=None, limit=10):
        """获取相关记忆"""
        query = """
        MATCH (n:Memory {entity: $entity})-[r]->(m:Memory)
        WHERE $relation_type IS NULL OR r.type = $relation_type
        RETURN m.entity as entity, m.type as type, m.properties as properties,
               r.type as relation_type, r.properties as relation_properties
        LIMIT $limit
        """
        return session.run(query,
                           entity=entity,
                           relation_type=relation_type,
                           limit=limit)

    def search_similar_memories(self, session, search_text, limit=5):
        """搜索相似记忆"""
        query = """
        CALL db.index.fulltext.queryNodes('memoryIndex', $search_text) 
        YIELD node, score
        RETURN node.entity as entity, node.type as type, 
               node.properties as properties, score
        ORDER BY score DESC
        LIMIT $limit
        """
        return session.run(query, search_text=search_text, limit=limit)