# 错误日志分析助手

- 一个基于FastAPI的业务系统错误日志分析助手，可以自动从Elasticsearch获取错误日志，使用Deepseek进行智能分析，并通过企业微信机器人发送通知。
- 本系统大部分代码由AI完成，少量代码由人工完成。

## 功能特点

- 自动获取ES中最近5分钟的错误日志
- 使用Deepseek AI进行智能分析
- 发送分析结果到企业微信群
- 将日志和分析结果存储到MySQL数据库
- 提供REST API接口查询历史记录
- 提供Web界面查看和管理日志分析结果

## Web界面功能

- 分页展示日志分析记录
- 显示错误日志详情和AI分析结果
- 手动触发日志分析任务
- 实时显示任务执行状态
- 支持查看完整的错误信息和分析报告

## 系统要求

- Python 3.8+
- MySQL 5.7+
- Elasticsearch 7+
- 企业微信机器人
- Deepseek API密钥
- 现代Web浏览器（Chrome、Firefox、Safari等）

## 安装步骤

1. 克隆代码库后，创建并激活虚拟环境：
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows CMD
venv\Scripts\activate.ps1 # Windows PowerShell
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
```bash
cp .env.example .env
```
编辑.env文件，填入实际的配置信息：
- ES_HOST: Elasticsearch服务器地址
- MYSQL_URL: MySQL连接URL
- DEEPSEEK_API_KEY: Deepseek API密钥
- DEEPSEEK_API_URL: Deepseek API地址
- WECHAT_WEBHOOK_URL: 企业微信机器人Webhook地址

4. 创建MySQL数据库：
```sql
source sql/initdb.sql;
```

## 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动后访问 http://localhost:8000 即可打开Web管理界面。

## API接口

### 触发日志分析
```bash
curl -X POST http://localhost:8000/analyze
```

### 查询历史记录
```bash
curl http://localhost:8000/logs
```

## 定时任务配置

建议配置cron任务每5分钟触发一次分析：

```bash
*/5 * * * * curl -X POST http://localhost:8000/analyze
```

## 页面截图
![截图1](/screenshot/image.png)
![截图2](/screenshot/image2.png)
## Web界面使用说明

1. 日志列表页面
   - 显示所有日志记录，包括错误发生时间、应用ID和错误摘要
   - 支持分页浏览，每页显示10条记录
   - 点击"详情"按钮可查看完整的错误信息和分析结果

2. 手动分析
   - 点击"触发分析"按钮可手动启动新的分析任务
   - 任务状态会实时显示在界面上
   - 分析完成后会自动刷新日志列表

## ElasticSearch日志格式参考
- ES索引格式: log-YYYY.MM.DD
- 日志格式:
```json
{
    "_index": "log-2025.03.16",
    "_type": "_doc",
    "_id": "4u61nJUB35d6noNTkaiq",
    "_version": 1,
    "_score": null,
    "_source": {
      "ParentTrackId": "",
      "Exception": "Quartz.JobPersistenceException: Couldn't store trigger 'DEFAULT.716_0000000000001' for 'default.716_12' job: Couldn't retrieve job because a required type was not ",
      "HostIPAddress": "192.168.15.252",
      "Message": "Error handling misfires: Couldn't store trigger 'DEFAULT.716_0000000000001' for 'default.716_12' job: Couldn't retrieve job because a required type was not found: Could not load type 'jobscheduler.JobModels.HttpServiceJob, jobscheduler'",
      "ThreadName": null,
      "ApplicationId": "jobscheduler",
      "LogType": "0",
      "ChainId": "",
      "TrackId": "",
      "LogName": "Quartz.Impl.AdoJobStore.MisfireHandler",
      "@timestamp": "2025-03-16T10:08:19.780Z",
      "LogTime": "2025-03-16T10:08:04.3857406+08:00",
      "ThreadId": 34,
      "@version": "1",
      "LogLevel": "fail",
      "EventId": 0
    },
    "fields": {
      "@timestamp": [
        "2025-03-16T10:08:19.780Z"
      ],
      "LogTime": [
        "2025-03-16T02:08:04.385Z"
      ]
    },
    "highlight": {
      "LogLevel": [
        "@kibana-highlighted-field@fail@/kibana-highlighted-field@"
      ]
    },
    "sort": [
      1742119699780
    ]
  }
```