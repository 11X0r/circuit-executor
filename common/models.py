from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any, Union

from pydantic import BaseModel, Field, field_serializer

from common.utils.config import config


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    id: str

    circuit_qasm: str
    shots: int
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, int]] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    @field_serializer('created_at', 'completed_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        return dt.isoformat()
    
    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }


class TaskRequest(BaseModel):
    quantum_circuit: str
    shots: int = Field(
        default=1024,
        gt=0,
        description="Number of shots to run"
    )


class TaskResponse(BaseModel):
    task_id: str
    status: str
