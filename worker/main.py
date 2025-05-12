"""Worker service for the quantum circuit executor."""
import asyncio
import json
import signal
from datetime import datetime, timezone
from typing import Dict, Any, Set

from common.models import TaskStatus
from common.nats_client import NATSClient
from common.redis_client import RedisClient
from common.utils.circuit_utils import qasm_to_circuit, execute_circuit
from common.utils.config import config
from common.utils.logging import setup_logging

logger = setup_logging(__name__)

nats_client = NATSClient()
redis_client = RedisClient()

max_concurrent_tasks = config["worker"].get("max_concurrent_tasks", 4)
sem = asyncio.Semaphore(max_concurrent_tasks)

active_tasks: Set[str] = set()


async def main() -> None:
    """Main worker function."""
    logger.info("Starting worker service")
    

    setup_signal_handlers()
    
    await connect_to_services()

    if nats_client.is_connected():
        await subscribe_to_tasks()
    else:
        logger.warning("NATS not connected - cannot subscribe to tasks")
    
    await maintain_service_connections()


def setup_signal_handlers() -> None:
    """Setup signal handlers for graceful shutdown."""
    loop = asyncio.get_event_loop()
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(sig))
        )
    
    logger.info("Signal handlers registered for graceful shutdown")


async def shutdown(signal: signal.Signals) -> None:
    """Handle graceful shutdown on receiving a signal."""
    logger.info(f"Received exit signal {signal.name}...")
    
    # Wait for active tasks to finish (with timeout)
    if active_tasks:
        logger.info(f"Waiting for {len(active_tasks)} active tasks to complete...")
        try:
            # Give active tasks some time to finish, but don't wait forever
            shutdown_timeout = 10  # seconds
            await asyncio.wait_for(
                asyncio.gather(*[asyncio.sleep(0.1) for _ in range(len(active_tasks))]),
                timeout=shutdown_timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Shutdown timeout reached with {len(active_tasks)} tasks still active")
    
    logger.info("Disconnecting from services...")
    try:
        await nats_client.disconnect()
    except Exception as e:
        logger.error(f"Error disconnecting from NATS: {e}")
    
    try:
        await redis_client.disconnect()
    except Exception as e:
        logger.error(f"Error disconnecting from Redis: {e}")

    logger.info("Stopping event loop...")
    asyncio.get_event_loop().stop()


async def connect_to_services() -> None:
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


async def maintain_service_connections() -> None:
    while True:
        # If not connected to NATS, try to reconnect
        if not nats_client.is_connected():
            try:
                await nats_client.connect()
                if nats_client.is_connected():
                    await subscribe_to_tasks()
            except Exception as e:
                logger.error(f"Failed to reconnect to NATS: {e}")
        
        await asyncio.sleep(5)


async def subscribe_to_tasks() -> None:
    if not nats_client.is_connected():
        await nats_client.connect()
        
    await nats_client.subscribe("tasks", handle_task_message)
    logger.info("Subscribed to 'tasks' subject")


async def handle_task_message(msg) -> None:
    try:
        payload = json.loads(msg.data.decode())
        task_id = payload.get("task_id")
        
        if not task_id:
            logger.error("Received message without task_id")
            return
            
        logger.info(f"Received task {task_id}")
        
        await sem.acquire()
        
        task = asyncio.create_task(process_task(task_id))
        task.add_done_callback(lambda _: sem.release())
        
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        sem.release()


async def process_task(task_id: str) -> None:
    active_tasks.add(task_id)
    
    try:
        logger.info(f"Processing task {task_id}")
        
        task_data = await redis_client.get_task(task_id)
        if not task_data:
            logger.error(f"Task {task_id} not found in Redis")
            return
        
        task_data["status"] = TaskStatus.PROCESSING
        await redis_client.set_task(task_id, task_data)
        
        circuit = qasm_to_circuit(task_data["circuit_qasm"])
        shots = task_data["shots"]
        
        logger.info(f"Executing circuit with {circuit.num_qubits} qubits and {shots} shots")
        start_time = datetime.now(timezone.utc)  # Changed from UTC to utc
        
        counts = await execute_circuit(circuit, shots)
        
        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()  # Changed from UTC to utc
        logger.info(f"Circuit execution completed in {execution_time:.2f} seconds")
        
        task_data["result"] = counts
        task_data["status"] = TaskStatus.COMPLETED
        task_data["completed_at"] = datetime.now(timezone.utc)  # Changed from UTC to utc
        
        await redis_client.set_task(task_id, task_data)
        logger.info(f"Task {task_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {e}")
        await handle_task_error(task_id, str(e))
    finally:
        active_tasks.discard(task_id)


async def handle_task_error(task_id: str, error_message: str) -> None:
    try:
        # Update task with error
        task_data = await redis_client.get_task(task_id)
        if task_data:
            task_data["status"] = TaskStatus.FAILED
            task_data["error"] = error_message
            task_data["completed_at"] = datetime.now(timezone.utc)  # Changed from UTC to utc
            await redis_client.set_task(task_id, task_data)
            logger.info(f"Updated task {task_id} with error status")
    except Exception as e:
        logger.error(f"Failed to update task {task_id} with error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker service stopped by user")
