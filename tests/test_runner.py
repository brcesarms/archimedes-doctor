"""
Testes unitários para o módulo runner do Archimedes Doctor.
Cobrem exclusivamente: find_python_and_pytest e run_pytest_isolated.
"""

import subprocess
from pathlib import Path
from unittest import mock

from src import runner
from src.runner import find_python_and_pytest, run_pytest_isolated


# ---------------------------------------------------------------- find_python_and_pytest

def test_find_uses_venv_when_pytest_exists_and_executable(tmp_path):
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "pytest").touch()
    (venv_bin / "python").touch()

    with mock.patch("src.runner.os.access", return_value=True), \
         mock.patch("src.runner.shutil.which", return_value=None) as which_mock:
        python_bin, pytest_bin = find_python_and_pytest(tmp_path)

    assert python_bin == str(tmp_path / ".venv" / "bin" / "python")
    assert pytest_bin == str(tmp_path / ".venv" / "bin" / "pytest")
    which_mock.assert_not_called()


def test_find_falls_back_to_path_when_venv_pytest_not_executable(tmp_path):
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "pytest").touch()

    with mock.patch("src.runner.os.access", return_value=False), \
         mock.patch(
            "src.runner.shutil.which",
            side_effect=["/usr/bin/pytest", "/usr/bin/python3"],
         ):
        python_bin, pytest_bin = find_python_and_pytest(tmp_path)

    assert python_bin == "/usr/bin/python3"
    assert pytest_bin == "/usr/bin/pytest"


def test_find_uses_path_when_no_venv(tmp_path):
    with mock.patch(
        "src.runner.shutil.which",
        side_effect=["/usr/bin/pytest", "/usr/bin/python3"],
    ):
        python_bin, pytest_bin = find_python_and_pytest(tmp_path)

    assert python_bin == "/usr/bin/python3"
    assert pytest_bin == "/usr/bin/pytest"


def test_find_fallback_defaults_when_pytest_missing_on_path(tmp_path):
    with mock.patch("src.runner.shutil.which", return_value=None):
        python_bin, pytest_bin = find_python_and_pytest(tmp_path)

    assert python_bin == "python"
    assert pytest_bin == "pytest"


def test_find_returns_two_strings(tmp_path):
    python_bin, pytest_bin = find_python_and_pytest(tmp_path)

    assert isinstance(python_bin, str)
    assert isinstance(pytest_bin, str)
    assert isinstance(python_bin and pytest_bin, str)


# ---------------------------------------------------------------- run_pytest_isolated: roteamento

def test_run_local_when_docker_not_requested(tmp_path):
    test_file = tmp_path / "tests" / "test_x.py"
    test_file.parent.mkdir(parents=True)
    test_file.touch()

    with mock.patch.object(
        runner, "_run_local_sandbox", return_value={"passed": True, "mode": "local_sandbox"},
    ) as local_mock, \
         mock.patch.object(runner, "_run_in_docker") as docker_mock:
        result = run_pytest_isolated(test_file, tmp_path, timeout_seconds=10)

    local_mock.assert_called_once_with(test_file, tmp_path, 10)
    docker_mock.assert_not_called()
    assert result == {"passed": True, "mode": "local_sandbox"}


def test_run_docker_when_requested_and_docker_available(tmp_path):
    test_file = tmp_path / "tests" / "test_x.py"
    test_file.parent.mkdir(parents=True)
    test_file.touch()
    docker_result = {"passed": False, "returncode": 2, "mode": "docker"}

    with mock.patch("src.runner.shutil.which", return_value="/usr/bin/docker"), \
         mock.patch.object(runner, "_run_in_docker", return_value=docker_result) as docker_mock, \
         mock.patch.object(runner, "_run_local_sandbox") as local_mock:
        result = run_pytest_isolated(test_file, tmp_path, timeout_seconds=30, use_docker=True)

    docker_mock.assert_called_once_with(test_file, tmp_path, 30)
    local_mock.assert_not_called()
    assert result == docker_result


