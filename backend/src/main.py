# backend/src/main.py
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import logging
from datetime import datetime
import traceback

from config.settings import settings
from database.db_manager import db_manager, DatabaseManager
from database.data_access import data_access, DataAccessLayer
from services.rag_agent import RAGAgent
from services.data_synthesizer import DataSynthesizer
from services.llm_service import LLMService
from services.retriever_service import RetrieverService

# 配置日志
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 全局组件实例
rag_agent = None
data_synthesizer = None
llm_service = None
retriever_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global rag_agent, data_synthesizer, llm_service, retriever_service

    # 启动时初始化
    logger.info("正在启动RAG智能体系统...")

    try:
        # 初始化数据库连接
        logger.info("正在初始化数据库连接...")
        db_manager.init_mysql()
        db_manager.init_neo4j()
        db_manager.init_redis()

        # 创建备份目录
        import os
        os.makedirs("./data/backups", exist_ok=True)
        logger.info("数据库连接初始化完成")

        # 初始化服务组件
        logger.info("正在初始化服务组件...")
        llm_service = LLMService()
        retriever_service = RetrieverService()
        rag_agent = RAGAgent()
        data_synthesizer = DataSynthesizer()

        # 测试LLM连接
        logger.info("正在测试LLM服务连接...")
        test_response = llm_service.chat_completion([
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"}
        ])
        if test_response:
            logger.info("LLM服务连接成功")
        else:
            logger.warning("LLM服务连接失败，某些功能可能不可用")

        logger.info("RAG智能体系统启动完成")
        yield

    except Exception as e:
        logger.error(f"启动失败: {e}")
        logger.error(traceback.format_exc())
        raise

    finally:
        # 关闭时清理
        logger.info("正在关闭RAG智能体系统...")
        db_manager.close()
        logger.info("系统已关闭")


