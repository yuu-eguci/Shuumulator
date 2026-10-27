"""使い捨ての MySQL (compose.yaml の mysql, mysql-notls) を使うテストです。
MYSQL_TEST_HOST が設定されていなければスキップします。
"""

import dataclasses
import io
import os
import socket
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import mysql.connector
import pytest
from helpers import FakeResponse, FakeSession

import consts
import main
import main_2_aggregation
import utils

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(not os.environ.get('MYSQL_TEST_HOST'), reason='MYSQL_TEST_HOST が未設定です。'),
]

SCHEMA = Path(__file__).resolve().parent.parent / 'docs' / 'schema.sql'
NOW = datetime(2026, 10, 27, 1, 0, tzinfo=UTC)


@pytest.fixture
def settings():
    return consts.Settings(
        mysql_host=os.environ['MYSQL_TEST_HOST'],
        mysql_port=int(os.environ['MYSQL_TEST_PORT']),
        mysql_user=os.environ['MYSQL_TEST_USER'],
        mysql_password=os.environ['MYSQL_TEST_PASSWORD'],
        mysql_database=os.environ['MYSQL_TEST_DATABASE'],
        mysql_tls=True,
        mysql_ssl_ca=os.environ['MYSQL_TEST_SSL_CA'],
        mysql_ssl_verify_identity=True,
        user_id=1,
    )


def execute(settings, sql, params=()):
    """テストの準備と確認に使う生の SQL 実行です。"""

    connection = mysql.connector.connect(**utils.get_connection_config(settings))
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(sql, params)
        rows = cursor.fetchall() if cursor.with_rows else cursor.lastrowid
        connection.commit()
        return rows
    finally:
        connection.close()


@pytest.fixture
def db(settings):
    """docs/schema.sql でテーブルを作り直します。"""

    for table in ('stock_log', 'trading', 'stock'):
        execute(settings, f'DROP TABLE IF EXISTS {table}')
    body = '\n'.join(line for line in SCHEMA.read_text(encoding='utf-8').splitlines()
                     if not line.startswith('--'))
    for statement in body.split(';'):
        if statement.strip():
            execute(settings, statement)
    return settings


def add_stock(settings, code, name):
    return execute(settings, 'INSERT INTO stock (code, name) VALUES (%s, %s)', (code, name))


def add_trading(settings, stock_id, user_id, buy, sell=None, created_at=NOW):
    naive = created_at.replace(tzinfo=None)
    return execute(
        settings,
        'INSERT INTO trading (stock_id, user_id, buy, bought_at, sell, sold_at, created_at)'
        ' VALUES (%s, %s, %s, %s, %s, %s, %s)',
        (stock_id, user_id, buy, naive, sell, naive if sell else None, naive))


def page(price, name='テスト'):
    return FakeResponse(200, f'<div id="stock-for-securities-company" data-price="{price}"'
                             f' data-short-name="{name}"></div>')


def run(settings, pages):
    return main.run(settings, session=FakeSession(pages), now=lambda: NOW, sleep=lambda _: None)


def test_tls_connection_is_encrypted(settings):
    with utils.DbClient(settings) as db_client:
        cursor = db_client.connection.cursor()
        cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
        _, cipher = cursor.fetchone()

    assert cipher


def test_untrusted_ca_is_rejected(settings):
    other = dataclasses.replace(settings, mysql_ssl_ca=os.environ['MYSQL_TEST_OTHER_CA'])

    with pytest.raises(mysql.connector.Error), utils.DbClient(other):
        pass


def test_hostname_mismatch_is_rejected(settings):
    # NOTE: 証明書は mysql というホスト名に対して発行しています。 IP アドレスで接続すると一致しません。
    by_ip = dataclasses.replace(settings, mysql_host=socket.gethostbyname(settings.mysql_host))

    with pytest.raises(mysql.connector.Error), utils.DbClient(by_ip):
        pass

    with utils.DbClient(dataclasses.replace(by_ip, mysql_ssl_verify_identity=False)):
        pass


