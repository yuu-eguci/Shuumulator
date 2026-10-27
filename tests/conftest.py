import os

import pytest
import requests


@pytest.fixture(autouse=True)
def _block_real_http(monkeypatch):
    """テスト中に本物の HTTP リクエストを送らないようにします。"""

    def refuse(*args, **kwargs):
        raise AssertionError('テスト中に本物の HTTP リクエストを送ろうとしました。')

    monkeypatch.setattr(requests.Session, 'request', refuse)
    monkeypatch.setattr(requests.adapters.HTTPAdapter, 'send', refuse)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """開発者の環境変数をテストに持ち込まないようにします。"""

    for name in list(os.environ):
        if name.startswith(('MYSQL_', 'SHUUMULATOR_')) and not name.startswith('MYSQL_TEST_'):
            monkeypatch.delenv(name)

