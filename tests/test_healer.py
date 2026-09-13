"""
Testes unitários para o módulo healer do Archimedes Doctor.
Cobrem exclusivamente: heal_file_tests (orquestrador do ciclo de Auto-Cura).
"""

import sys
from pathlib import Path
from unittest import mock

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import src.healer as healer
from src.healer import heal_file_tests

PASS_RESULT = {"passed": True, "traceback": ""}


def _fail_result(traceback="Traceback simulado"):
    return {"passed": False, "traceback": traceback, "stderr": "", "stdout": ""}


def _definitions(*names):
    return [{"type": "function", "name": name, "lineno": "1"} for name in names]


# ---------------------------------------------------------------- falha na geração inicial

def test_heal_generation_failure_returns_failed(tmp_path):
    source_file = tmp_path / "src" / "math_ops.py"
    test_file = tmp_path / "tests" / "test_math_ops.py"

    with mock.patch.object(
        healer, "locate_or_propose_test_file", return_value=test_file,
    ), mock.patch.object(
        healer, "extract_functions_and_classes", return_value=_definitions("my_func"),
    ), mock.patch.object(
        healer, "get_existing_tests_in_file", return_value=set(),
    ), mock.patch.object(
        healer, "generate_tests_for_file", return_value=False,
    ) as gen_mock, mock.patch.object(healer, "run_pytest_isolated") as run_mock:
        result = heal_file_tests(source_file, tmp_path)

    assert result["status"] == "failed"
    assert result["iterations"] == 0
    assert result["source"] == str(source_file.resolve())
    assert result["test"] == str(test_file)
    assert "Falha ao gerar" in result["message"]
    gen_mock.assert_called_once()
    run_mock.assert_not_called()


def test_heal_generation_success_but_file_not_created_returns_failed(tmp_path):
    source_file = tmp_path / "src" / "math_ops.py"
    test_file = tmp_path / "tests" / "test_math_ops.py"

    with mock.patch.object(
        healer, "locate_or_propose_test_file", return_value=test_file,
    ), mock.patch.object(
        healer, "extract_functions_and_classes", return_value=_definitions("my_func"),
    ), mock.patch.object(
        healer, "get_existing_tests_in_file", return_value=set(),
    ), mock.patch.object(
        healer, "generate_tests_for_file", return_value=True,
    ), mock.patch.object(healer, "run_pytest_isolated") as run_mock:
        result = heal_file_tests(source_file, tmp_path)

    assert result["status"] == "failed"
    assert result["iterations"] == 0
    run_mock.assert_not_called()


# ---------------------------------------------------------------- sucesso na primeira rodada

def test_heal_first_attempt_passed(tmp_path):
    source_file = tmp_path / "src" / "math_ops.py"
    test_file = tmp_path / "tests" / "test_math_ops.py"
    test_file.parent.mkdir(parents=True)
    test_file.touch()

    with mock.patch.object(
        healer, "locate_or_propose_test_file", return_value=test_file,
    ), mock.patch.object(
        healer, "extract_functions_and_classes", return_value=_definitions("my_func"),
    ), mock.patch.object(
        healer, "get_existing_tests_in_file", return_value={"test_my_func"},
    ), mock.patch.object(
        healer, "generate_tests_for_file",
    ) as gen_mock, mock.patch.object(
        healer, "request_healing_fix",
    ) as fix_mock, mock.patch.object(
        healer, "run_pytest_isolated", return_value=PASS_RESULT,
    ) as run_mock:
        result = heal_file_tests(source_file, tmp_path)

    assert result["status"] == "passed"
    assert result["iterations"] == 1
    assert result["message"] == "Sucesso imediato sem necessidade de cura."
    gen_mock.assert_not_called()
    fix_mock.assert_not_called()
    run_mock.assert_called_once_with(test_file, tmp_path, use_docker=False)


# ---------------------------------------------------------------- loop de auto-cura

