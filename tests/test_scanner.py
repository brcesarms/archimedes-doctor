"""
Testes unitários para o módulo scanner e runner do Archimedes Doctor.
"""

from pathlib import Path
from src.scanner import (
    extract_functions_and_classes,
    locate_or_propose_test_file,
    get_existing_tests_in_file,
)
from src.runner import _extract_surgical_traceback


def test_extract_functions_and_classes(tmp_path):
    code = '''
class UserService:
    def __init__(self, db):
        self.db = db

    def get_user(self, user_id: int):
        return {"id": user_id}

def calculate_hash(data: str) -> str:
    return "hash"

async def async_fetch():
    pass
'''
    py_file = tmp_path / "sample.py"
    py_file.write_text(code, encoding="utf-8")

    defs = extract_functions_and_classes(py_file)
    names = [d["name"] for d in defs]

    assert "UserService" in names
    assert "UserService.__init__" in names
    assert "UserService.get_user" in names
    assert "calculate_hash" in names
    assert "async_fetch" in names


def test_locate_or_propose_test_file(tmp_path):
    repo = tmp_path
    src = repo / "src" / "math_ops.py"
    src.parent.mkdir(parents=True)
    src.touch()

    proposed = locate_or_propose_test_file(src, repo)
    assert proposed == repo / "tests" / "test_math_ops.py"


def test_get_existing_tests_in_file(tmp_path):
    test_code = '''
def test_addition():
    assert 1 + 1 == 2

def test_subtraction():
    assert 2 - 1 == 1

class TestComplex:
    def test_multiplication(self):
        assert 2 * 2 == 4
'''
    test_file = tmp_path / "test_example.py"
    test_file.write_text(test_code, encoding="utf-8")

    tests = get_existing_tests_in_file(test_file)
    assert "test_addition" in tests
    assert "test_subtraction" in tests
    assert "test_multiplication" in tests


def test_extract_surgical_traceback():
    sample_output = """
============================= test session starts ==============================
collected 2 items

tests/test_demo.py .F                                                    [100%]

=================================== FAILURES ===================================
_________________________________ test_failure _________________________________

    def test_failure():
>       assert 1 == 2
E       assert 1 == 2

tests/test_demo.py:4: AssertionError
=========================== short test summary info ============================
FAILED tests/test_demo.py::test_failure - assert 1 == 2
========================= 1 failed, 1 passed in 0.05s ==========================
"""
    trace = _extract_surgical_traceback(sample_output)
    assert "AssertionError" in trace
    assert "assert 1 == 2" in trace
    assert "FAILED tests/test_demo.py::test_failure" in trace
