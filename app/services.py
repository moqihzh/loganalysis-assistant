from datetime import datetime, timedelta
import pytz
from elasticsearch import Elasticsearch
import requests
import json
from dotenv import load_dotenv
import os
import re
import hashlib

load_dotenv()


class ESService:
    def __init__(self):
        self.es = Elasticsearch(
            os.getenv("ES_HOST"),
            basic_auth=(os.getenv("ES_USERNAME"), os.getenv("ES_PASSWORD")),
            verify_certs=False
        )
        self.beijing_tz = pytz.timezone('Asia/Shanghai')

    def get_recent_errors(self, minutes=5):
        try:
            print("[ES Query Debug] 准备发送错误分析请求")
            print(f"[ES Query Debug] ES Host: {os.getenv('ES_HOST')}")
            
            # 获取当前北京时间
            now = datetime.now(self.beijing_tz)
            # 生成多个可能的索引模式，包括今天和昨天
            today_index = f"log-{now.strftime('%Y.%m.%d')}"
            yesterday = now - timedelta(days=1)
            yesterday_index = f"log-{yesterday.strftime('%Y.%m.%d')}"
            index_pattern = f"{today_index},{yesterday_index}"
            
            # ES的range查询使用UTC时间，需要将北京时间转换为UTC
            utc_now = now.astimezone(pytz.UTC)
            utc_start = utc_now - timedelta(minutes=minutes)
            
            print(f"[ES Query Debug] index_pattern: {index_pattern}")
            print(f"[ES Query Debug] utc_now: {utc_now.isoformat()}")
            print(f"[ES Query Debug] utc_start: {utc_start.isoformat()}")
            
            # 执行查询
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "range": {
                                    "@timestamp": {
                                        "gte": utc_start.isoformat(),
                                        "lte": utc_now.isoformat()
                                    }
                                }
                            }
                        ],
                        "should": [
                            {"match": {"LogLevel": "fail"}},
                            {
                                "bool": {
                                    "must": [
                                        {"match": {"LogLevel": "info"}},
                                        {
                                            "range": {
                                                "Response.StatusCode": {
                                                    "gte": 501,
                                                    "lte": 504
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        ],
                        "minimum_should_match": 1
                    }
                },
                "sort": [
                    {"@timestamp": {"order": "desc"}}
                ],
                "_source": [
                    "@timestamp",
                    "LogLevel",
                    "Exception",
                    "ApplicationId",
                    "Message",
                    "StackTrace",
                    "Request.Path",
                    "Response.StatusCode"
                ]
            }

            print("[ES Query Debug] Executing query:", query)
            print("[ES Query Debug] Using index pattern:", index_pattern)
            result = self.es.search(index=index_pattern, body=query, size=100)
            print("[ES Query Debug] Query result:", result)
            
            logs = []
            for hit in result["hits"]["hits"]:
                source = hit["_source"]
                # 转换时间到北京时间
                utc_time = datetime.fromisoformat(source["@timestamp"].replace('Z', '+00:00'))
                beijing_time = utc_time.astimezone(self.beijing_tz)
                
                # 构建错误日志对象
                log_entry = {
                    "timestamp": beijing_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "application_id": source.get("ApplicationId", "未知应用"),
                    "Exception": source.get("Exception", ""),
                    "Message": source.get("Message", ""),
                    "StackTrace": source.get("StackTrace", ""),
                    "request_path": source.get("Request.Path", ""),
                    "status_code": source.get("Response.StatusCode", "")
                }
                
                # 组合完整的错误信息
                error_parts = []
                if log_entry["Exception"]:
                    error_parts.append(f"异常: {log_entry['Exception']}")
                if log_entry["Message"]:
                    error_parts.append(f"消息: {log_entry['Message']}")
                if log_entry["StackTrace"]:
                    error_parts.append(f"堆栈: {log_entry['StackTrace']}")
                
                log_entry["Exception"] = "\n".join(error_parts)
                logs.append(log_entry)
            
            print(f"[ES Query Debug] 检索到 {len(logs)} 条错误日志")
            return logs
        except Exception as e:
            print(f"[ES Query Debug] 发生错误: {str(e)}")
            print(f"[ES Query Debug] 错误类型: {e.__class__.__name__}")
            return []


class DeepseekService:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.api_url = os.getenv("DEEPSEEK_API_URL")
        self.model = "deepseek-chat"  # 使用基础模型名称

    def _simplify_error_log(self, error_log: str) -> str:
        """简化错误日志，提取关键信息"""
        # 将多行错误堆栈转为单行
        error_log = error_log.replace('\n', ' ').replace('\r', ' ')
        
        # 移除多余的空格
        error_log = ' '.join(error_log.split())
        
        # 提取关键信息的模式
        patterns = [
            r'Error: .*?(?=\s+at\s+|$)',  # 提取错误描述
            r'Exception: .*?(?=\s+at\s+|$)',  # 提取异常描述
            r'Failed to .*?(?=\s+at\s+|$)',  # 提取Failed to类型的错误
            r'status code (\d+)',  # 提取HTTP状态码
            r'at .*?:\d+:\d+',  # 保留最关键的堆栈信息
            r'Caused by: .*?(?=\s+at\s+|$)',  # 提取根本原因
            r'message: ".*?"',  # 提取错误消息
            r'reason: ".*?"'  # 提取错误原因
        ]
        
        # 提取匹配的关键信息
        key_info = []
        for pattern in patterns:
            matches = re.findall(pattern, error_log)
            if matches:
                # 如果是列表中的第一个模式（错误描述），保留更多内容
                if pattern == patterns[0]:
                    key_info.extend(matches[:3])  # 错误描述保留前三条
                else:
                    key_info.extend(matches[:1])  # 其他类型只保留第一条
        
        if not key_info:
            # 如果没有匹配到任何模式，尝试提取引号中的内容
            quoted = re.findall(r'"([^"]+)"', error_log)
            if quoted:
                return ' | '.join(quoted[:3])  # 最多保留3个引号中的内容
            # 如果还是没有，返回原始日志的前200个字符
            return error_log[:200] + ('...' if len(error_log) > 200 else '')
        
        # 组合关键信息，确保总长度不超过500字符
        simplified_log = ' | '.join(key_info)
        if len(simplified_log) > 500:
            return simplified_log[:500] + '...'
        return simplified_log

    def analyze_error(self, error_message: str) -> str:
        try:
            # 简化错误日志
            simplified_error = self._simplify_error_log(error_message)
            print(f"[Deepseek Debug] 原始错误日志长度: {len(error_message)} chars")
            print(f"[Deepseek Debug] 简化后日志长度: {len(simplified_error)} chars")
            print("[Deepseek Debug] 简化后日志内容:")
            print(simplified_error)
            
            print("[Deepseek Debug] 准备发送错误分析请求")
            print(f"[Deepseek Debug] API URL: {self.api_url}")
            print(f"[Deepseek Debug] Model: {self.model}")
            print(f"[Deepseek Debug] Error message length: {len(error_message)} chars")
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # 构建API请求数据
            data = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的错误日志分析助手。请简洁地分析错误原因并给出具体的解决方案。分析要点：1. 错误类型和关键信息 2. 可能的原因 3. 建议的解决方案"
                    },
                    {
                        "role": "user",
                        "content": f"分析以下错误日志（回答限200字）：\n{simplified_error}"
                    }
                ],
                "temperature": 0.3,
                "stream": False
            }
            
            # 打印详细的请求信息
            print("[Deepseek Debug] 发送API请求...")
            print(f"[Deepseek Debug] 请求参数: {json.dumps({k:v for k,v in data.items() if k != 'messages'}, ensure_ascii=False)}")
            print(f"[Deepseek Debug] 系统提示词长度: {len(data['messages'][0]['content'])} chars")
            print(f"[Deepseek Debug] 用户消息长度: {len(data['messages'][1]['content'])} chars")
            
            # 发送请求并处理响应
            response = requests.post(self.api_url, headers=headers, json=data, timeout=30)  # 添加超时设置
            print(f"[Deepseek Debug] API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("[Deepseek Debug] 成功获取响应")
                print(f"[Deepseek Debug] 响应内容: {json.dumps(result, ensure_ascii=False)}")
                if "choices" in result and len(result["choices"]) > 0:
                    analysis = result["choices"][0]["message"]["content"]
                    print(f"[Deepseek Debug] 分析结果长度: {len(analysis)} chars")
                    return analysis
                else:
                    print("[Deepseek Debug] 响应格式错误: choices不存在或为空")
                    return "分析服务返回格式错误"
            else:
                print(f"[Deepseek Debug] 请求失败: HTTP {response.status_code}")
                print(f"[Deepseek Debug] 错误响应: {response.text}")
                return f"分析服务请求失败 (HTTP {response.status_code})"
        except requests.Timeout:
            print("[Deepseek Debug] 请求超时")
            return "分析服务请求超时"
        except requests.RequestException as e:
            print(f"[Deepseek Debug] 网络请求错误: {str(e)}")
            return "分析服务网络错误"
        except Exception as e:
            print(f"[Deepseek Debug] 未预期的错误: {str(e)}")
            print(f"[Deepseek Debug] 错误类型: {e.__class__.__name__}")
            return "分析服务出现未知错误"


class WeChatService:
    def __init__(self):
        self.webhook_url = os.getenv("WECHAT_WEBHOOK_URL")
        self.max_content_length = 4000  # 留一些余量，避免达到4096的限制
        self.message_cache = {}  # 用于存储最近发送的消息
        self.cache_expire_minutes = 30  # 缓存过期时间（分钟）

    def _truncate_text(self, text: str, max_length: int) -> str:
        """截断文本，确保不超过最大长度，并添加省略号"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def _generate_message_key(self, error_info: str) -> str:
        """生成消息的唯一标识，用于判断重复"""
        # 提取错误信息中的关键部分
        # 1. 移除时间戳、IP地址等变化的信息
        cleaned_error = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '', error_info)
        cleaned_error = re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', '', cleaned_error)
        
        # 2. 移除行号等变化的信息
        cleaned_error = re.sub(r'line \d+', '', cleaned_error)
        cleaned_error = re.sub(r':\d+:\d+', '', cleaned_error)
        
        # 3. 提取错误类型和关键信息
        error_type = ''
        key_message = ''
        
        # 尝试匹配常见的错误模式
        error_match = re.search(r'(Error|Exception|Failed):[^\n]+', cleaned_error)
        if error_match:
            error_type = error_match.group(0)
        
        # 尝试提取引号中的关键信息
        message_match = re.search(r'"([^"]+)"', cleaned_error)
        if message_match:
            key_message = message_match.group(1)
        
        # 组合特征值
        key_parts = []
        if error_type:
            key_parts.append(error_type)
        if key_message:
            key_parts.append(key_message)
        if not key_parts:  # 如果没有提取到特征，使用清理后的错误信息前100个字符
            key_parts.append(cleaned_error[:100])
        
        # 使用MD5生成最终的特征值
        key = '|'.join(key_parts)
        return hashlib.md5(key.encode()).hexdigest()

    def _is_duplicate_message(self, error_info: str) -> bool:
        """检查是否是重复消息"""
        current_time = datetime.now(pytz.timezone('Asia/Shanghai'))
        message_key = self._generate_message_key(error_info)
        
        # 清理过期的缓存
        expired_keys = []
        for key, (timestamp, count) in self.message_cache.items():
            if (current_time - timestamp).total_seconds() > self.cache_expire_minutes * 60:
                print(f"[WeChat Debug] 清理过期消息缓存: {key} (发送次数: {count})")
                expired_keys.append(key)
        for key in expired_keys:
            del self.message_cache[key]
        
        # 检查是否存在相同的消息
        if message_key in self.message_cache:
            last_time, count = self.message_cache[message_key]
            time_diff = (current_time - last_time).total_seconds() / 60  # 转换为分钟
            
            # 更新计数和时间戳
            self.message_cache[message_key] = (current_time, count + 1)
            
            print(f"[WeChat Debug] 检测到重复消息:")
            print(f"[WeChat Debug] - 消息特征值: {message_key}")
            print(f"[WeChat Debug] - 首次发送时间: {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"[WeChat Debug] - 距上次发送: {time_diff:.1f}分钟")
            print(f"[WeChat Debug] - 累计次数: {count + 1}")
            return True
        
        # 新消息，添加到缓存
        print(f"[WeChat Debug] 新消息特征值: {message_key}")
        self.message_cache[message_key] = (current_time, 1)
        return False

    def send_alert(self, error_info: dict, analysis: str):
        try:
            print("[WeChat Debug] 准备发送企业微信通知")
            print(f"[WeChat Debug] Webhook URL: {self.webhook_url}")
            print(f"[WeChat Debug] Error info: {json.dumps(error_info, ensure_ascii=False)}")
            print(f"[WeChat Debug] Analysis length: {len(analysis)} chars")
            
            # 检查是否是重复消息
            if self._is_duplicate_message(error_info["Exception"]):
                # 如果是重复消息，检查是否需要发送汇总
                current_time = datetime.now(pytz.timezone('Asia/Shanghai'))
                message_key = self._generate_message_key(error_info["Exception"])
                last_time, count = self.message_cache[message_key]
                
                # 每隔10次或者每隔1小时发送一次汇总
                time_diff = (current_time - last_time).total_seconds() / 3600  # 转换为小时
                if count % 10 == 0 or time_diff >= 1:
                    # 构建汇总消息
                    content = f"""### 系统异常告警（汇总）
> 发生时间：{current_time.strftime('%Y-%m-%d %H:%M:%S')}
> 汇总周期：{f"{time_diff:.1f}小时" if time_diff >= 1 else f"{count}次"}
> 应用ID：<font color=\"warning\">{error_info.get("application_id", "未知应用")}</font>

**开发环境业务日志异常信息**：
{self._truncate_text(error_info["Exception"], 1000)}

**DeepSeek分析结果**：
{self._truncate_text(analysis, 1000)}

**统计信息**：
- 首次出现：{last_time.strftime('%Y-%m-%d %H:%M:%S')}
- 累计次数：{count}次
- 平均频率：{(count / time_diff):.1f}次/小时"""

                    message = {
                        "msgtype": "markdown",
                        "markdown": {"content": content}
                    }
                    
                    print("[WeChat Debug] 发送汇总消息...")
                    print(f"[WeChat Debug] 汇总周期: {f'{time_diff:.1f}小时' if time_diff >= 1 else f'{count}次'}")
                    print(f"[WeChat Debug] 消息总长度: {len(content)} chars")
                    
                    response = requests.post(self.webhook_url, json=message, timeout=10)
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("errcode") == 0:
                            print("[WeChat Debug] 汇总消息发送成功")
                            return True
                    print(f"[WeChat Debug] 汇总消息发送失败: {response.text}")
                    
                print("[WeChat Debug] 跳过发送重复消息")
                return True
            
            # 计算各部分内容的最大长度
            template_length = 100
            max_error_length = min(2000, (self.max_content_length - template_length) // 2)
            max_analysis_length = min(2000, self.max_content_length - template_length - len(self._truncate_text(error_info["Exception"], max_error_length)))
            
            # 截断错误信息和分析结果
            truncated_error = self._truncate_text(error_info["Exception"], max_error_length)
            truncated_analysis = self._truncate_text(analysis, max_analysis_length)
            
            # 构建消息内容
            current_time = datetime.now(pytz.timezone('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')
            content = f"""### 系统异常告警
> 发生时间：{current_time}
> 应用ID：<font color=\"warning\">{error_info.get("application_id", "未知应用")}</font>
> 请求路径：{error_info.get("request_path", "未知路径")}

**开发环境业务日志异常信息**：
{truncated_error}

**DeepSeek分析结果**：
{truncated_analysis}"""
            
            message = {
                "msgtype": "markdown",
                "markdown": {"content": content}
            }
            
            # 打印消息详情
            print("[WeChat Debug] 消息内容预览:")
            print(f"[WeChat Debug] 发送时间: {current_time}")
            print(f"[WeChat Debug] 截断后错误信息长度: {len(truncated_error)} chars")
            print(f"[WeChat Debug] 截断后分析结果长度: {len(truncated_analysis)} chars")
            print(f"[WeChat Debug] 消息总长度: {len(content)} chars")
            
            # 发送请求
            print("[WeChat Debug] 发送消息...")
            response = requests.post(self.webhook_url, json=message, timeout=10)
            print(f"[WeChat Debug] 发送状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("[WeChat Debug] 响应内容:", json.dumps(result, ensure_ascii=False))
                if result.get("errcode") == 0:
                    print("[WeChat Debug] 消息发送成功")
                    return True
                else:
                    print(f"[WeChat Debug] 发送失败: {result.get('errmsg', '未知错误')}")
                    return False
            else:
                print(f"[WeChat Debug] 请求失败: HTTP {response.status_code}")
                print(f"[WeChat Debug] 错误响应: {response.text}")
                return False
                
        except requests.Timeout:
            print("[WeChat Debug] 请求超时")
            return False
        except requests.RequestException as e:
            print(f"[WeChat Debug] 网络请求错误: {str(e)}")
            return False
        except Exception as e:
            print(f"[WeChat Debug] 未预期的错误: {str(e)}")
            print(f"[WeChat Debug] 错误类型: {e.__class__.__name__}")
            return False
