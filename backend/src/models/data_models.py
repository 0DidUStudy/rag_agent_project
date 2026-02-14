# backend/src/models/data_models.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime


class KnowledgeBase(BaseModel):
    """知识库数据模型"""
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=10)
    chapter: Optional[str] = None
    section: Optional[str] = None
    tags: List[str] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class QAPairModel(BaseModel):
    """问答对数据模型"""
    id: Optional[int] = None
    question: str = Field(..., min_length=5)
    answer: str = Field(..., min_length=10)
    source: str = Field(default="synthetic")
    difficulty: str = Field(default="medium")
    subject: Optional[str] = None
    tags: List[str] = []
    created_at: Optional[datetime] = None

    @validator('difficulty')
    def validate_difficulty(cls, v):
        allowed = ['easy', 'medium', 'hard', 'expert']
        if v not in allowed:
            raise ValueError(f'难度必须是以下之一: {allowed}')
        return v


class MemoryNode(BaseModel):
    """记忆节点模型"""
    entity: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MemoryRelation(BaseModel):
    """记忆关系模型"""
    subject: str
    relation: str
    object: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class ConversationRecord(BaseModel):
    """对话记录模型"""
    id: Optional[int] = None
    user_id: str
    session_id: Optional[str] = None
    query: str
    response: str
    context: Optional[Dict[str, Any]] = None
    memory_used: Optional[List[MemoryNode]] = None
    knowledge_used: Optional[List[KnowledgeBase]] = None
    created_at: Optional[datetime] = None

    @validator('session_id', pre=True, always=True)
    def set_session_id(cls, v):
        if v is None:
            import uuid
            return str(uuid.uuid4())
        return v


class SearchRequest(BaseModel):
    """搜索请求模型"""
    query: str
    top_k: int = Field(default=5, ge=1, le=50)
    search_type: str = Field(default="hybrid")

    @validator('search_type')
    def validate_search_type(cls, v):
        allowed = ['knowledge', 'memory', 'hybrid']
        if v not in allowed:
            raise ValueError(f'搜索类型必须是以下之一: {allowed}')
        return v


class SearchResponse(BaseModel):
    """搜索响应模型"""
    results: List[Dict[str, Any]]
    total: int
    search_type: str
    query_time: float