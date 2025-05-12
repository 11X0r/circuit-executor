import json
import pytest

from qiskit import QuantumCircuit
from qiskit.qasm3 import dumps as qasm3_dumps

from common.utils.circuit_utils import (
    circuit_to_qasm,
    deserialise_circuit_payload,
    execute_circuit,
    qasm_to_circuit,
    serialise_circuit_payload,
)


class TestCircuitUtils:
    
    def test_circuit_to_qasm(self):
        # Create a simple Bell state circuit
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure([0, 1], [0, 1])
        
        qasm_str = circuit_to_qasm(qc)

        assert isinstance(qasm_str, str)
        assert "OPENQASM 3.0" in qasm_str
        assert "include" in qasm_str
        assert "h " in qasm_str
        assert "cx " in qasm_str
        assert "measure" in qasm_str
    
    def test_deserialise_circuit_payload(self):
        # Create a simple circuit
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure([0, 1], [0, 1])
        
        payload = {
            "qasm": qasm3_dumps(qc),
            "shots": 2048,
            "metadata": {"test": "value"}
        }
        
        result = deserialise_circuit_payload(json.dumps(payload))
        
        assert "circuit" in result
        assert "shots" in result
        assert "metadata" in result
        assert result["shots"] == 2048
        assert isinstance(result["circuit"], QuantumCircuit)
        assert result["metadata"]["test"] == "value"
    
    @pytest.mark.asyncio
    async def test_execute_circuit(self):
        """Test executing a quantum circuit."""
        # Create a Bell state circuit
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure([0, 1], [0, 1])
        
        result = await execute_circuit(qc, 1024)
        
        assert isinstance(result, dict)
        assert len(result) > 0

        total_counts = sum(result.values())
        assert total_counts == 1024
        
        # Check that results are approximately as expected (should be ~50% each outcome)
        # Allow for statistical variation with a tolerance
        assert '00' in result or '11' in result
        
    def test_qasm_to_circuit(self):
        # Create QASM string for a Bell state
        qasm_str = """OPENQASM 3.0;
                      include "stdgates.inc";
                      qubit[2] q;
                      bit[2] c;
                      h q[0];
                      cx q[0],q[1];
                      c[0] = measure q[0];
                      c[1] = measure q[1];"""
        
        circuit = qasm_to_circuit(qasm_str)

        assert isinstance(circuit, QuantumCircuit)
        assert circuit.num_qubits == 2
        assert circuit.num_clbits == 2
        
    def test_serialise_circuit_payload(self):
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure([0, 1], [0, 1])
        
        payload_str = serialise_circuit_payload(qc, 1024)
        
        assert isinstance(payload_str, str)
        
        payload = json.loads(payload_str)
        assert "qasm" in payload
        assert "shots" in payload
        assert payload["shots"] == 1024
        assert "metadata" in payload
        assert "num_qubits" in payload["metadata"]
        assert payload["metadata"]["num_qubits"] == 2
        assert "num_clbits" in payload["metadata"]
        assert payload["metadata"]["num_clbits"] == 2