# 创建应用实例
app = FastAPI(
    title="RAG智能体系统",
    version="1.0.0",
    description="基于检索增强生成的智能教学系统",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 数据模型
class QueryRequest(BaseModel):
    question: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    use_cache: Optional[bool] = True


class QueryResponse(BaseModel):
    response: str
    retrieval_context: dict
    sub_questions: List[str]
    conversation_id: Optional[int] = None
    timestamp: str


class SynthesisRequest(BaseModel):
    textbook_title: str
    num_agents: int = 3
    difficulty_levels: Optional[List[str]] = ["easy", "medium", "hard"]
    num_qa_pairs: Optional[int] = 10


class SynthesisResponse(BaseModel):
    status: str
    qa_pairs_generated: int
    qa_pairs: List[Dict[str, Any]]
    synthesis_id: Optional[str] = None


class AlgorithmDemoRequest(BaseModel):
    algorithm_name: str
    input_data: Dict[str, Any]
    step_by_step: bool = False
    visualization_type: Optional[str] = "static"


class AlgorithmDemoResponse(BaseModel):
    status: str
    algorithm: str
    steps: List[Dict[str, Any]]
    result: Optional[Any] = None
    visualization_data: Optional[Dict[str, Any]] = None


class KnowledgeCreateRequest(BaseModel):
    title: str
    content: str
    chapter: Optional[str] = None
    section: Optional[str] = None
    tags: Optional[List[str]] = []


class QACreateRequest(BaseModel):
    question: str
    answer: str
    source: str = "manual"
    difficulty: str = "medium"
    subject: Optional[str] = None
    tags: Optional[List[str]] = []


class MemoryNodeCreateRequest(BaseModel):
    entity: str
    node_type: str
    properties: Optional[Dict[str, Any]] = {}


class MemoryRelationCreateRequest(BaseModel):
    subject: str
    relation: str
    object: str
    properties: Optional[Dict[str, Any]] = {}


class BackupRequest(BaseModel):
    backup_type: str = "all"  # all, mysql, neo4j
    description: Optional[str] = None


class CleanupRequest(BaseModel):
    days: int = 30
    confirm: bool = False


# 异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.error(f"全局异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "服务器内部错误",
            "detail": str(exc) if settings.DEBUG else "Internal server error",
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理器"""
    logger.warning(f"HTTP异常 {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path
        }
    )


# 中间件 - 请求日志
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """请求日志中间件"""
    start_time = datetime.utcnow()

    # 记录请求
    logger.info(f"请求开始: {request.method} {request.url.path}")

    try:
        response = await call_next(request)
        process_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # 记录响应
        logger.info(
            f"请求完成: {request.method} {request.url.path} "
            f"- 状态码: {response.status_code} - 耗时: {process_time:.2f}ms"
        )

        return response

    except Exception as exc:
        process_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.error(
            f"请求异常: {request.method} {request.url.path} "
            f"- 异常: {exc} - 耗时: {process_time:.2f}ms"
        )
        raise


# 基础路由
@app.get("/")
async def root():
    """根路由"""
    return {
        "message": "欢迎使用RAG智能体系统",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "文档": "/docs",
            "健康检查": "/health",
            "系统状态": "/status",
            "RAG问答": "/query",
            "数据合成": "/synthesize",
            "算法演示": "/demo/algorithm",
            "数据库管理": "/api/database"
        }
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    try:
        # 检查MySQL
        with db_manager.mysql_session() as session:
            session.execute("SELECT 1")

        # 检查Neo4j
        with db_manager.neo4j_session() as session:
            session.run("RETURN 1")

        # 检查Redis
        redis_status = "connected" if db_manager._redis_client else "not_configured"

        # 检查LLM服务
        llm_status = "connected" if llm_service and llm_service.chat_completion([
            {"role": "system", "content": "test"},
            {"role": "user", "content": "test"}
        ], max_tokens=10) else "disconnected"

        return {
            "status": "healthy",
            "services": {
                "mysql": "connected",
                "neo4j": "connected",
                "redis": redis_status,
                "llm": llm_status
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@app.get("/status")
async def system_status():
    """系统状态检查"""
    try:
        # 获取数据库统计
        stats = data_access.get_database_stats()

        # 获取服务状态
        services = {
            "mysql": "connected",
            "neo4j": "connected",
            "redis": "connected" if db_manager._redis_client else "not_configured",
            "rag_agent": "initialized" if rag_agent else "not_initialized",
            "llm_service": "initialized" if llm_service else "not_initialized"
        }

        # 检查每个服务的实际状态
        try:
            with db_manager.mysql_session() as session:
                session.execute("SELECT 1")
        except:
            services["mysql"] = "disconnected"

        try:
            with db_manager.neo4j_session() as session:
                session.run("RETURN 1")
        except:
            services["neo4j"] = "disconnected"

        if db_manager._redis_client:
            try:
                db_manager._redis_client.ping()
            except:
                services["redis"] = "disconnected"

        return {
            "status": "running",
            "services": services,
            "statistics": stats,
            "system_info": {
                "debug_mode": settings.DEBUG,
                "api_version": "1.0.0",
                "startup_time": "已启动"
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"状态检查失败: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# RAG智能体路由
@app.post("/query", response_model=QueryResponse)
async def query_rag_agent(request: QueryRequest):
    """RAG智能体问答接口"""
    if not rag_agent:
        raise HTTPException(status_code=503, detail="RAG智能体未初始化")

    try:
        # 检查缓存
        cached_result = None
        if request.use_cache and db_manager._redis_client:
            cached_result = db_manager.get_cached_result(request.question)

        if cached_result:
            logger.info(f"使用缓存结果: {request.question[:50]}...")
            return QueryResponse(**cached_result)

        # 处理查询
        logger.info(f"处理查询: {request.question[:100]}...")
        result = rag_agent.process_query(request.question, request.user_id)

        # 保存对话记录
        conversation_record = {
            "user_id": request.user_id or "anonymous",
            "session_id": request.session_id,
            "query": request.question,
            "response": result["response"],
            "context": result["retrieval_context"],
            "memory_used": result["retrieval_context"].get("memory", [])
        }

        conversation_id = data_access.create_conversation(conversation_record)

        # 缓存结果
        if request.use_cache and db_manager._redis_client:
            db_manager.cache_query_result(request.question, result)

        response_data = {
            "response": result["response"],
            "retrieval_context": result["retrieval_context"],
            "sub_questions": result["retrieval_context"].get("sub_questions", []),
            "conversation_id": conversation_id,
            "timestamp": datetime.utcnow().isoformat()
        }

        logger.info(f"查询处理完成: {request.question[:50]}...")
        return QueryResponse(**response_data)

    except Exception as e:
        logger.error(f"查询处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理查询失败: {str(e)}")


@app.post("/synthesize", response_model=SynthesisResponse)
async def synthesize_data(request: SynthesisRequest, background_tasks: BackgroundTasks):
    """数据合成接口"""
    if not data_synthesizer:
        raise HTTPException(status_code=503, detail="数据合成器未初始化")

    try:
        logger.info(f"开始数据合成: {request.textbook_title}")

        def synthesize_task():
            """后台合成任务"""
            try:
                qa_pairs = data_synthesizer.synthesize_qa_pairs(
                    request.textbook_title,
                    request.num_agents
                )
                logger.info(f"数据合成完成: 生成 {len(qa_pairs)} 个问答对")
            except Exception as e:
                logger.error(f"数据合成任务失败: {e}")

        # 在后台执行合成任务
        background_tasks.add_task(synthesize_task)

        # 立即返回响应，不等待任务完成
        return SynthesisResponse(
            status="started",
            qa_pairs_generated=0,
            qa_pairs=[],
            synthesis_id=f"synth_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        )

    except Exception as e:
        logger.error(f"数据合成启动失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"数据合成失败: {str(e)}")


@app.post("/demo/algorithm", response_model=AlgorithmDemoResponse)
async def algorithm_demo(request: AlgorithmDemoRequest):
    """算法演示接口"""
    try:
        logger.info(f"算法演示请求: {request.algorithm_name}")

        # 这里可以根据不同的算法名称实现不同的演示逻辑
        # 目前实现一个通用的模拟演示

        if request.algorithm_name == "kmp":
            steps = [
                {"step": 1, "description": "构建模式串的部分匹配表",
                 "data": {"pattern": "ABCDABD", "next": [0, 0, 0, 0, 1, 2, 0]}},
                {"step": 2, "description": "初始化主串和模式串指针", "data": {"text_index": 0, "pattern_index": 0}},
                {"step": 3, "description": "开始匹配过程", "data": {"match_count": 0}},
                {"step": 4, "description": "根据部分匹配表调整模式串位置", "data": {"adjustment": 2}},
                {"step": 5, "description": "找到匹配位置", "data": {"position": 15}}
            ]
            result = {"match_position": 15, "comparisons": 28}
        elif request.algorithm_name == "dp":
            steps = [
                {"step": 1, "description": "初始化动态规划表", "data": {"dp_table": [[0] * 5 for _ in range(5)]}},
                {"step": 2, "description": "填充基础情况", "data": {"base_cases": "已填充"}},
                {"step": 3, "description": "递推计算最优解", "data": {"iteration": 1}},
                {"step": 4, "description": "完成表格填充", "data": {"completed": True}},
                {"step": 5, "description": "回溯构建最优解", "data": {"solution_path": [1, 3, 5]}}
            ]
            result = {"optimal_value": 42, "solution": [1, 3, 5]}
        else:
            steps = [
                {"step": 1, "description": "算法初始化", "data": {"status": "initialized"}},
                {"step": 2, "description": "处理输入数据", "data": {"input_size": len(str(request.input_data))}},
                {"step": 3, "description": "执行算法核心逻辑", "data": {"progress": 50}},
                {"step": 4, "description": "生成输出结果", "data": {"output_ready": True}}
            ]
            result = {"message": "算法演示完成", "input": request.input_data}

        visualization_data = {
            "type": request.visualization_type,
            "algorithm": request.algorithm_name,
            "steps": steps,
            "current_step": 0 if request.step_by_step else len(steps)
        }

        return AlgorithmDemoResponse(
            status="success",
            algorithm=request.algorithm_name,
            steps=steps,
            result=result,
            visualization_data=visualization_data
        )

    except Exception as e:
        logger.error(f"算法演示失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"算法演示失败: {str(e)}")


# 数据库管理路由
@app.get("/api/database/stats")
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
        logger.error(f"获取数据库统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@app.post("/api/database/knowledge")
async def create_knowledge_item(request: KnowledgeCreateRequest):
    """创建知识条目"""
    try:
        from models.data_models import KnowledgeBase

        knowledge = KnowledgeBase(
            title=request.title,
            content=request.content,
            chapter=request.chapter,
            section=request.section,
            tags=request.tags
        )

        knowledge_id = data_access.create_knowledge(knowledge)

        return {
            "status": "success",
            "message": "知识条目创建成功",
            "knowledge_id": knowledge_id,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"创建知识条目失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建知识条目失败: {str(e)}")


@app.post("/api/database/qa")
async def create_qa_item(request: QACreateRequest):
    """创建问答对"""
    try:
        from models.data_models import QAPairModel

        qa_pair = QAPairModel(
            question=request.question,
            answer=request.answer,
            source=request.source,
            difficulty=request.difficulty,
            subject=request.subject,
            tags=request.tags
        )

        qa_id = data_access.create_qa_pair(qa_pair)

        return {
            "status": "success",
            "message": "问答对创建成功",
            "qa_id": qa_id,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"创建问答对失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建问答对失败: {str(e)}")


@app.post("/api/database/memory/node")
async def create_memory_node_item(request: MemoryNodeCreateRequest):
    """创建记忆节点"""
    try:
        success = data_access.create_memory_node(
            request.entity,
            request.node_type,
            request.properties
        )

        if success:
            return {
                "status": "success",
                "message": "记忆节点创建成功",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="记忆节点创建失败")

    except Exception as e:
        logger.error(f"创建记忆节点失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建记忆节点失败: {str(e)}")


@app.post("/api/database/memory/relation")
async def create_memory_relation_item(request: MemoryRelationCreateRequest):
    """创建记忆关系"""
    try:
        success = data_access.create_memory_relation(
            request.subject,
            request.relation,
            request.object,
            request.properties
        )

        if success:
            return {
                "status": "success",
                "message": "记忆关系创建成功",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="记忆关系创建失败")

    except Exception as e:
        logger.error(f"创建记忆关系失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建记忆关系失败: {str(e)}")


@app.get("/api/database/memory/search")
async def search_memory_items(
        query: str,
        limit: int = 10,
        offset: int = 0
):
    """搜索记忆"""
    try:
        results = data_access.search_memories(query, limit)

        return {
            "status": "success",
            "data": results,
            "total": len(results),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"搜索记忆失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索记忆失败: {str(e)}")


@app.get("/api/database/memory/graph/{entity}")
async def get_memory_graph(
        entity: str,
        depth: int = 2
):
    """获取记忆图"""
    try:
        graph = data_access.get_memory_subgraph(entity, depth)

        return {
            "status": "success",
            "data": graph,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"获取记忆图失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取记忆图失败: {str(e)}")


@app.post("/api/database/backup")
async def backup_database(
        request: BackupRequest,
        background_tasks: BackgroundTasks
):
    """备份数据库"""
    try:
        def do_backup():
            try:
                if request.backup_type in ["all", "mysql"]:
                    backup_file = db_manager.backup_mysql()
                    if backup_file:
                        logger.info(f"MySQL备份完成: {backup_file}")

                if request.backup_type in ["all", "neo4j"]:
                    backup_file = db_manager.backup_neo4j()
                    if backup_file:
                        logger.info(f"Neo4j备份完成: {backup_file}")

                if request.description:
                    logger.info(f"备份描述: {request.description}")

            except Exception as e:
                logger.error(f"备份任务执行失败: {e}")

        background_tasks.add_task(do_backup)

        return {
            "status": "success",
            "message": f"{request.backup_type}备份任务已启动",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"启动备份失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动备份失败: {str(e)}")


@app.post("/api/database/cleanup")
async def cleanup_old_data(request: CleanupRequest):
    """清理旧数据"""
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="请确认清理操作，设置 confirm=true"
        )

    try:
        stats = data_access.cleanup_old_data(request.days)

        return {
            "status": "success",
            "message": f"清理了 {request.days} 天前的数据",
            "stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"清理数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理数据失败: {str(e)}")


@app.get("/api/database/health")
async def database_health_check():
    """数据库健康检查"""
    try:
        # 检查MySQL连接
        mysql_status = "healthy"
        try:
            with db_manager.mysql_session() as session:
                session.execute("SELECT 1")
        except Exception as e:
            mysql_status = f"error: {str(e)}"

        # 检查Neo4j连接
        neo4j_status = "healthy"
        try:
            with db_manager.neo4j_session() as session:
                session.run("RETURN 1")
        except Exception as e:
            neo4j_status = f"error: {str(e)}"

        # 检查Redis连接
        redis_status = "not_configured"
        if db_manager._redis_client:
            try:
                db_manager._redis_client.ping()
                redis_status = "healthy"
            except Exception as e:
                redis_status = f"error: {str(e)}"

        return {
            "status": "healthy" if mysql_status == "healthy" and neo4j_status == "healthy" else "unhealthy",
            "services": {
                "mysql": mysql_status,
                "neo4j": neo4j_status,
                "redis": redis_status
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# 知识库查询路由
@app.get("/api/knowledge/search")
async def search_knowledge(
        q: Optional[str] = None,
        page: int = 1,
        limit: int = 20
):
    """搜索知识库"""
    try:
        offset = (page - 1) * limit
        results = data_access.search_knowledge(q, limit, offset)

        return {
            "status": "success",
            "data": [item.dict() for item in results],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": len(results),
                "has_more": len(results) == limit
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"搜索知识库失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索知识库失败: {str(e)}")


@app.get("/api/qa/search")
async def search_qa_pairs(
        q: Optional[str] = None,
        difficulty: Optional[str] = None,
        subject: Optional[str] = None,
        page: int = 1,
        limit: int = 20
):
    """搜索问答对"""
    try:
        offset = (page - 1) * limit
        results = data_access.search_qa_pairs(q, difficulty, subject, limit, offset)

        return {
            "status": "success",
            "data": [item.dict() for item in results],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": len(results),
                "has_more": len(results) == limit
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"搜索问答对失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索问答对失败: {str(e)}")


@app.get("/api/conversation/user/{user_id}")
async def get_user_conversations(
        user_id: str,
        page: int = 1,
        limit: int = 50
):
    """获取用户对话历史"""
    try:
        offset = (page - 1) * limit
        conversations = data_access.get_user_conversations(user_id, limit, offset)

        return {
            "status": "success",
            "data": [conv.dict() for conv in conversations],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": len(conversations),
                "has_more": len(conversations) == limit
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"获取用户对话历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取用户对话历史失败: {str(e)}")


# 系统管理路由
@app.get("/api/admin/startup-check")
async def admin_startup_check():
    """管理员启动检查"""
    try:
        # 检查所有服务
        checks = {}

        # MySQL检查
        try:
            with db_manager.mysql_session() as session:
                result = session.execute("SELECT VERSION()").fetchone()
                checks["mysql"] = {
                    "status": "connected",
                    "version": str(result[0]) if result else "unknown"
                }
        except Exception as e:
            checks["mysql"] = {"status": "error", "error": str(e)}

        # Neo4j检查
        try:
            with db_manager.neo4j_session() as session:
                result = session.run("CALL dbms.components() YIELD versions RETURN versions[0] as version").single()
                checks["neo4j"] = {
                    "status": "connected",
                    "version": result["version"] if result else "unknown"
                }
        except Exception as e:
            checks["neo4j"] = {"status": "error", "error": str(e)}

        # Redis检查
        if db_manager._redis_client:
            try:
                info = db_manager._redis_client.info()
                checks["redis"] = {
                    "status": "connected",
                    "version": info.get("redis_version", "unknown")
                }
            except Exception as e:
                checks["redis"] = {"status": "error", "error": str(e)}
        else:
            checks["redis"] = {"status": "not_configured"}

        # LLM服务检查
        if llm_service:
            try:
                response = llm_service.chat_completion([
                    {"role": "system", "content": "ping"},
                    {"role": "user", "content": "pong"}
                ], max_tokens=5)
                checks["llm"] = {
                    "status": "connected",
                    "response": response[:50] if response else "no_response"
                }
            except Exception as e:
                checks["llm"] = {"status": "error", "error": str(e)}
        else:
            checks["llm"] = {"status": "not_initialized"}

        return {
            "status": "completed",
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"启动检查失败: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@app.post("/api/admin/reset-cache")
async def admin_reset_cache():
    """重置缓存"""
    try:
        if db_manager._redis_client:
            db_manager._redis_client.flushall()
            return {
                "status": "success",
                "message": "缓存已清空",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "success",
                "message": "缓存未配置，无需清空",
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception as e:
        logger.error(f"重置缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"重置缓存失败: {str(e)}")


# 监控端点
@app.get("/api/monitor/metrics")
async def get_metrics():
    """获取系统监控指标"""
    try:
        import psutil
        import platform

        # 系统信息
        system_info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available,
            "disk_usage": psutil.disk_usage('/').percent
        }

        # 进程信息
        process = psutil.Process()
        process_info = {
            "pid": process.pid,
            "name": process.name(),
            "cpu_percent": process.cpu_percent(),
            "memory_percent": process.memory_percent(),
            "threads": process.num_threads(),
            "connections": len(process.connections())
        }

        # 数据库连接统计
        db_stats = data_access.get_database_stats()

        return {
            "status": "success",
            "system": system_info,
            "process": process_info,
            "database": db_stats,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"获取监控指标失败: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# 静态文件服务
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    # 启动应用
    uvicorn.run(
        "main:app",
        host=settings.HOST if hasattr(settings, 'HOST') else "0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
        access_log=True,
        workers=1  # 开发环境使用单worker
    )