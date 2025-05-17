import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
import multiprocessing as mp
import atexit
from typing import Dict, Any, Optional

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit.qasm3 import dumps as qasm3_dumps
from qiskit.qasm3 import loads as qasm3_loads
from qiskit.exceptions import QiskitError

from common.utils.logging import setup_logging

logger = setup_logging(__name__)

# Create a thread pool for executing circuits
thread_pool = ThreadPoolExecutor(max_workers=max(2, min(mp.cpu_count(), 8)))
simulator = AerSimulator()

# Register thread pool shutdown at exit
atexit.register(lambda: thread_pool.shutdown(wait=False))

# --- QASM conversion functions ---

def circuit_to_qasm(circuit: QuantumCircuit) -> str:
    """Convert a QuantumCircuit to QASM3 string."""
    try:
        qasm_str = qasm3_dumps(circuit)
        logger.debug(f"Converted circuit to QASM: {qasm_str[:50]}...")
        return qasm_str
    except QiskitError as e:
        logger.error(f"Error converting circuit to QASM: {e}")
        raise


def qasm_to_circuit(qasm_str: str) -> QuantumCircuit:
    """Convert QASM3 string to QuantumCircuit."""
    try:
        circuit = qasm3_loads(qasm_str)
        logger.debug(f"Converted QASM to circuit with {circuit.num_qubits} qubits")
        return circuit
    except QiskitError as e:
        logger.error(f"Error converting QASM to circuit: {e}")
        raise


# --- Payload serialization functions ---

def deserialise_circuit_payload(payload_str: str) -> Dict[str, Any]:
    """Deserialise NATS message to circuit and metadata."""
    try:
        payload = json.loads(payload_str)
        circuit = qasm_to_circuit(payload["qasm"])
        return {
            "circuit": circuit,
            "shots": payload.get("shots", 1024),
            "metadata": payload.get("metadata", {})
        }
    except (QiskitError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error deserialising circuit payload: {e}")
        raise


def serialise_circuit_payload(circuit: QuantumCircuit, shots: Optional[int] = None) -> str:
    """Serialise circuit and metadata for NATS message."""
    try:
        payload = {
            "qasm": circuit_to_qasm(circuit),
            "shots": shots or 1024,
            "metadata": {
                "num_qubits": circuit.num_qubits,
                "num_clbits": circuit.num_clbits
            }
        }
        return json.dumps(payload)
    except (QiskitError, TypeError, json.JSONEncodeError) as e:
        logger.error(f"Error serialising circuit payload: {e}")
        raise


# --- Circuit execution functions ---

async def execute_circuit(circuit: QuantumCircuit, shots: int) -> Dict[str, int]:
    """Execute a quantum circuit asynchronously.
    
    This function offloads the circuit execution to a thread pool
    to keep the event loop responsive during CPU-intensive work.
    
    Args:
        circuit: The quantum circuit to execute
        shots: Number of shots for the simulation
        
    Returns:
        A dictionary of measurement results
    """
    def _execute_in_thread(circuit: QuantumCircuit, shots: int) -> Dict[str, int]:
        """Execute circuit in a thread to avoid blocking the event loop."""
        logger.debug(f"Executing circuit with {circuit.num_qubits} qubits and {shots} shots")
        try:
            result = simulator.run(circuit, shots=shots).result()
            return result.get_counts(circuit)
        except Exception as e:
            logger.error(f"Error executing circuit: {e}")
            raise
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        thread_pool,
        _execute_in_thread,
        circuit,
        shots
    )
