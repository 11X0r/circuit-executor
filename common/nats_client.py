import json
import asyncio
from typing import Any, Dict, Callable

import nats

from common.utils.config import config
from common.utils.logging import setup_logging


logger = setup_logging(__name__)


class NATSClient:    
    def __init__(self):
        self.nc = None
        self.server = config["nats"]["url"]
        self.max_reconnect_attempts = config["nats"]["max_reconnect_attempts"]
        self.reconnect_time_wait = config["nats"]["reconnect_time_wait"]
    
    def is_connected(self) -> bool:
        return self.nc is not None and self.nc.is_connected
    
    async def connect(self) -> None:
        if self.is_connected():
            return
        
        logger.info(f"Connecting to NATS at {self.server}")
        try:
            self.nc = await nats.connect(self.server)
            logger.info(f"Connected to NATS")
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
    
    async def disconnect(self) -> None:
        if self.is_connected():
            await self.nc.close()
            self.nc = None
            logger.info("Disconnected from NATS")
    
    async def publish(self, subject: str, payload: Dict[str, Any]) -> None:
        if not self.is_connected():
            try:
                await self.connect()
            except Exception as e:
                logger.error(f"Failed to connect to NATS for publishing: {e}")
                return  # Continue without raising
            
        try:
            if self.is_connected():
                message = json.dumps(payload).encode()
                await self.nc.publish(subject, message)
                logger.info(f"Published message to {subject}")
            else:
                logger.warning(f"Cannot publish to {subject} - not connected to NATS")
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
   
    async def subscribe(self, subject: str, callback: Callable) -> None:
        if not self.is_connected():
            await self.connect()
            if not self.is_connected():
                logger.error("Not connected to NATS - cannot subscribe")
                return
        
        try:
            await self.nc.subscribe(subject, cb=callback)
            logger.info(f"Subscribed to {subject}")
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
