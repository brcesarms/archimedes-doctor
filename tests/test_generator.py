"""
Testes unitários para o módulo generator do Archimedes Doctor.
Cobrem: find_opencode_binary, generate_tests_for_file e request_healing_fix.
"""

from pathlib import Path
from unittest import mock

from src import generator
from src.generator import (
    find_opencode_binary,
    generate_tests_for_file,
    request_healing_fix,
)


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    source_file = repo / "src" / "math_ops.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )
    test_file = repo / "tests" / "test_math_ops.py"
    return source_file, test_file, repo


# ---------------------------------------------------------------- find_opencode_binary

def test_find_opencode_binary_prefers_path_resolved_by_which():
    with mock.patch("src.generator.shutil.which", return_value="/usr/bin/opencode"):
        result = find_opencode_binary()

    assert result == "/usr/bin/opencode"


def test_find_opencode_binary_returns_string_when_which_succeeds():
    with mock.patch("src.generator.shutil.which", return_value="/usr/bin/opencode"):
        result = find_opencode_binary()

    assert isinstance(result, str)
    assert result


def test_find_opencode_binary_uses_home_opencode_bin(tmp_path):
    candidate = tmp_path / ".opencode" / "bin" / "opencode"
    candidate.parent.mkdir(parents=True)
    candidate.touch()

    with mock.patch("src.generator.shutil.which", return_value=None), \
         mock.patch.object(Path, "home", return_value=tmp_path), \
         mock.patch("src.generator.os.access", return_value=True):
        result = find_opencode_binary()

    assert result == str(candidate)


def test_find_opencode_binary_returns_first_executable_candidate(tmp_path):
    home_candidate = tmp_path / ".opencode" / "bin" / "opencode"
    local_candidate = tmp_path / ".local" / "bin" / "opencode"
    home_candidate.parent.mkdir(parents=True)
    home_candidate.touch()
    local_candidate.parent.mkdir(parents=True)
    local_candidate.touch()

    with mock.patch("src.generator.shutil.which", return_value=None), \
         mock.patch.object(Path, "home", return_value=tmp_path), \
         mock.patch("src.generator.os.access", return_value=True):
        result = find_opencode_binary()

    assert result == str(home_candidate)


def test_find_opencode_binary_skips_missing_and_picks_existing(tmp_path):
    local_candidate = tmp_path / ".local" / "bin" / "opencode"
    local_candidate.parent.mkdir(parents=True)
    local_candidate.touch()

    with mock.patch("src.generator.shutil.which", return_value=None), \
         mock.patch.object(Path, "home", return_value=tmp_path), \
         mock.patch("src.generator.os.access", return_value=True):
        result = find_opencode_binary()

    assert result == str(local_candidate)


def test_find_opencode_binary_skips_candidate_when_not_executable(tmp_path):
    home_candidate = tmp_path / ".opencode" / "bin" / "opencode"
    home_candidate.parent.mkdir(parents=True)
    home_candidate.touch()

    with mock.patch("src.generator.shutil.which", return_value=None), \
         mock.patch.object(Path, "home", return_value=tmp_path), \
         mock.patch("src.generator.os.access", return_value=False):
        result = find_opencode_binary()

    assert result == "opencode"


def test_find_opencode_binary_fallback_when_nothing_found(tmp_path):
    with mock.patch("src.generator.shutil.which", return_value=None), \
         mock.patch.object(Path, "home", return_value=tmp_path), \
         mock.patch("src.generator.os.access", return_value=False):
        result = find_opencode_binary()

    assert result == "opencode"


# ---------------------------------------------------------------- generate_tests_for_file

def test_generate_tests_success_returns_true_when_file_created(tmp_path):
    source_file, test_file, repo = _make_repo(tmp_path)

    def _fake_run(cmd, cwd, check):
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.touch()
        return mock.Mock()

    with mock.patch(
        "src.generator.find_opencode_binary", return_value="/custom/opencode",
    ), mock.patch(
        "src.generator.subprocess.run", side_effect=_fake_run,
    ) as run_mock:
        result = generate_tests_for_file(
            source_file, test_file, repo, ["add"], model="test-model",
        )

    assert result is True
    assert run_mock.call_count == 1
    args, kwargs = run_mock.call_args
    cmd = args[0]
    assert cmd[0] == "/custom/opencode"
    assert cmd[1] == "run"
    assert "-m" in cmd
    assert cmd[cmd.index("-m") + 1] == "test-model"
    assert kwargs["cwd"] == repo
    assert kwargs["check"] is True


