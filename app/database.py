from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv
import os

load_dotenv()

MYSQL_URL = os.getenv("MYSQL_URL", "mysql+pymysql://user:password@localhost/log_analysis")

# 配置数据库连接池和重连机制
engine = create_engine(
    MYSQL_URL,
    pool_size=5,  # 连接池大小
    max_overflow=10,  # 超过连接池大小外最多创建的连接数
    pool_timeout=30,  # 连接池中没有可用连接的超时时间
    pool_recycle=3600,  # 连接在连接池中的存活时间
    pool_pre_ping=True,  # 每次连接前ping一下数据库，确保连接有效
    poolclass=QueuePool  # 使用队列池
)

# 配置连接事件监听器
@event.listens_for(engine, 'connect')
def receive_connect(dbapi_connection, connection_record):
    print('Database connected')

@event.listens_for(engine, 'close')
def receive_close(dbapi_connection, connection_record):
    print('Database disconnected')

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
