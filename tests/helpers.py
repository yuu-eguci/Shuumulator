"""テスト用の小物です。"""


class FakeResponse:
    def __init__(self, status_code=200, text=''):
        self.status_code = status_code
        self.text = text


class FakeSession:
    """requests.Session の代わりです。 URL ごとに決めたレスポンスを返します。"""

    def __init__(self, pages=None, error=None):
        self.pages = pages or {}
        self.error = error
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append((url, timeout))
        if self.error:
            raise self.error
        return self.pages.get(url, FakeResponse(404, 'not found'))
