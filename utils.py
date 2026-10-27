"""
Python やるときにいつもあって欲しい自分用モジュールです。
これは使いまわしたいのでリポジトリのビジネスロジック入れないでね。
NOTE: DbClient 内なら OK。
以下、できること。

# MySQL への接続。
# NOTE: 書き込んだら commit() してください。 with を例外で抜けるとロールバックします。
with utils.DbClient(settings) as db_client:
    stocks = db_client.fetch_stocks()

# logger の取得。
logger = utils.get_my_logger(__name__)
"""

# Built-in modules.
import hashlib
import logging
from datetime import UTC, datetime
from decimal import Decimal

# Third-party modules.
import mysql.connector

# User modules.
import consts


class DbError(Exception):
    """DB の状態が想定と違うときのエラーです。"""


def get_connection_config(settings: consts.Settings) -> dict:
    """mysql.connector.connect に渡す設定を作ります。

    NOTE: TLS が有効なときは、証明書の検証を必ず有効にします。
          ssl_verify_cert が False だと、 TLS 非対応のサーバには平文で接続してしまいます。
    """

    config = {
        'host': settings.mysql_host,
        'port': settings.mysql_port,
        'user': settings.mysql_user,
        'password': settings.mysql_password,
        'database': settings.mysql_database,
        'connection_timeout': 10,
    }
    if settings.mysql_tls:
        config.update(
            ssl_disabled=False,
            ssl_ca=settings.mysql_ssl_ca,
            ssl_verify_cert=True,
            ssl_verify_identity=settings.mysql_ssl_verify_identity,
        )
    else:
        config.update(ssl_disabled=True)
    return config


def get_run_lock_name(settings: consts.Settings) -> str:
    """売買の実行を 1 つに絞るための MySQL ロック (GET_LOCK) の名前です。
    NOTE: GET_LOCK の名前はサーバ全体で共有され、 64 文字までなので、 DB 名とユーザをハッシュにします。
    """

    key = f'{settings.mysql_database}:{settings.user_id}'.encode()
    return f'shuumulator:{hashlib.sha256(key).hexdigest()[:32]}'


def to_utc_naive(value: datetime) -> datetime:
    """DB に保存するため、 aware datetime を UTC のタイムゾーンなし datetime にします。"""

    if value.tzinfo is None:
        raise ValueError('タイムゾーン付きの datetime を渡してください。')
    return value.astimezone(UTC).replace(tzinfo=None)


