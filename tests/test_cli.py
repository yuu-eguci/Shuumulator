import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ['main.py', 'execute_main_if_market_is_open.py', 'main_2_aggregation.py']


def run_script(script, *args, cwd, env=None):
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith(('MYSQL_', 'SHUUMULATOR_'))}
    clean_env.update(env or {})
    return subprocess.run(
        [sys.executable, str(ROOT / script), *args],
        cwd=cwd, env=clean_env, capture_output=True, text=True, timeout=60, check=False)


@pytest.mark.parametrize('script', SCRIPTS)
def test_refuses_to_run_without_execute(script, tmp_path):
    result = run_script(script, cwd=tmp_path)

    assert result.returncode == 2
    assert '--execute' in result.stderr
    assert result.stdout == ''


@pytest.mark.parametrize('script', SCRIPTS)
def test_help_is_safe(script, tmp_path):
    result = run_script(script, '--help', cwd=tmp_path)

    assert result.returncode == 0
    assert '--execute' in result.stdout


@pytest.mark.parametrize('script', SCRIPTS)
def test_missing_config_fails_without_leaking_values(script, tmp_path):
    result = run_script(script, '--execute', cwd=tmp_path, env={'MYSQL_PASSWORD': 'pw-sentinel'})

    assert result.returncode == 2
    assert 'MYSQL_HOST' in result.stderr
    assert 'pw-sentinel' not in result.stdout + result.stderr


@pytest.mark.parametrize('script', SCRIPTS)
def test_execute_reads_dotenv_from_working_directory(script, tmp_path):
    (tmp_path / '.env').write_text(
        "MYSQL_HOST='db.test'\nMYSQL_USER='u'\nMYSQL_PASSWORD='pw-sentinel'\n"
        "MYSQL_DATABASE='d'\nMYSQL_TLS='true'\n", encoding='utf-8')

    result = run_script(script, '--execute', cwd=tmp_path)

    # NOTE: .env を読んだうえで、 TLS の CA が無いので接続前に止まること。
    assert result.returncode == 2
    assert 'MYSQL_SSL_CA' in result.stderr
    assert 'pw-sentinel' not in result.stdout + result.stderr


@pytest.mark.parametrize('script', SCRIPTS)
def test_execute_ignores_dotenv_in_parent_directory(script, tmp_path):
    (tmp_path / '.env').write_text("MYSQL_HOST='db.test'\n", encoding='utf-8')
    child = tmp_path / 'child'
    child.mkdir()

    result = run_script(script, '--execute', cwd=child)

    # NOTE: 親ディレクトリの .env は読まないので、 MYSQL_HOST が無いと言われること。
    assert result.returncode == 2
    assert 'MYSQL_HOST' in result.stderr


@pytest.mark.parametrize('script', SCRIPTS)
def test_environment_takes_precedence_over_dotenv(script, tmp_path):
    (tmp_path / '.env').write_text(
        "MYSQL_HOST='unreachable.invalid'\nMYSQL_USER='u'\nMYSQL_PASSWORD='pw-sentinel'\n"
        "MYSQL_DATABASE='d'\nMYSQL_TLS='true'\n", encoding='utf-8')

    result = run_script(script, '--execute', cwd=tmp_path, env={'MYSQL_TLS': 'false'})

    # NOTE: 環境変数の MYSQL_TLS=false が勝つので、 CA が無いという設定エラーにはならないこと。
    #       接続先は存在しないホストなので、 DB の読み込みに失敗して 1 (市場が閉まっていれば 0) です。
    assert result.returncode in (0, 1)
    assert 'MYSQL_SSL_CA' not in result.stderr
    assert 'Traceback' not in result.stderr
    assert 'pw-sentinel' not in result.stdout + result.stderr


def test_consts_does_not_print_credentials(tmp_path):
    result = run_script('consts.py', cwd=tmp_path, env={'MYSQL_PASSWORD': 'pw-sentinel'})

    assert result.returncode == 0
    assert result.stdout + result.stderr == ''
