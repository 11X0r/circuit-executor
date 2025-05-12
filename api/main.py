import uuid
import json
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from common.models import Task, TaskStatus
from common.nats_client import NATSClient
from common.redis_client import RedisClient
from common.redis_client import CustomJSONEncoder
from common.utils.logging import setup_logging


logger = setup_logging(__name__)
nats_client = NATSClient()
redis_client = RedisClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting API server")
    
    try:
        await nats_client.connect()
        logger.info("Connected to NATS")
    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")
    
    try:
        await redis_client.connect()
        logger.info("Connected to Redis")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
    
    logger.info("API server started and ready for requests")
    yield
    
    logger.info("Shutting down API server")
    try:
        await nats_client.disconnect()
    except Exception as e:
        logger.error(f"Error disconnecting from NATS: {e}")
        
    try:
        await redis_client.disconnect()
    except Exception as e:
        logger.error(f"Error disconnecting from Redis: {e}")


app = FastAPI(lifespan=lifespan)


class QuantumCircuitRequest(BaseModel):
    quantum_circuit: str
    shots: int


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    is_nats_connected = nats_client.is_connected()
    is_redis_connected = False
    
    try:
        is_redis_connected = await redis_client.ping()
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
    
    return {
        "status": "healthy",
        "services": {
            "nats": is_nats_connected,
            "redis": is_redis_connected
        }
    }


@app.post("/tasks", status_code=201)
async def submit_task(request: QuantumCircuitRequest):
    """Submit a quantum circuit for execution."""
    task_id = str(uuid.uuid4())
    
    try:
        task = Task(
            id=task_id,
            circuit_qasm=request.quantum_circuit,
            shots=request.shots,
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        try:
            try:
                task_data = task.model_dump()
            except AttributeError:
                task_data = task.dict()
            
            task_json = json.dumps(task_data, cls=CustomJSONEncoder)
            task_data = json.loads(task_json)
            
            await redis_client.set_task(task_id, task_data)
            logger.info(f"Task {task_id} stored in Redis")
        except Exception as e:
            logger.error(f"Failed to store task in Redis: {e}")
            raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}")
        
        try:
            if nats_client.is_connected():
                await nats_client.publish("tasks", {"task_id": task_id})
                logger.info(f"Task {task_id} published to NATS")
            else:
                logger.warning(f"NATS not connected - task {task_id} not published")
        except Exception as e:
            logger.error(f"Error publishing task to NATS: {e}")
            # Non-critical error, continue without failing
        
        return {"task_id": task_id, "status": "pending"}
        
    except Exception as e:
        logger.error(f"Unexpected error submitting task: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating task: {str(e)}")


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Retrieve a task by ID."""
    try:
        task_data = await redis_client.get_task(task_id)
        
        if not task_data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return task_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve task")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
