# backend/src/database/db_manager.py
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from neo4j import GraphDatabase, exceptions
import redis
import json
from datetime import datetime
import pickle
from typing import Optional, Generator, Any
import hashlib

from config.settings import settings

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器，负责连接管理和持久化"""

    def __init__(self):
        self._mysql_engine = None
        self._mysql_session_factory = None
        self._neo4j_driver = None
        self._redis_client = None
        self._backup_path = "./data/backups"

    def init_mysql(self):
        """初始化MySQL连接"""
        try:
            self._mysql_engine = create_engine(
                f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
                f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}",
                pool_size=20,
                max_overflow=30,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=settings.DEBUG
            )

            self._mysql_session_factory = scoped_session(
                sessionmaker(autocommit=False, autoflush=False, bind=self._mysql_engine)
            )

            logger.info("MySQL连接池初始化成功")

            # 创建必要的表
            self._create_mysql_tables()

        except Exception as e:
            logger.error(f"MySQL连接失败: {e}")
            raise

    def init_neo4j(self):
        """初始化Neo4j连接"""
        try:
            self._neo4j_driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60
            )

            # 测试连接
            with self._neo4j_driver.session() as session:
                session.run("RETURN 1")

            logger.info("Neo4j连接成功")

            # 创建索引和约束
            self._create_neo4j_indexes()

        except exceptions.ServiceUnavailable as e:
            logger.error(f"Neo4j服务不可用: {e}")
            raise
        except exceptions.AuthError as e:
            logger.error(f"Neo4j认证失败: {e}")
            raise

    def init_redis(self):
        """初始化Redis连接（用于缓存和会话管理）"""
        try:
            self._redis_client = redis.Redis(
                host='localhost',
                port=6379,
                db=0,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )

            # 测试连接
            self._redis_client.ping()
            logger.info("Redis连接成功")

        except redis.ConnectionError as e:
            logger.warning(f"Redis连接失败，将使用内存缓存: {e}")
            self._redis_client = None

    def _create_mysql_tables(self):
        """创建MySQL表结构"""
        from sqlalchemy import MetaData

        metadata = MetaData()

        # 反射现有表结构
        metadata.reflect(bind=self._mysql_engine)

        # 如果表不存在，则创建
        if 'textbook_knowledge' not in metadata.tables:
            from database.mysql_models import Base
            Base.metadata.create_all(bind=self._mysql_engine)
            logger.info("MySQL表创建完成")

    def _create_neo4j_indexes(self):
        """创建Neo4j索引和约束"""
        with self._neo4j_driver.session() as session:
            # 创建约束确保实体唯一性
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Memory) REQUIRE n.entity IS UNIQUE")

            # 创建全文索引
            session.run("""
            CREATE FULLTEXT INDEX memory_search_index IF NOT EXISTS 
            FOR (n:Memory) ON EACH [n.entity, n.properties]
            """)

            # 创建关系类型索引
            session.run("""
            CREATE INDEX rel_type_index IF NOT EXISTS 
            FOR ()-[r:RELATION]-() ON (r.type)
            """)

            logger.info("Neo4j索引创建完成")

    @contextmanager
    def mysql_session(self):
        """获取MySQL会话上下文管理器"""
        session = self._mysql_session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"MySQL会话错误: {e}")
            raise
        finally:
            session.close()

    @contextmanager
    def neo4j_session(self):
        """获取Neo4j会话上下文管理器"""
        if not self._neo4j_driver:
            raise Exception("Neo4j未初始化")

        session = self._neo4j_driver.session()
        try:
            yield session
        except Exception as e:
            logger.error(f"Neo4j会话错误: {e}")
            raise
        finally:
            session.close()

    def backup_mysql(self, backup_file: str = None):
        """备份MySQL数据"""
        import os
        import subprocess

        if not backup_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{self._backup_path}/mysql_backup_{timestamp}.sql"

        os.makedirs(os.path.dirname(backup_file), exist_ok=True)

        try:
            command = [
                'mysqldump',
                f'-u{settings.MYSQL_USER}',
                f'-p{settings.MYSQL_PASSWORD}',
                f'-h{settings.MYSQL_HOST}',
                f'-P{settings.MYSQL_PORT}',
                settings.MYSQL_DATABASE,
                '--skip-comments',
                '--compact'
            ]

            with open(backup_file, 'w') as f:
                subprocess.run(command, stdout=f, check=True)

            logger.info(f"MySQL备份完成: {backup_file}")
            return backup_file

        except subprocess.CalledProcessError as e:
            logger.error(f"MySQL备份失败: {e}")
            return None

    def backup_neo4j(self, backup_file: str = None):
        """备份Neo4j数据"""
        import os
        import subprocess

        if not backup_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{self._backup_path}/neo4j_backup_{timestamp}.cql"

        os.makedirs(os.path.dirname(backup_file), exist_ok=True)

        try:
            with self.neo4j_session() as session:
                # 导出节点
                nodes_query = """
                MATCH (n)
                RETURN labels(n) as labels, properties(n) as properties
                ORDER BY id(n)
                """

                # 导出关系
                relations_query = """
                MATCH (a)-[r]->(b)
                RETURN labels(a) as start_labels, 
                       properties(a) as start_props,
                       type(r) as rel_type,
                       properties(r) as rel_props,
                       labels(b) as end_labels,
                       properties(b) as end_props
                ORDER BY id(r)
                """

                nodes = list(session.run(nodes_query))
                relations = list(session.run(relations_query))

                with open(backup_file, 'w') as f:
                    # 写入节点
                    for node in nodes:
                        labels = ':'.join(node['labels'])
                        props = json.dumps(dict(node['properties']), ensure_ascii=False)
                        f.write(f"CREATE (n:{labels} {props});\n")

                    # 写入关系
                    for rel in relations:
                        start_labels = ':'.join(rel['start_labels'])
                        start_props = json.dumps(dict(rel['start_props']), ensure_ascii=False)
                        end_labels = ':'.join(rel['end_labels'])
                        end_props = json.dumps(dict(rel['end_props']), ensure_ascii=False)
                        rel_type = rel['rel_type']
                        rel_props = json.dumps(dict(rel['rel_props']), ensure_ascii=False)

                        f.write(
                            f"MATCH (a:{start_labels} {start_props}), "
                            f"(b:{end_labels} {end_props}) "
                            f"CREATE (a)-[:{rel_type} {rel_props}]->(b);\n"
                        )

                logger.info(f"Neo4j备份完成: {backup_file}")
                return backup_file

        except Exception as e:
            logger.error(f"Neo4j备份失败: {e}")
            return None

    def restore_mysql(self, backup_file: str):
        """恢复MySQL数据"""
        import subprocess

        try:
            command = [
                'mysql',
                f'-u{settings.MYSQL_USER}',
                f'-p{settings.MYSQL_PASSWORD}',
                f'-h{settings.MYSQL_HOST}',
                f'-P{settings.MYSQL_PORT}',
                settings.MYSQL_DATABASE
            ]

            with open(backup_file, 'r') as f:
                subprocess.run(command, stdin=f, check=True)

            logger.info(f"MySQL恢复完成: {backup_file}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"MySQL恢复失败: {e}")
            return False

    def restore_neo4j(self, backup_file: str):
        """恢复Neo4j数据"""
        try:
            # 先清空现有数据
            with self.neo4j_session() as session:
                session.run("MATCH (n) DETACH DELETE n")

            # 执行备份文件
            with self.neo4j_session() as session:
                with open(backup_file, 'r') as f:
                    cql_statements = f.read().split(';')

                    for statement in cql_statements:
                        statement = statement.strip()
                        if statement:
                            try:
                                session.run(statement)
                            except Exception as e:
                                logger.warning(f"执行CQL语句失败: {statement[:50]}... - {e}")

            logger.info(f"Neo4j恢复完成: {backup_file}")
            return True

        except Exception as e:
            logger.error(f"Neo4j恢复失败: {e}")
            return False

    def cache_query_result(self, query: str, result: Any, ttl: int = 3600):
        """缓存查询结果"""
        if not self._redis_client:
            return

        cache_key = f"query_cache:{hashlib.md5(query.encode()).hexdigest()}"
        try:
            self._redis_client.setex(
                cache_key,
                ttl,
                pickle.dumps(result)
            )
        except Exception as e:
            logger.warning(f"缓存查询结果失败: {e}")

    def get_cached_result(self, query: str) -> Optional[Any]:
        """获取缓存的查询结果"""
        if not self._redis_client:
            return None

        cache_key = f"query_cache:{hashlib.md5(query.encode()).hexdigest()}"
        try:
            cached = self._redis_client.get(cache_key)
            if cached:
                return pickle.loads(cached)
        except Exception as e:
            logger.warning(f"获取缓存失败: {e}")

        return None

    def close(self):
        """关闭所有数据库连接"""
        try:
            if self._mysql_engine:
                self._mysql_engine.dispose()
                logger.info("MySQL连接已关闭")

            if self._neo4j_driver:
                self._neo4j_driver.close()
                logger.info("Neo4j连接已关闭")

            if self._redis_client:
                self._redis_client.close()
                logger.info("Redis连接已关闭")

        except Exception as e:
            logger.error(f"关闭数据库连接时出错: {e}")


# 全局数据库管理器实例
db_manager = DatabaseManager()