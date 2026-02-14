# backend/src/api/database_api.py
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, Optional
import os
from datetime import datetime

from database.db_manager import db_manager
from database.data_access import data_access
from models.data_models import (
    KnowledgeBase, QAPairModel, ConversationRecord,
    SearchRequest, SearchResponse
)

router = APIRouter(prefix="/api/database", tags=["database"])


@router.get("/stats")
async def get_database_stats():
    """获取数据库统计信息"""
    try:
        stats = data_access.get_database_stats()
        return {
            "status": "success",
            "data": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.post("/knowledge")
async def create_knowledge(knowledge: KnowledgeBase):
    """创建知识记录"""
    try:
        knowledge_id = data_access.create_knowledge(knowledge)
        return {
            "status": "success",
            "message": "知识记录创建成功",
            "knowledge_id": knowledge_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建知识记录失败: {str(e)}")


@router.get("/knowledge/{knowledge_id}")
async def get_knowledge(knowledge_id: int):
    """获取知识记录"""
    knowledge = data_access.get_knowledge_by_id(knowledge_id)
    if not knowledge:
        raise HTTPException(status_code=404, detail="知识记录不存在")
    return {"status": "success", "data": knowledge.dict()}


@router.get("/knowledge")
async def search_knowledge(
        query: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
):
    """搜索知识记录"""
    try:
        results = data_access.search_knowledge(query, limit, offset)
        return {
            "status": "success",
            "data": [item.dict() for item in results],
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.post("/qa")
async def create_qa_pair(qa_pair: QAPairModel):
    """创建问答对"""
    try:
        qa_id = data_access.create_qa_pair(qa_pair)
        return {
            "status": "success",
            "message": "问答对创建成功",
            "qa_id": qa_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建问答对失败: {str(e)}")


@router.post("/conversation")
async def create_conversation(conversation: ConversationRecord):
    """创建对话记录"""
    try:
        conv_id = data_access.create_conversation(conversation)
        return {
            "status": "success",
            "message": "对话记录创建成功",
            "conversation_id": conv_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建对话记录失败: {str(e)}")


@router.get("/conversation/user/{user_id}")
async def get_user_conversations(
        user_id: str,
        limit: int = 50,
        offset: int = 0
):
    """获取用户对话历史"""
    try:
        conversations = data_access.get_user_conversations(user_id, limit, offset)
        return {
            "status": "success",
            "data": [conv.dict() for conv in conversations],
            "total": len(conversations)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取对话历史失败: {str(e)}")


@router.post("/memory/node")
async def create_memory_node(
        entity: str,
        node_type: str,
        properties: Optional[Dict[str, Any]] = None
):
    """创建记忆节点"""
    try:
        success = data_access.create_memory_node(entity, node_type, properties or {})
        if success:
            return {"status": "success", "message": "记忆节点创建成功"}
        else:
            raise HTTPException(status_code=500, detail="记忆节点创建失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建记忆节点失败: {str(e)}")


@router.get("/memory/search")
async def search_memories(
        query: str,
        limit: int = 10
):
    """搜索记忆"""
    try:
        results = data_access.search_memories(query, limit)
        return {
            "status": "success",
            "data": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索记忆失败: {str(e)}")


@router.get("/memory/graph/{entity}")
async def get_memory_graph(
        entity: str,
        depth: int = 2
):
    """获取记忆图"""
    try:
        graph = data_access.get_memory_subgraph(entity, depth)
        return {
            "status": "success",
            "data": graph
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取记忆图失败: {str(e)}")


@router.post("/backup/mysql")
async def backup_mysql(background_tasks: BackgroundTasks):
    """备份MySQL数据库"""
    try:
        def do_backup():
            backup_file = db_manager.backup_mysql()
            if backup_file:
                logger.info(f"MySQL备份任务完成: {backup_file}")

        background_tasks.add_task(do_backup)
        return {
            "status": "success",
            "message": "MySQL备份任务已启动",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动备份失败: {str(e)}")


@router.post("/backup/neo4j")
async def backup_neo4j(background_tasks: BackgroundTasks):
    """备份Neo4j数据库"""
    try:
        def do_backup():
            backup_file = db_manager.backup_neo4j()
            if backup_file:
                logger.info(f"Neo4j备份任务完成: {backup_file}")

        background_tasks.add_task(do_backup)
        return {
            "status": "success",
            "message": "Neo4j备份任务已启动",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动备份失败: {str(e)}")


@router.post("/cleanup")
async def cleanup_old_data(days: int = 30):
    """清理旧数据"""
    try:
        stats = data_access.cleanup_old_data(days)
        return {
            "status": "success",
            "message": f"清理了 {days} 天前的数据",
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理数据失败: {str(e)}")


@router.get("/health")
async def database_health():
    """数据库健康检查"""
    try:
        # 检查MySQL连接
        with db_manager.mysql_session() as session:
            session.execute("SELECT 1")

        # 检查Neo4j连接
        with db_manager.neo4j_session() as session:
            session.run("RETURN 1")

        return {
            "status": "healthy",
            "mysql": "connected",
            "neo4j": "connected",
            "redis": "connected" if db_manager._redis_client else "not_configured",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }