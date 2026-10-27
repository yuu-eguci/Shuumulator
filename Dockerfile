# syntax=docker/dockerfile:1

# NOTE: ローカル、CI、本番ジョブで同じ Python を使うため、パッチバージョンと digest まで固定します。
FROM python:3.14.10-slim@sha256:82abc9f53600280b0757126f83c5a7d47088592d2acb6b4c0b9e97f76865508c AS python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

# Pipfile.lock からハッシュ付きの requirements を書き出します。
# NOTE: pipenv はこのステージでしか使いません。最終イメージには入りません。
FROM python AS lock
RUN python -m venv /opt/pipenv && /opt/pipenv/bin/pip install pipenv==2026.10.3
WORKDIR /src
COPY Pipfile Pipfile.lock ./
# NOTE: Pipfile と Pipfile.lock がずれていたらここで失敗します。
RUN /opt/pipenv/bin/pipenv verify \
    && /opt/pipenv/bin/pipenv requirements --hash > requirements.txt \
    && /opt/pipenv/bin/pipenv requirements --hash --dev > requirements-dev.txt

FROM python AS app-deps
COPY --from=lock /src/requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --require-hashes --no-deps -r /tmp/requirements.txt

FROM python AS dev-deps
COPY --from=lock /src/requirements-dev.txt /tmp/requirements-dev.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --require-hashes --no-deps -r /tmp/requirements-dev.txt

# 本番ジョブ用です。 --execute を付けない限り何もしません。
FROM python AS app
COPY --from=app-deps /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
RUN useradd --create-home --uid 10001 shuumulator
WORKDIR /app
COPY consts.py utils.py functions.py main.py main_2_aggregation.py execute_main_if_market_is_open.py ./
COPY data ./data
USER shuumulator
CMD ["python", "main.py", "--help"]

# lint、テスト、依存監査用です。ソースは compose で読み取り専用マウントします。
FROM python AS dev
COPY --from=dev-deps /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    RUFF_NO_CACHE=true
RUN useradd --create-home --uid 10001 shuumulator
WORKDIR /app
USER shuumulator
CMD ["sh", "-c", "ruff check . && pytest"]