def test_heal_healed_on_second_iteration(tmp_path):
    source_file = tmp_path / "src" / "math_ops.py"
    test_file = tmp_path / "tests" / "test_math_ops.py"
    test_file.parent.mkdir(parents=True)
    test_file.touch()
    fail_run = _fail_result("assert 1 == 2")

    with mock.patch.object(
        healer, "locate_or_propose_test_file", return_value=test_file,
    ), mock.patch.object(
        healer, "extract_functions_and_classes", return_value=_definitions("my_func"),
    ), mock.patch.object(
        healer, "get_existing_tests_in_file", return_value={"test_my_func"},
    ), mock.patch.object(
        healer, "request_healing_fix", return_value=True,
    ) as fix_mock, mock.patch.object(
        healer, "run_pytest_isolated",
        side_effect=[fail_run, fail_run, PASS_RESULT],
    ) as run_mock:
        result = heal_file_tests(source_file, tmp_path, max_retries=3)

    assert result["status"] == "healed"
    assert result["iterations"] == 2
    assert result["message"] == "Curado com sucesso na iteração 2."
    assert run_mock.call_count == 3
    assert fix_mock.call_count == 2
    fix_mock.assert_any_call(
        source_file=source_file,
        test_file=test_file,
        repo_root=tmp_path,
        traceback_snippet="assert 1 == 2",
        iteration=1,
        max_iterations=3,
        model=None,
    )
    fix_mock.assert_any_call(
        source_file=source_file,
        test_file=test_file,
        repo_root=tmp_path,
        traceback_snippet="assert 1 == 2",
        iteration=2,
        max_iterations=3,
        model=None,
    )


def test_heal_unhealed_after_max_retries(tmp_path):
    source_file = tmp_path / "src" / "math_ops.py"
    test_file = tmp_path / "tests" / "test_math_ops.py"
    test_file.parent.mkdir(parents=True)
    test_file.touch()
    fail_run = _fail_result("ZeroDivisionError")

    with mock.patch.object(
        healer, "locate_or_propose_test_file", return_value=test_file,
    ), mock.patch.object(
        healer, "extract_functions_and_classes", return_value=_definitions("my_func"),
    ), mock.patch.object(
        healer, "get_existing_tests_in_file", return_value={"test_my_func"},
    ), mock.patch.object(
        healer, "request_healing_fix", return_value=True,
    ) as fix_mock, mock.patch.object(
        healer, "run_pytest_isolated", return_value=fail_run,
    ) as run_mock:
        result = heal_file_tests(source_file, tmp_path, max_retries=2)

    assert result["status"] == "unhealed"
    assert result["iterations"] == 2
    assert result["last_traceback"] == "ZeroDivisionError"
    assert "2 tentativas" in result["message"]
    assert run_mock.call_count == 3
    assert fix_mock.call_count == 2
    assert [c.kwargs["iteration"] for c in fix_mock.call_args_list] == [1, 2]
    assert all(c.kwargs["max_iterations"] == 2 for c in fix_mock.call_args_list)


def test_heal_loop_continues_when_fix_communication_fails(tmp_path):
    source_file = tmp_path / "src" / "math_ops.py"
    test_file = tmp_path / "tests" / "test_math_ops.py"
    test_file.parent.mkdir(parents=True)
    test_file.touch()
    fail_run = _fail_result("boom")

    with mock.patch.object(
        healer, "locate_or_propose_test_file", return_value=test_file,
    ), mock.patch.object(
        healer, "extract_functions_and_classes", return_value=_definitions("my_func"),
    ), mock.patch.object(
        healer, "get_existing_tests_in_file", return_value={"test_my_func"},
    ), mock.patch.object(
        healer, "request_healing_fix", return_value=False,
    ) as fix_mock, mock.patch.object(
        healer, "run_pytest_isolated", return_value=fail_run,
    ) as run_mock:
        result = heal_file_tests(source_file, tmp_path, max_retries=1)

    assert result["status"] == "unhealed"
    assert result["iterations"] == 1
    fix_mock.assert_called_once()
    assert run_mock.call_count == 2
    run_mock.assert_called_with(test_file, tmp_path, use_docker=False)


# ---------------------------------------------------------------- propagação de parâmetros

