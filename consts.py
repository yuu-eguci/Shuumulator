"""Shuumulator の定数と設定です。
NOTE: import しただけでは環境変数を読みません。DB 接続情報は load_settings() で取得します。
"""

# Built-in modules.
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

# 利確ラインです。
# NOTE: Decimal にするので文字列で定義します。
PROFIT_BOOKING_RATE = '0.025'


class ConfigError(Exception):
    """設定が足りない、あるいは値がおかしいときのエラーです。
    NOTE: メッセージには変数名だけを入れ、値は入れません。
    """


@dataclass(frozen=True)
class Settings:
    """実行に必要な設定です。"""

    mysql_host: str
    mysql_port: int
    mysql_user: str
    # NOTE: ログなどに出てしまわないよう repr から外します。
    mysql_password: str = field(repr=False)
    mysql_database: str
    mysql_tls: bool
    mysql_ssl_ca: str | None
    mysql_ssl_verify_identity: bool
    user_id: int


def get_env(environ: Mapping[str, str], keyname: str) -> str:
    """必須の環境変数を取得します。
    空文字列も未設定として扱います。
    """

    value = environ.get(keyname, '')
    if not value:
        raise ConfigError(f'{keyname} が設定されていません。')
    return value


def get_bool(environ: Mapping[str, str], keyname: str, default: bool) -> bool:
    """true/false の環境変数を取得します。ほかの値はエラーにします。"""

    value = environ.get(keyname, '')
    if not value:
        return default
    if value.lower() not in ('true', 'false'):
        raise ConfigError(f'{keyname} は true か false にしてください。')
    return value.lower() == 'true'


def get_positive_int(environ: Mapping[str, str], keyname: str, default: int) -> int:
    """正の整数の環境変数を取得します。"""

    value = environ.get(keyname, '')
    if not value:
        return default
    if not value.isdecimal() or int(value) <= 0:
        raise ConfigError(f'{keyname} は正の整数にしてください。')
    return int(value)


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """環境変数から設定を読みます。

    Args:
        environ (Mapping[str, str], optional): 省略時は os.environ。

    Raises:
        ConfigError: 設定が足りない、あるいは値がおかしい。

    Returns:
        Settings: 設定。
    """

    if environ is None:
        environ = os.environ

    # NOTE: 必須の値から順に確認します。
    mysql_host = get_env(environ, 'MYSQL_HOST')
    mysql_user = get_env(environ, 'MYSQL_USER')
    mysql_password = get_env(environ, 'MYSQL_PASSWORD')
    mysql_database = get_env(environ, 'MYSQL_DATABASE')
    mysql_port = get_positive_int(environ, 'MYSQL_PORT', default=3306)
    if mysql_port > 65535:
        raise ConfigError('MYSQL_PORT は 65535 以下にしてください。')

    mysql_tls = get_bool(environ, 'MYSQL_TLS', default=True)
    mysql_ssl_ca = environ.get('MYSQL_SSL_CA') or None
    # NOTE: TLS を使うなら証明書を必ず検証します。 CA が無いまま接続はしません。
    if mysql_tls:
        if not mysql_ssl_ca:
            raise ConfigError('MYSQL_TLS が true のときは MYSQL_SSL_CA が必要です。')
        if not Path(mysql_ssl_ca).is_file():
            raise ConfigError('MYSQL_SSL_CA のファイルが見つかりません。')

    return Settings(
        mysql_host=mysql_host,
        mysql_port=mysql_port,
        mysql_user=mysql_user,
        mysql_password=mysql_password,
        mysql_database=mysql_database,
        mysql_tls=mysql_tls,
        mysql_ssl_ca=mysql_ssl_ca,
        mysql_ssl_verify_identity=get_bool(environ, 'MYSQL_SSL_VERIFY_IDENTITY', default=True),
        user_id=get_positive_int(environ, 'SHUUMULATOR_USER_ID', default=1),
    )