class DbClient:
    """DB アクセスを行うクラスです。 with 構文で使用可能です。
    with utils.DbClient(settings) as db_client:
        stocks = db_client.fetch_stocks()
    """

    def __init__(self, settings: consts.Settings):
        self.settings = settings

    def __enter__(self):
        self.connection = mysql.connector.connect(**get_connection_config(self.settings))
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is not None:
                self.connection.rollback()
        finally:
            self.connection.close()

    def commit(self) -> None:
        self.connection.commit()

    def acquire_run_lock(self) -> bool:
        """売買の実行ロックを待たずに取ります。取れなければ False です。
        NOTE: ロックはこの接続を閉じると外れます。
        """

        cursor = self.connection.cursor()
        try:
            cursor.execute('SELECT GET_LOCK(%s, 0)', (get_run_lock_name(self.settings),))
            (acquired,) = cursor.fetchone()
        finally:
            cursor.close()
        return acquired == 1

    def _fetch_all(self, sql: str, params: tuple = ()) -> list:
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            cursor.close()

    def _execute(self, sql: str, params: tuple) -> tuple[int, int]:
        """INSERT, UPDATE を実行して (lastrowid, rowcount) を返します。 commit はしません。"""

        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, params)
            return cursor.lastrowid, cursor.rowcount
        finally:
            cursor.close()

    def fetch_completed_tradings(self, user_id: int, with_stock: bool = False) -> list:
        """完了済みの trading レコードを取得します。

        Args:
            user_id (int): trading.user_id
            with_stock (bool, optional): Defaults to False.
                                         True なら stock.code, stock.name も取得します。

        Returns:
            list: tradings
        """

        columns = ['trading.id', 'trading.stock_id', 'trading.user_id', 'trading.buy',
                   'trading.bought_at', 'trading.sell', 'trading.sold_at']
        if with_stock:
            columns += ['stock.code', 'stock.name']
        select_sql = ' '.join([
            'SELECT', ', '.join(columns),
            'FROM trading',
            'LEFT JOIN stock ON trading.stock_id = stock.id' if with_stock else '',
            'WHERE trading.user_id = %s AND trading.sold_at IS NOT NULL',
            'ORDER BY trading.sold_at, trading.id',
        ])
        return self._fetch_all(select_sql, (user_id,))

    def fetch_newest_trading(self, stock_id: int, user_id: int) -> dict | None:
        """このユーザの、この stock の最新 trading レコードを取得します。
        存在しなければ None を返します。
        """

        select_sql = ' '.join([
            'SELECT id, stock_id, user_id, buy, bought_at, sell, sold_at, created_at',
            'FROM trading',
            'WHERE stock_id = %s AND user_id = %s',
            'ORDER BY created_at DESC, id DESC',
            'LIMIT 1',
        ])
        records = self._fetch_all(select_sql, (stock_id, user_id))
        return records[0] if records else None

    def fetch_stocks(self) -> list:
        """stocks を取得します。
        NOTE: 接続先は設定の MYSQL_DATABASE です。 DB 名は SQL に書きません。
        """

        return self._fetch_all('SELECT id, code, name FROM stock ORDER BY id')

    def create_stock_log(self, stock_id: int, price: Decimal, created_at: datetime) -> int:
        """stock_log を INSERT します。

        Returns:
            int: created id
        """

        insert_sql = 'INSERT INTO stock_log (stock_id, price, created_at) VALUES (%s, %s, %s)'
        last_row_id, _ = self._execute(insert_sql, (stock_id, price, to_utc_naive(created_at)))
        return last_row_id

    def create_trading(self, stock_id: int, user_id: int, price: Decimal,
                       bought_at: datetime) -> int:
        """trading を一件追加します (買付)。

        Returns:
            int: created trading.id
        """

        insert_sql = ' '.join([
            'INSERT INTO trading',
            '(stock_id, user_id, buy, bought_at, created_at)',
            'VALUES (%s, %s, %s, %s, %s)',
        ])
        bought_at = to_utc_naive(bought_at)
        last_row_id, _ = self._execute(insert_sql, (stock_id, user_id, price, bought_at, bought_at))
        return last_row_id

    def update_trading(self, trading_id: int, user_id: int, sell_price: Decimal,
                       sold_at: datetime) -> None:
        """trading.sell と trading.sold_at を更新します (売付)。

        Raises:
            DbError: このユーザの未売却の trading が見つからない。
        """

        update_sql = ' '.join([
            'UPDATE trading',
            'SET sell = %s, sold_at = %s',
            'WHERE id = %s AND user_id = %s AND sold_at IS NULL',
        ])
        _, row_count = self._execute(
            update_sql, (sell_price, to_utc_naive(sold_at), trading_id, user_id))
        if row_count != 1:
            raise DbError(f'売付できる trading が見つかりません。 trading.id: {trading_id}')


def get_my_logger(logger_name: str) -> logging.Logger:
    """モジュール用のロガーを作成します。
    logger = get_my_logger(__name__)

    Args:
        logger_name (str): getLogger にわたす名前。 __name__ を想定しています。

    Returns:
        logging.Logger: モジュール用のロガー。
    """

    logger = logging.getLogger(logger_name)
    # NOTE: 同じ名前で何度呼ばれてもハンドラを重ねて付けないようにします。
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    # コンソールへ出力するハンドラを作成。
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s - %(name)s - %(funcName)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    # 親ロガーへの伝播をオフにします。
    logger.propagate = False
    return logger
