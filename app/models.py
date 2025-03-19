from sqlalchemy import Column, Integer, String, DateTime, Text, Index, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import pytz

Base = declarative_base()

def get_shanghai_time():
    return datetime.now(pytz.timezone('Asia/Shanghai'))

class ErrorLog(Base):
    __tablename__ = 'error_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    log_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    error_message = Column(Text, nullable=False)
    analysis_result = Column(Text, nullable=True)
    application_id = Column(String(100), index=True)
    request_path = Column(String(500), nullable=True)  # 新增字段
    created_at = Column(DateTime, nullable=False, default=get_shanghai_time)

