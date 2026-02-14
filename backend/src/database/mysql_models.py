# backend/src/database/mysql_models.py
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config.settings import settings

Base = declarative_base()


class TextbookKnowledge(Base):
    """教材知识库"""
    __tablename__ = "textbook_knowledge"

    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    chapter = Column(String(200))
    section = Column(String(200))
    tags = Column(JSON)  # 存储标签列表
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class QAPair(Base):
    """问答对"""
    __tablename__ = "qa_pairs"

    id = Column(Integer, primary_key=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    source = Column(String(200))  # 来源：synthetic, manual, etc.
    difficulty = Column(String(50))  # 难度等级
    subject = Column(String(100))  # 学科
    tags = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class ConversationHistory(Base):
    """对话历史"""
    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(100))
    session_id = Column(String(100))
    query = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    context = Column(JSON)  # 检索的上下文
    memory_used = Column(JSON)  # 使用的记忆
    created_at = Column(DateTime, default=datetime.utcnow)


# 创建数据库连接
engine = create_engine(
    f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
    f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)