def test_run_falls_back_to_local_when_docker_requested_but_missing(tmp_path):
    test_file = tmp_path / "tests" / "test_x.py"
    test_file.parent.mkdir(parents=True)
    test_file.touch()

    with mock.patch("src.runner.shutil.which", return_value=None), \
         mock.patch.object(runner, "_run_in_docker") as docker_mock, \
         mock.patch.object(
            runner,
            "_run_local_sandbox",
            return_value={"passed": True, "mode": "local_sandbox"},
         ) as local_mock:
        result = run_pytest_isolated(test_file, tmp_path, timeout_seconds=30, use_docker=True)

    docker_mock.assert_not_called()
    local_mock.assert_called_once()
    assert result["mode"] == "local_sandbox"


# ---------------------------------------------------------------- run_pytest_isolated: execução local (subprocess)

def test_run_pytest_isolated_success_local(tmp_path):
    fake_res = subprocess.CompletedProcess([], returncode=0, stdout="1 passed\n", stderr="")

    with mock.patch(
        "src.runner.find_python_and_pytest", return_value=("/venv/bin/python", "/venv/bin/pytest"),
    ), mock.patch("src.runner.subprocess.run", return_value=fake_res) as run_mock:
        result = run_pytest_isolated(tmp_path / "test_x.py", tmp_path, timeout_seconds=5)

    args, kwargs = run_mock.call_args
    assert result["passed"] is True
    assert result["returncode"] == 0
    assert result["stdout"] == "1 passed\n"
    assert result["mode"] == "local_sandbox"
    assert result["traceback"] == ""
    assert kwargs["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert str(tmp_path) in kwargs["env"]["PYTHONPATH"]
    assert kwargs["timeout"] == 5
    assert args[0][0] == "/venv/bin/pytest"


def test_run_pytest_isolated_failure_local(tmp_path):
    output = (
        "tests/test_x.py F                                        [100%]\n"
        "============================ FAILURES =============================\n"
        "__________________________ test_failure __________________________\n"
        "    def test_failure():\n"
        ">       assert 1 == 2\n"
        "E       assert 1 == 2\n"
        "========================= short test summary info =================\n"
        "FAILED tests/test_x.py::test_failure - assert 1 == 2\n"
    )
    fake_res = subprocess.CompletedProcess([], returncode=1, stdout=output, stderr="")

    with mock.patch(
        "src.runner.find_python_and_pytest", return_value=("python", "pytest"),
    ), mock.patch("src.runner.subprocess.run", return_value=fake_res):
        result = run_pytest_isolated(tmp_path / "test_x.py", tmp_path, timeout_seconds=5)

    assert result["passed"] is False
    assert result["returncode"] == 1
    assert result["mode"] == "local_sandbox"
    assert "assert 1 == 2" in result["traceback"]
    assert "FAILED tests/test_x.py::test_failure" in result["traceback"]


def test_run_pytest_isolated_timeout(tmp_path):
    with mock.patch(
        "src.runner.find_python_and_pytest", return_value=("python", "pytest"),
    ), mock.patch(
        "src.runner.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["pytest"], timeout=5),
    ):
        result = run_pytest_isolated(tmp_path / "test_x.py", tmp_path, timeout_seconds=5)

    assert result["passed"] is False
    assert result["returncode"] == -1
    assert result["mode"] == "local_sandbox"
    assert "Timeout" in result["stderr"]
    assert "TimeoutExpired" in result["traceback"]


def test_run_pytest_isolated_unexpected_error(tmp_path):
    with mock.patch(
        "src.runner.find_python_and_pytest", return_value=("python", "pytest"),
    ), mock.patch("src.runner.subprocess.run", side_effect=OSError("boom")):
        result = run_pytest_isolated(tmp_path / "test_x.py", tmp_path, timeout_seconds=5)

    assert result["passed"] is False
    assert result["returncode"] == 1
    assert result["mode"] == "local_sandbox"
    assert "boom" in result["stderr"]
    assert "boom" in result["traceback"]