def test_generate_tests_prompt_contains_paths_functions_and_source(tmp_path):
    source_file, test_file, repo = _make_repo(tmp_path)

    with mock.patch(
        "src.generator.find_opencode_binary", return_value="/custom/opencode",
    ), mock.patch(
        "src.generator.subprocess.run", return_value=mock.Mock(),
    ) as run_mock:
        generate_tests_for_file(source_file, test_file, repo, ["add", "subtract"])

    prompt = run_mock.call_args.args[0][-1]
    assert "tests/test_math_ops.py" in prompt
    assert "src/math_ops.py" in prompt
    assert "add, subtract" in prompt
    assert "def add(a, b):" in prompt


def test_generate_tests_prompt_uses_default_targets_when_empty_list(tmp_path):
    source_file, test_file, repo = _make_repo(tmp_path)

    with mock.patch(
        "src.generator.subprocess.run", return_value=mock.Mock(),
    ) as run_mock:
        generate_tests_for_file(source_file, test_file, repo, [])

    prompt = run_mock.call_args.args[0][-1]
    assert "todas as funções e classes principais" in prompt


def test_generate_tests_uses_relative_paths_for_nested_source(tmp_path):
    repo = tmp_path / "repo"
    source_file = repo / "packages" / "core" / "api.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("def ping():\n    return 'pong'\n", encoding="utf-8")
    test_file = repo / "tests" / "test_api.py"

    with mock.patch(
        "src.generator.subprocess.run", return_value=mock.Mock(),
    ) as run_mock:
        generate_tests_for_file(source_file, test_file, repo, ["ping"])

    prompt = run_mock.call_args.args[0][-1]
    assert "packages/core/api.py" in prompt
    assert "tests/test_api.py" in prompt


def test_generate_tests_omits_model_flag_when_model_none(tmp_path):
    source_file, test_file, repo = _make_repo(tmp_path)

    with mock.patch(
        "src.generator.find_opencode_binary", return_value="opencode",
    ), mock.patch(
        "src.generator.subprocess.run", return_value=mock.Mock(),
    ) as run_mock:
        generate_tests_for_file(source_file, test_file, repo, ["add"])

    cmd = run_mock.call_args.args[0]
    assert cmd[0] == "opencode"
    assert cmd[1] == "run"
    assert "-m" not in cmd


def test_generate_tests_returns_false_when_file_not_created(tmp_path):
    source_file, test_file, repo = _make_repo(tmp_path)

    with mock.patch(
        "src.generator.subprocess.run", return_value=mock.Mock(),
    ):
        result = generate_tests_for_file(source_file, test_file, repo, ["add"])

    assert result is False
    assert not test_file.is_file()


def test_generate_tests_returns_false_on_subprocess_error(tmp_path):
    source_file, test_file, repo = _make_repo(tmp_path)

    with mock.patch(
        "src.generator.subprocess.run", side_effect=FileNotFoundError("opencode"),
    ):
        result = generate_tests_for_file(source_file, test_file, repo, ["add"])

    assert result is False


def test_generate_tests_returns_false_on_non_zero_exit(tmp_path):
    source_file, test_file, repo = _make_repo(tmp_path)

    with mock.patch(
        "src.generator.subprocess.run",
        side_effect=Exception("exit code 1"),
    ):
        result = generate_tests_for_file(source_file, test_file, repo, ["add"])

    assert result is False


# ---------------------------------------------------------------- request_healing_fix

def test_healing_fix_success_returns_true(tmp_path):
    source_file, test_file, repo = _make_repo(tmp_path)
    traceback = "assert 1 == 2"

    with mock.patch(
        "src.generator.find_opencode_binary", return_value="/custom/opencode",
    ), mock.patch(
        "src.generator.subprocess.run", return_value=mock.Mock(),
    ) as run_mock:
        result = request_healing_fix(
            source_file, test_file, repo,
            traceback_snippet=traceback,
            iteration=2,
            max_iterations=5,
            model="test-model",
        )

    assert result is True
    args, kwargs = run_mock.call_args
    cmd = args[0]
    assert cmd[0] == "/custom/opencode"
    assert cmd[1] == "run"
    assert "-m" in cmd
    assert cmd[cmd.index("-m") + 1] == "test-model"
    assert kwargs["cwd"] == repo
    assert kwargs["check"] is True


