import httpx
import json
from aistack.config.config import Config
import logging
logger = logging.getLogger(__name__)
class TaskAPIClient:
    def __init__(self):
        self.client = httpx.Client(base_url=Config().api_base_url)
        self.headers = {
            "X-Parse-Application-Id": Config().parse_app_id,
            "X-Parse-REST-API-Key": Config().parse_api_key,
            "X-Parse-Revocable-Session": "1",
            "Content-Type": "application/json"
        }
    
    def get_pending_tasks(self, task_type: str, limit: int = 2):
        try:
            params={"where": json.dumps({
                    "type": task_type,
                    "status": 0  # 0表示待处理状态
                }), "skip": 0,"limit": limit}
            
            response = self.client.get(
                Config().task_path,
                params=params,
                headers=self.headers
            )
            # 关键检查：HTTP状态码异常时抛出HTTPError
            response.raise_for_status()  
            
            # 返回解析后的JSON数据
            return response.json().get("results", [])
        except httpx.HTTPStatusError as e:
            logger.error(f"API请求失败: {e.response.status_code} {e.request.url}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"响应解析失败: {e}")
            raise
        except Exception as e:
            logger.error(f"未知错误: {e}")
            raise

    
   
    
    def update_task(self, task_id: str, status: int, account_id: str = None, result: list = None ):
        logger.info(f"更新任务状态 任务ID: {task_id} 新状态: {status}")
        try:
            response = self.client.put(
                f"{Config().task_path}/{task_id}",
                json={
                    "status": status,
                    "result": result or [],
                    "executor": account_id if account_id else "unknown"  # 补充executor字段
                },
                headers=self.headers
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"任务状态更新失败: {str(e)}")
            raise  # 可选：重新抛出异常供调用方处理