@pytest.mark.parametrize('use_pure', [False, True], ids=['c-extension', 'pure-python'])
def test_tls_is_not_downgraded_when_server_has_no_tls(settings, use_pure):
    notls = dataclasses.replace(settings, mysql_host=os.environ['MYSQL_TEST_NOTLS_HOST'])
    config = utils.get_connection_config(notls)

    # NOTE: C 拡張と pure Python で TLS の扱いが違うので、両方確かめます。
    with pytest.raises(mysql.connector.Error) as e:
        mysql.connector.connect(**config, use_pure=use_pure).close()

    # NOTE: 2026 は「SSL が必要だがサーバが対応していない」です。認証など別の理由で落ちたのではないこと。
    assert e.value.errno == 2026


def test_fetch_stocks_uses_configured_database(db):
    stock_id = add_stock(db, '1357', 'A')

    with utils.DbClient(db) as db_client:
        assert db_client.fetch_stocks() == [{'id': stock_id, 'code': '1357', 'name': 'A'}]


def test_newest_trading_is_scoped_to_user(db):
    stock_id = add_stock(db, '1357', 'A')
    mine = add_trading(db, stock_id, 1, '100', created_at=datetime(2026, 10, 26, tzinfo=UTC))
    add_trading(db, stock_id, 2, '200', created_at=datetime(2026, 10, 27, tzinfo=UTC))

    with utils.DbClient(db) as db_client:
        assert db_client.fetch_newest_trading(stock_id, user_id=1)['id'] == mine
        assert db_client.fetch_newest_trading(stock_id, user_id=3) is None


def test_completed_tradings_are_scoped_and_columns_do_not_collide(db):
    add_stock(db, '0000', 'padding so that stock.id differs from trading.id')
    stock_id = add_stock(db, '1357', 'A')
    trading_id = add_trading(db, stock_id, 1, '100', sell='110')
    add_trading(db, stock_id, 1, '100')
    add_trading(db, stock_id, 2, '100', sell='90')

    with utils.DbClient(db) as db_client:
        [row] = db_client.fetch_completed_tradings(1, with_stock=True)

    assert row['id'] == trading_id
    assert row['stock_id'] == stock_id
    assert (row['code'], row['name'], row['buy'], row['sell']) == ('1357', 'A', Decimal('100.00'),
                                                                   Decimal('110.00'))


def test_update_trading_only_sells_own_open_trading(db):
    stock_id = add_stock(db, '1357', 'A')
    sold = add_trading(db, stock_id, 1, '100', sell='110')
    others = add_trading(db, stock_id, 2, '100')

    with utils.DbClient(db) as db_client:
        with pytest.raises(utils.DbError):
            db_client.update_trading(sold, user_id=1, sell_price=Decimal('120'), sold_at=NOW)
        with pytest.raises(utils.DbError):
            db_client.update_trading(others, user_id=1, sell_price=Decimal('120'), sold_at=NOW)


