from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException, Query, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from pydantic import BaseModel
import uvicorn
import os


from .database import get_db, engine
from .models import Base, ErrorLog
from .services import ESService, DeepseekService, WeChatService

# 创建数据库表
Base.metadata.create_all(bind=engine)

class ErrorLogResponse(BaseModel):
    id: int
    log_time: datetime
    error_message: str
    analysis_result: str
    application_id: str | None = None
    created_at: datetime

    class Config:
        orm_mode = True

app = FastAPI(
    title="日志分析助手",
    description="""
    自动分析业务系统错误日志的API服务。
    
    功能特点：
    * 从Elasticsearch获取最近5分钟的错误日志
    * 使用Deepseek AI进行智能分析
    * 发送分析结果到企业微信群
    * 存储日志和分析结果到MySQL数据库
    * 支持自定义定时任务管理
    """,
    version="1.0.0",
    docs_url="/swagger",
    redoc_url=None
)


# 挂载静态文件目录
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def read_root():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/schedule")
async def read_schedule():
    return FileResponse(os.path.join(static_dir, "schedule.html"))

# 初始化服务
es_service = ESService()
deepseek_service = DeepseekService()
wechat_service = WeChatService()

async def process_error_logs(db: Session):
    try:
        # 获取最近的错误日志
        recent_errors = es_service.get_recent_errors()
        
        if not recent_errors:
            print("No recent errors found")
            return
        
        # 分析每个错误并发送通知
        for error in recent_errors:
            # 获取错误分析结果
            analysis = deepseek_service.analyze_error(error["Exception"])
            
            # 保存到数据库
            db_log = ErrorLog(
                log_time=datetime.fromisoformat(error["timestamp"].replace('Z', '+00:00')),
                error_message=error["Exception"],
                analysis_result=analysis,
                application_id=error.get("application_id"),
            )
            db.add(db_log)
            
            # 发送到企业微信
            wechat_service.send_alert(error, analysis)
        db.commit()
        print(f"Successfully processed {len(recent_errors)} error logs")
        
    except Exception as e:
        print(f"Error in process_error_logs: {str(e)}")
        db.rollback()
        raise

@app.post("/analyze", 
    summary="触发日志分析任务",
    description="""
    触发一次日志分析任务，该任务会：
    1. 从ES获取最近5分钟的错误日志
    2. 使用Deepseek分析每条错误日志
    3. 将分析结果发送到企业微信
    4. 保存日志和分析结果到数据库
    """,
    response_description="返回任务启动状态",
    tags=["任务管理"]
)
async def analyze_logs(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        background_tasks.add_task(process_error_logs, db)
        return {"message": "日志分析任务已启动", "status": "success"}
    except Exception as e:
        print(f"Error in analyze_logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 添加分页响应模型
class PaginatedErrorLogResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[ErrorLogResponse]

    class Config:
        orm_mode = True

@app.get("/logs", 
    response_model=PaginatedErrorLogResponse,
    summary="获取历史日志记录",
    description="获取日志分析记录，支持分页查询。page从1开始，page_size默认为20，最大为100。",
    response_description="返回分页的日志记录列表",
    tags=["日志查询"]
)
async def get_logs(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页记录数，最大100")
):
    # 计算总记录数
    total = db.query(ErrorLog).count()
    
    # 计算偏移量
    offset = (page - 1) * page_size
    
    # 获取分页数据
    logs = db.query(ErrorLog)\
        .order_by(ErrorLog.created_at.desc())\
        .offset(offset)\
        .limit(page_size)\
        .all()
    
    # 将 SQLAlchemy 模型对象转换为字典
    log_responses = [
        ErrorLogResponse(
            id=log.id,
            log_time=log.log_time,
            error_message=log.error_message,
            analysis_result=log.analysis_result,
            application_id=log.application_id,
            created_at=log.created_at
        ) for log in logs
    ]
    
    return PaginatedErrorLogResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
        data=log_responses
    )

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
