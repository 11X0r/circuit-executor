import json
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional

import redis.asyncio as redis

from common.utils.config import config
from common.utils.logging import setup_logging


logger = setup_logging(__name__)

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


class RedisClient:    
    def __init__(self):
        self.redis = None
        self.url = config["redis"]["url"]
        self.db = config["redis"]["db"]
    
    async def connect(self) -> None:
        if self.redis is not None:
            return
        
        try:
            self.redis = redis.from_url(
                self.url,
                db=self.db,
                decode_responses=True
            )
            logger.info(f"Connected to Redis at {self.url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self) -> None:
        if self.redis is not None:
            try:
                await self.redis.close()
                self.redis = None
                logger.info("Disconnected from Redis")
            except Exception as e:
                logger.error(f"Error disconnecting from Redis: {e}")
                self.redis = None
    
    async def ping(self) -> bool:
        """Ping Redis to check connection."""
        if self.redis is None:
            try:
                await self.connect()
            except:
                return False
                
        try:
            return await self.redis.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    async def set_task(self, task_id: str, task_data: Dict[str, Any]) -> None:
        if self.redis is None:
            await self.connect()
        
        key = f"task:{task_id}"
        try:
            json_data = json.dumps(task_data, cls=CustomJSONEncoder)
            await self.redis.set(key, json_data)
            logger.info(f"Stored task {task_id} in Redis")
        except Exception as e:
            logger.error(f"Failed to store task {task_id} in Redis: {e}")
            raise
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        if self.redis is None:
            await self.connect()
        
        key = f"task:{task_id}"
        try:
            data = await self.redis.get(key)
            if data is None:
                logger.info(f"Task {task_id} not found in Redis")
                return None
            
            return json.loads(data)
        except Exception as e:
            logger.error(f"Failed to retrieve task {task_id} from Redis: {e}")
            raise