def test_run_buys_sells_and_isolates_bad_stock(db):
    good = add_stock(db, '1357', 'A')
    bad = add_stock(db, '9999', 'broken page')
    alnum = add_stock(db, '130A', 'B')
    url = 'https://minkabu.jp/stock/{}'.format

    first = run(db, {url('1357'): page('1000'), url('9999'): FakeResponse(200, '<html></html>'),
                     url('130A'): page('2000')})

    assert first == 1
    rows = execute(db, 'SELECT stock_id, user_id, buy, sell FROM trading ORDER BY stock_id')
    assert rows == [
        {'stock_id': good, 'user_id': 1, 'buy': Decimal('1000.00'), 'sell': None},
        {'stock_id': alnum, 'user_id': 1, 'buy': Decimal('2000.00'), 'sell': None},
    ]
    assert execute(db, 'SELECT COUNT(*) AS n FROM stock_log WHERE stock_id = %s', (bad,)) == [{'n': 0}]

    # 1357 は利確ライン (2.5%) 超え、 130A はキープ。 9999 は直った。
    second = run(db, {url('1357'): page('1030'), url('9999'): page('500'), url('130A'): page('2010')})

    assert second == 0
    rows = execute(db, 'SELECT stock_id, buy, sell FROM trading ORDER BY stock_id')
    assert rows == [
        {'stock_id': good, 'buy': Decimal('1000.00'), 'sell': Decimal('1030.00')},
        {'stock_id': bad, 'buy': Decimal('500.00'), 'sell': None},
        {'stock_id': alnum, 'buy': Decimal('2000.00'), 'sell': None},
    ]
    assert execute(db, 'SELECT COUNT(*) AS n FROM stock_log') == [{'n': 5}]

    out = io.StringIO()
    assert main_2_aggregation.run(db, out) == 0
    assert 'wins_len: 1' in out.getvalue().splitlines()


def test_run_rolls_back_stock_when_write_fails(db):
    add_stock(db, '1357', 'A')
    # NOTE: trading.user_id は INT なので、この値は INSERT で失敗します。 stock_log も残らないこと。
    too_large_user = dataclasses.replace(db, user_id=2**31)

    assert run(too_large_user, {'https://minkabu.jp/stock/1357': page('1000')}) == 1

    assert execute(db, 'SELECT COUNT(*) AS n FROM stock_log') == [{'n': 0}]
    assert execute(db, 'SELECT COUNT(*) AS n FROM trading') == [{'n': 0}]


def test_run_stops_before_writing_when_loss_cut_is_unavailable(db):
    stock_id = add_stock(db, '1357', 'A')
    for _ in range(3):
        add_trading(db, stock_id, 1, '100', sell='90')
    session = FakeSession({'https://minkabu.jp/stock/1357': page('1000')})

    result = main.run(db, session=session, now=lambda: NOW, sleep=lambda _: None)

    assert result == 1
    assert session.calls == []
    assert execute(db, 'SELECT COUNT(*) AS n FROM trading') == [{'n': 3}]
    assert execute(db, 'SELECT COUNT(*) AS n FROM stock_log') == [{'n': 0}]


def test_run_refuses_while_another_run_holds_the_lock(db):
    add_stock(db, '1357', 'A')
    session = FakeSession({'https://minkabu.jp/stock/1357': page('1000')})
    other = mysql.connector.connect(**utils.get_connection_config(db))
    try:
        cursor = other.cursor()
        cursor.execute('SELECT GET_LOCK(%s, 0)', (utils.get_run_lock_name(db),))
        assert cursor.fetchone() == (1,)

        # NOTE: cron が重なっても、同じ銘柄を二重に買わないこと。
        assert main.run(db, session=session, now=lambda: NOW, sleep=lambda _: None) == 1
        assert session.calls == []
        assert execute(db, 'SELECT COUNT(*) AS n FROM trading') == [{'n': 0}]
    finally:
        other.close()

    # ロックが外れれば実行できます。
    assert main.run(db, session=session, now=lambda: NOW, sleep=lambda _: None) == 0
    assert execute(db, 'SELECT COUNT(*) AS n FROM trading') == [{'n': 1}]


def test_run_lock_is_per_database_and_user(settings):
    other_user = dataclasses.replace(settings, user_id=2)
    other_database = dataclasses.replace(settings, mysql_database='another')

    names = {utils.get_run_lock_name(s) for s in (settings, other_user, other_database)}

    assert len(names) == 3
    assert all(len(name) <= 64 for name in names)


def test_run_fails_cleanly_when_database_is_unreachable(settings):
    unreachable = dataclasses.replace(settings, mysql_host='unreachable.invalid')
    session = FakeSession()

    assert main.run(unreachable, session=session, now=lambda: NOW, sleep=lambda _: None) == 1
    assert session.calls == []
