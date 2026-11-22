from __future__ import annotations

from unittest import mock

from src.vision.backends import (
    BackendKind,
    RawDetection,
    probe_backends,
    select_backend,
)


def test_backend_kind_enum():
    assert BackendKind.CPU.value == "cpu"
    assert BackendKind.CUDA.value == "cuda"
    assert BackendKind.OPENVINO.value == "openvino"
    assert BackendKind.TENSORRT.value == "tensorrt"
    assert BackendKind.MPS.value == "mps"

@mock.patch("src.vision.backends._module_available")
def test_probe_backends_only_cpu(mock_mod_avail):
    mock_mod_avail.return_value = False
    backends = probe_backends()
    assert backends == {BackendKind.CPU}

@mock.patch("src.vision.backends._module_available")
def test_probe_backends_openvino(mock_mod_avail):
    def side_effect(name):
        return name == "openvino"
    mock_mod_avail.side_effect = side_effect
    
    backends = probe_backends()
    assert backends == {BackendKind.CPU, BackendKind.OPENVINO}

def test_select_backend_auto_fallback():
    # If openvino and cpu are available, it should prefer OPENVINO based on PREFERENCE order
    avail = {BackendKind.CPU, BackendKind.OPENVINO}
    assert select_backend("auto", available=avail) == BackendKind.OPENVINO
    
    # If only cpu is available
    assert select_backend("auto", available={BackendKind.CPU}) == BackendKind.CPU

def test_select_backend_specific():
    avail = {BackendKind.CPU, BackendKind.CUDA}
    
    # Exact match
    assert select_backend("cuda", available=avail) == BackendKind.CUDA
    
    # Mapping 'cuda:0' to 'cuda'
    assert select_backend("cuda:0", available=avail) == BackendKind.CUDA
    
    # Unavailable requested degrades to best available (CUDA in this case)
    assert select_backend("tensorrt", available=avail) == BackendKind.CUDA
    
    # Unknown degrades to best available
    assert select_backend("unknown", available=avail) == BackendKind.CUDA

def test_raw_detection():
    det = RawDetection(label="person", confidence=0.9, box=(10, 20, 30, 40))
    assert det.label == "person"
    assert det.confidence == 0.9
    assert det.box == (10, 20, 30, 40)
