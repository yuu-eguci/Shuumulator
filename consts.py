"""
Python やるときにいつもあって欲しい自分用モジュールです。
"""

# Built-in modules.
import os
import dotenv


# .env をロードします。
# 本スクリプトは .env がなくても動きます。(そのための raise_error_if_not_found です。)
# NOTE: raise_error_if_not_found=False .env が見つからなくてもエラーを起こさない。
dotenv.load_dotenv(dotenv.find_dotenv(raise_error_if_not_found=False))


def get_env(keyname: str) -> str:
    """環境変数を取得します。
    GitHub Actions では環境変数が設定されていなくても yaml 内で空文字列が入ってしまう。空欄チェックも行います。

    Arguments:
        keyname {str} -- 環境変数名。

    Raises:
        KeyError: 環境変数が見つからない。

    Returns:
        str -- 環境変数の値。
    """
    _ = os.environ[keyname]
    if not _:
        raise KeyError(f'{keyname} is empty.')
    return _


MYSQL_HOST = get_env('MYSQL_HOST')
MYSQL_USER = get_env('MYSQL_USER')
MYSQL_PASSWORD = get_env('MYSQL_PASSWORD')
MYSQL_DATABASE = get_env('MYSQL_DATABASE')
SLACK_BOT_TOKEN = get_env('SLACK_BOT_TOKEN')
SLACK_MESSAGE_CHANNEL = get_env('SLACK_MESSAGE_CHANNEL')

# 利確ラインです。
# NOTE: Decimal にするので文字列で定義します。
PROFIT_BOOKING_RATE = '0.025'

if __name__ == '__main__':
    print(repr(MYSQL_HOST))
    print(repr(MYSQL_USER))
    print(repr(MYSQL_PASSWORD))
    print(repr(MYSQL_DATABASE))