def test_healing_fix_prompt_contains_traceback_and_iteration(tmp_path):
    source_file, test_file, repo = _make_repo(tmp_path)

    with mock.patch(
        "src.generator.subprocess.run", return_value=mock.Mock(),
    ) as run_mock:
        request_healing_fix(
            source_file, test_file, repo,
            traceback_snippet="ZeroDivisionError: division by zero",
            iteration=1,
            max_iterations=3,
        )

    prompt = run_mock.call_args.args[0][-1]
    assert "1/3" in prompt
    assert "ZeroDivisionError: division by zero" in prompt
    assert "tests/test_math_ops.py" in prompt
    assert "src/math_ops.py" in prompt


def test_healing_fix_prompt_contains_healing_instructions(tmp_path):
    source_file, test_file, repo = _make_repo(tmp_path)

    with mock.patch(
        "src.generator.subprocess.run", return_value=mock.Mock(),
    ) as run_mock:
        request_healing_fix(
            source_file, test_file, repo, traceback_snippet="boom",
            iteration=1, max_iterations=1,
        )

    prompt = run_mock.call_args.args[0][-1]
    assert "INSTRUÇÃO DE CURA" in prompt
    assert "STACK TRACE DA FALHA" in prompt


def test_healing_fix_omits_model_flag_when_model_none(tmp_path):
    source_file, test_file, repo = _make_repo(tmp_path)

    with mock.patch(
        "src.generator.find_opencode_binary", return_value="opencode",
    ), mock.patch(
        "src.generator.subprocess.run", return_value=mock.Mock(),
    ) as run_mock:
        request_healing_fix(
            source_file, test_file, repo, traceback_snippet="boom",
            iteration=1, max_iterations=3,
        )

    cmd = run_mock.call_args.args[0]
    assert cmd[0] == "opencode"
    assert "-m" not in cmd


def test_healing_fix_returns_false_on_subprocess_error(tmp_path):
    source_file, test_file, repo = _make_repo(tmp_path)

    with mock.patch(
        "src.generator.subprocess.run", side_effect=OSError("fork failed"),
    ):
        result = request_healing_fix(
            source_file, test_file, repo, traceback_snippet="boom",
            iteration=1, max_iterations=3,
        )

    assert result is False


def test_fetch_rag_context_returns_empty_when_rag_not_found(tmp_path):
    from src.generator import fetch_rag_context_for_error
    with mock.patch("src.generator.shutil.which", return_value=None):
        ctx = fetch_rag_context_for_error("ZeroDivisionError: division by zero", tmp_path)
    assert ctx == ""


def test_fetch_rag_context_success(tmp_path):
    from src.generator import fetch_rag_context_for_error
    mock_out = (
        "Considere as seguintes referências técnicas locais:\n"
        "--- [Fonte: math.py] ---\ndef add(a, b):\n\n"
        "--- TAREFA SOLICITADA ---\n"
    )
    mock_res = mock.Mock(returncode=0, stdout=mock_out)
    with mock.patch("src.generator.shutil.which", return_value="/bin/rag"), \
         mock.patch("src.generator.subprocess.run", return_value=mock_res):
        ctx = fetch_rag_context_for_error("AssertionError: 1 != 2", tmp_path)

    assert "--- [Fonte: math.py] ---" in ctx


def test_healing_fix_injects_rag_block_when_rag_returns_context(tmp_path):
    source_file, test_file, repo = _make_repo(tmp_path)

    with mock.patch(
        "src.generator.fetch_rag_context_for_error",
        return_value="--- [Fonte: math.py] ---",
    ), mock.patch(
        "src.generator.subprocess.run", return_value=mock.Mock(),
    ) as run_mock:
        request_healing_fix(
            source_file, test_file, repo,
            traceback_snippet="NameError: name 'foo' is not defined",
            iteration=1,
            max_iterations=3,
        )

    prompt = run_mock.call_args.args[0][-1]
    assert "--- CONTEXTO DO PROJETO (recuperado via Archimedes RAG) ---" in prompt
    assert "--- [Fonte: math.py] ---" in prompt