def test_heal_resolves_paths_before_calling_dependencies(tmp_path):
    repo = tmp_path / "repo"
    source_file = repo / "src" / ".." / "src" / "math_ops.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.touch()
    test_file = repo / "tests" / "test_math_ops.py"
    test_file.parent.mkdir(parents=True)
    test_file.touch()

    with mock.patch.object(
        healer, "locate_or_propose_test_file", return_value=test_file,
    ) as locate_mock, mock.patch.object(
        healer, "extract_functions_and_classes", return_value=_definitions("my_func"),
    ), mock.patch.object(
        healer, "get_existing_tests_in_file", return_value={"test_my_func"},
    ), mock.patch.object(
        healer, "run_pytest_isolated", return_value=PASS_RESULT,
    ):
        heal_file_tests(source_file, repo)

    resolved_source = source_file.resolve()
    resolved_repo = repo.resolve()
    assert locate_mock.call_args[0][0] == resolved_source
    assert locate_mock.call_args[0][1] == resolved_repo


def test_heal_propagates_docker_flag(tmp_path):
    source_file = tmp_path / "src" / "math_ops.py"
    test_file = tmp_path / "tests" / "test_math_ops.py"
    test_file.parent.mkdir(parents=True)
    test_file.touch()

    with mock.patch.object(
        healer, "locate_or_propose_test_file", return_value=test_file,
    ), mock.patch.object(
        healer, "extract_functions_and_classes", return_value=_definitions("my_func"),
    ), mock.patch.object(
        healer, "get_existing_tests_in_file", return_value={"test_my_func"},
    ), mock.patch.object(
        healer, "run_pytest_isolated", return_value=PASS_RESULT,
    ) as run_mock:
        result = heal_file_tests(source_file, tmp_path, use_docker=True)

    assert result["status"] == "passed"
    run_mock.assert_called_once_with(test_file, tmp_path, use_docker=True)


def test_heal_propagates_model_to_generator(tmp_path):
    source_file = tmp_path / "src" / "math_ops.py"
    test_file = tmp_path / "tests" / "test_math_ops.py"

    with mock.patch.object(
        healer, "locate_or_propose_test_file", return_value=test_file,
    ), mock.patch.object(
        healer, "extract_functions_and_classes", return_value=_definitions("my_func"),
    ), mock.patch.object(
        healer, "get_existing_tests_in_file", return_value=set(),
    ), mock.patch.object(
        healer, "generate_tests_for_file", return_value=True,
    ) as gen_mock, mock.patch.object(
        healer, "run_pytest_isolated", return_value=PASS_RESULT,
    ):
        heal_file_tests(source_file, tmp_path, model="gpt-test")

    gen_mock.assert_called_once_with(
        source_file, test_file, tmp_path, ["my_func"], model="gpt-test",
    )


# ---------------------------------------------------------------- integração com scanner real

def test_heal_full_success_with_real_scanner(tmp_path):
    repo = tmp_path / "repo"
    src_dir = repo / "src"
    src_dir.mkdir(parents=True)
    source_file = src_dir / "math_ops.py"
    source_file.write_text(
        "def my_func():\n    return 42\n",
        encoding="utf-8",
    )
    test_file = repo / "tests" / "test_math_ops.py"

    def fake_generate(src, tst, root, funcs, model=None):
        tst.parent.mkdir(parents=True, exist_ok=True)
        tst.write_text("def test_my_func():\n    assert my_func() == 42\n", encoding="utf-8")
        return tst.is_file()

    with mock.patch.object(
        healer, "generate_tests_for_file", side_effect=fake_generate,
    ), mock.patch.object(
        healer, "run_pytest_isolated", return_value=PASS_RESULT,
    ) as run_mock:
        result = heal_file_tests(source_file, repo)

    assert result["status"] == "passed"
    assert result["iterations"] == 1
    assert Path(result["test"]) == test_file
    assert test_file.is_file()
    assert "def test_my_func" in test_file.read_text(encoding="utf-8")
    run_mock.assert_called_once_with(test_file, repo, use_docker=False)