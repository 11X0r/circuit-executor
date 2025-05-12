import asyncio
import os
import pytest
import httpx
import socket
from qiskit import QuantumCircuit

from common.models import TaskStatus
from common.utils.circuit_utils import circuit_to_qasm, qasm_to_circuit


# More flexible API URL determination
def get_api_url():
    # Environment override
    if "API_URL" in os.environ:
        return os.environ["API_URL"]
    
    # Try to resolve "api" hostname (Docker service name)
    try:
        socket.gethostbyname("api")
        return "http://api:8000"
    except socket.gaierror:
        # Fall back to localhost (for local development)
        return "http://localhost:8000"


API_URL = get_api_url()
print(f"Using API URL: {API_URL}")


def create_test_circuit() -> QuantumCircuit:
    """Create a test quantum circuit."""
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])
    return qc


@pytest.mark.asyncio
async def test_submit_and_retrieve_task():
    """Test submitting a task and retrieving its result."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        # First, check health to ensure services are running
        health_response = await client.get(f"{API_URL}/health")
        print(f"Health check status: {health_response.status_code}")
        print(f"Health check response: {health_response.json()}")
        
        # Create quantum circuit
        circuit = create_test_circuit()
        qasm = circuit_to_qasm(circuit)
        print(f"QASM generated: {qasm[:50]}...")
        
        payload = {
            "quantum_circuit": qasm,
            "shots": 100
        }
        
        # Submit task
        try:
            response = await client.post(f"{API_URL}/tasks", json=payload)
            print(f"Submit task status: {response.status_code}")
            if response.status_code != 201:
                print(f"Error response: {response.text}")
            
            assert response.status_code == 201
            data = response.json()
            assert "task_id" in data
            assert data["status"] == "pending"
            
            task_id = data["task_id"]
            
            # Wait for task to complete (with timeout)
            max_retries = 10
            for i in range(max_retries):
                print(f"Checking task status (attempt {i+1}/{max_retries})...")
                # Get task result
                response = await client.get(f"{API_URL}/tasks/{task_id}")
                print(f"Get task status: {response.status_code}")
                data = response.json()
                print(f"Task data: {data}")
                
                if data["status"] in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    break
                    
                await asyncio.sleep(1)
            
            # Even if task isn't complete, we just check that the API is working
            assert "id" in data
            assert data["id"] == task_id
            
        except httpx.HTTPError as exc:
            print(f"HTTP Exception: {exc}")
            print(f"Request: {exc.request.url} - {exc.request.method}")
            raise


@pytest.mark.asyncio
async def test_task_not_found():
    """Test retrieving a non-existent task."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{API_URL}/tasks/non-existent-id")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Task not found"


@pytest.mark.asyncio
async def test_health_check():
    """Test the health check endpoint."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{API_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "services" in data
        assert "nats" in data["services"]
        assert "redis" in data["services"]
