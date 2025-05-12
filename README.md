# Quantum Circuit Executor

A distributed system for executing quantum circuits using microservices, message queuing, and containerisation.

## Architecture

- **API Server**: FastAPI application that accepts circuit requests and retrieves results
- **Worker Service**: Asynchronous processor that executes quantum circuits
- **NATS**: Message broker for API-worker communication
- **Redis**: Data store for task persistence

## Quick Start

```bash
# Build and start all services
docker-compose up -d

# Check health status
curl http://localhost:8000/health

# Submit a Bell state circuit
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"quantum_circuit": "OPENQASM 3.0; include \"stdgates.inc\"; qubit[2] q; bit[2] c; h q[0]; cx q[0],q[1]; c[0] = measure q[0]; c[1] = measure q[1];", "shots": 1024}'

# Retrieve results (replace with your task_id)
curl http://localhost:8000/tasks/{task_id}
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tasks` | POST | Submit a quantum circuit for execution |
| `/tasks/{task_id}` | GET | Retrieve task results |
| `/health` | GET | Check system health |

## Implementation Notes

- **Execution Strategy**: Worker uses ThreadPoolExecutor for circuit execution, which empirically outperforms ProcessPoolExecutor for typical workloads (benchmark: 13.58s vs 19.02s for 21-23 qubit circuits)
- **GIL Considerations**: ThreadPoolExecutor performs better because Qiskit's C/C++ backend releases the GIL during simulation, making serialisation overhead of ProcessPoolExecutor more costly than GIL contention
- **Concurrency Control**: Semaphore limits concurrent task execution to prevent resource exhaustion
- **Message Handling**: NATS ensures reliable task delivery between API and worker
- **State Management**: Redis stores task metadata and execution results
- **Error Handling**: Comprehensive try/except blocks with status updates

## Configuration

Configuration options available via environment variables or config.toml:

```toml
[server]
host = "0.0.0.0"
port = 8000

[nats]
url = "nats://nats:4222"

[redis]
url = "redis://redis:6379"

[worker]
max_concurrent_tasks = 4  # Defaults to CPU count
```

## Testing

```bash
# Run integration tests
docker-compose exec api pytest -xvs tests/test_integration.py

# Run circuit utility tests
docker-compose exec api pytest -xvs tests/test_circuit_utils.py
```

## Performance Considerations

Based on extensive benchmarks with 21-23 qubit circuits:

| Execution Strategy | Performance | Relative Speed |
|-------------------|-------------|----------------|
| ThreadPoolExecutor | 13.58s | 1.00x (fastest) |
| Pure AsyncIO (Blocking) | 16.41s | 1.21x slower |
| ProcessPoolExecutor | 19.02s | 1.40x slower |
| Hybrid (Threads + Processes) | 27.97s | 2.06x slower |

ThreadPoolExecutor is the recommended default due to:
1. Qiskit's C/C++ backend releases the GIL during simulation
2. Serialisation overhead in ProcessPoolExecutor exceeds GIL benefits
3. Simpler implementation with better performance for circuits up to ~25 qubits

For extremely large circuits (>25 qubits) or workloads with 100K+ shots, ProcessPoolExecutor may eventually outperform by completely bypassing the GIL:

```python
# In worker/main.py, replace ThreadPoolExecutor with:
from concurrent.futures import ProcessPoolExecutor
process_pool = ProcessPoolExecutor(max_workers=min(mp.cpu_count(), 8))
```

## Scaling

Add more worker instances to process tasks in parallel. NATS queue groups ensure tasks are distributed evenly across workers.