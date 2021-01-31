"""
Python やるときにいつもあって欲しい自分用モジュールです。
これは使いまわしたいのでリポジトリのビジネスロジック入れないでね。
NOTE: DbClient 内なら OK。
以下、できること。

# Dependencies
pipenv install python-dotenv mysql-connector-python

# MySQL への接続。
with utils.DbClient() as db_client:
    records = db_client.sample_select()

# logger の取得。
logger = utils.get_my_logger(__name__)

# Slack メッセージの送信。
utils.send_slack_message(message)
"""

# Built-in modules.
import logging
import datetime

# Third-party modules.
import mysql.connector
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import pytz

# User modules.
import consts


class DbClient:
    """DB アクセスを行うクラスです。 with 構文で使用可能です。
    with utils.DbClient() as db_client:
        records = db_client.sample_select()
    """

    def __enter__(self):
        mysql_connection_config = {
            'host': consts.MYSQL_HOST,
            'user': consts.MYSQL_USER,
            'password': consts.MYSQL_PASSWORD,
            'database': consts.MYSQL_DATABASE,
        }
        self.connection = mysql.connector.connect(**mysql_connection_config)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.connection.close()

    def sample_select(self) -> list:
        """サンプルです。

        Returns:
            list: Select 結果のリスト。
        """

        select_sql = ' '.join([
            'SELECT',
                'id',  # noqa: E131
            'FROM sampletable',
            'WHERE',
                'id = %s',
            'ORDER BY id DESC',
        ])
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(select_sql, (1,))
        records = cursor.fetchall()
        cursor.close()
        return records

    def sample_update(self):
        """サンプルです。
        """

        update_sql = ' '.join([
            'UPDATE sampletable',
            'SET',
                'foo = %s',  # noqa: E131
            'WHERE id = %s',
        ])
        cursor = self.connection.cursor()
        cursor.execute(update_sql, (1, 1))
        cursor.close()
        self.connection.commit()

    def fetch_completed_tradings(self, user: int) -> list:
        """完了済みの trading レコードを取得します。

        Args:
            user (int): trading.user

        Returns:
            list: tradings
        """

        select_sql = ' '.join([
            'SELECT *',
            'FROM trading',
            'WHERE user=%s AND sold_at IS NOT NULL',
        ])
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(select_sql, (user,))
        records = cursor.fetchall()
        cursor.close()
        return records

    def fetch_stocks(self) -> list:
        """stocks を取得します。

        Returns:
            list: stocks
        """

        select_sql = ' '.join([
            'SELECT * FROM shuumulator.stock',
        ])
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(select_sql)
        records = cursor.fetchall()
        cursor.close()
        return records

    def create_stock_log(self, stock_id, price) -> int:
        """stock_log を INSERT します。

        Args:
            stock_id ([type]): stock.id
            price ([type]): stock_log.price

        Returns:
            int: created id
        """

        update_sql = ' '.join([
            'INSERT INTO stock_log (stock, price, created_at)',
            'VALUES (%s, %s, %s)',
        ])
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            update_sql,
            (stock_id, price, datetime.datetime.now(tz=pytz.utc))
        )
        last_row_id = cursor.lastrowid
        cursor.close()
        self.connection.commit()
        return last_row_id


def get_placeholder(count: int) -> str:
    """count ぶんのプレースホルダ文字列を作ります。
    %s, %s, %s, %s, ...

    Args:
        count (int): 欲しい %s の数。

    Returns:
        str: %s, %s, %s, %s, ...
    """

    return ','.join(('%s' for i in range(count)))


def get_my_logger(logger_name: str) -> logging.Logger:
    """モジュール用のロガーを作成します。
    logger = get_my_logger(__name__)

    Args:
        logger_name (str): getLogger にわたす名前。 __name__ を想定しています。

    Returns:
        logging.Logger: モジュール用のロガー。
    """

    """
    メインの処理とは別に関係ない。

    Returns:
        Logger -- モジュール用のロガー。
    """

    # ルートロガーを作成します。ロガーはモジュールごとに分けるもの。
    logger = logging.getLogger(logger_name)
    # ルートロガーのログレベルは DEBUG。
    logger.setLevel(logging.DEBUG)
    # コンソールへ出力するハンドラを作成。
    handler = logging.StreamHandler()
    # ハンドラもログレベルを持ちます。
    handler.setLevel(logging.DEBUG)
    # ログフォーマットをハンドラに設定します。
    formatter = logging.Formatter(
        # NOTE: 改行は逆に見づらいので E501 を無視します。
        '%(asctime)s - %(levelname)s - %(filename)s - %(name)s - %(funcName)s - %(message)s')  # noqa: E501
    handler.setFormatter(formatter)
    # ハンドラをロガーへセットします。
    logger.addHandler(handler)
    # 親ロガーへの(伝播をオフにします。
    logger.propagate = False
    return logger


def send_slack_message(message: str) -> None:
    """slack_sdk を用いたメッセージ送信を行います。
    Document: https://github.com/slackapi/python-slack-sdk/blob/main/tutorial/01-creating-the-slack-app.md  # noqa: E501

    Args:
        message (str): 送信したいメッセージ。
    """

    slack_client = WebClient(token=consts.SLACK_BOT_TOKEN)

    try:
        # NOTE: unfurl_links は時折鬱陶しいと思っている「リンクの展開機能」です。不要です。 False.
        response = slack_client.chat_postMessage(
            channel=consts.SLACK_MESSAGE_CHANNEL,
            text=message,
            unfurl_links=False)
        # NOTE: Slack api のドキュメントにあるコードですが、正常に終了しても false になる場合があるので注意。
        #       リンクの含まれるメッセージを送信すると、返却値が勝手に変更されるため一致しません。
        #       - リンクの前後に <, > がつく
        #       - & -> &amp; エスケープが起こる
        assert response['message']['text'] == message
    except SlackApiError as e:
        assert e.response['ok'] is False
        # str like 'invalid_auth', 'channel_not_found'
        assert e.response['error']
        logger.error(f'Got an error: {e.response["error"]}')


# utils モジュール用のロガーを作成します。
logger = get_my_logger(__name__)

if __name__ == '__main__':
    logger.debug('でばーぐ')
    logger.info('いんーふぉ')
    logger.warning('うぉーにん')
    logger.error('えろあ')
    logger.fatal('ふぇーたる(critical と同じっぽい)')
    logger.critical('くりてぃこぉ')
