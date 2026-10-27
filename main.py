"""Shuumulator main module

株価をスクレイピングで取得し、一定のルール(Shuumulator)で算出した利確ラインと損切ラインによって仮想売買を行うモジュールです。
実行すると stock テーブルに登録されている銘柄について売買を行います。
NOTE: DB への書き込みとスクレイピングを行うので、 --execute を付けたときだけ動きます。
"""

# Built-in modules.
import argparse
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

# Third-party modules.
import dotenv
import mysql.connector
import requests

# User modules.
import consts
import functions
import utils

# ロガーを取得します。
logger = utils.get_my_logger(__name__)


def run(settings: consts.Settings,
        session,
        now: Callable[[], datetime] = lambda: datetime.now(tz=UTC),
        sleep: Callable[[float], None] = time.sleep) -> int:
    """メインの実行関数です。

    Args:
        settings (consts.Settings): 設定。
        session: requests.Session (テストでは偽物)。
        now (Callable, optional): 現在時刻を返す関数。
        sleep (Callable, optional): 待機する関数。

    Returns:
        int: 終了コード。全銘柄うまくいけば 0、失敗した銘柄がある、あるいは中止したら 1。
    """

    logger.info(f'Shuumulator started at {now().astimezone(functions.JST).isoformat()}')

    # NOTE: cron が重なっても同じ銘柄を二重に買わないよう、実行中はロックを持ち続けます。
    #       ロックはこの接続を閉じると外れます。
    try:
        with utils.DbClient(settings) as lock_client:
            if not lock_client.acquire_run_lock():
                logger.error('別の Shuumulator が実行中なので、何もせずに終了します。')
                return 1
            return run_locked(settings, session, now, sleep)
    except mysql.connector.Error as e:
        logger.error(f'DB の読み込みに失敗したので、売買を中止します: {e}')
        return 1


def run_locked(settings: consts.Settings,
               session,
               now: Callable[[], datetime],
               sleep: Callable[[float], None]) -> int:
    """実行ロックを取ったあとの処理です。"""

    # 利確ラインを定義します。
    profit_booking_rate = functions.get_profit_booking_rate()
    logger.info(f'利確ライン {profit_booking_rate!r} で実行します。')

    # ユーザの勝率を取得し、損切ラインを算出します。
    # NOTE: 利確ラインと勝率がわかると損切ラインがわかります。
    with utils.DbClient(settings) as db_client:
        completed_tradings = db_client.fetch_completed_tradings(settings.user_id)
        target_stocks = db_client.fetch_stocks()
    user_wins_rate = functions.calculate_wins_rate(completed_tradings)
    logger.info(f'現在のユーザ勝率は {user_wins_rate!r} です。')
    try:
        loss_cut_rate = functions.get_loss_cut_rate(profit_booking_rate, user_wins_rate)
    except functions.LossCutRateUnavailableError as e:
        # NOTE: 損切ラインなしでは売買のルールが成り立たないので、何も書き込まずに中止します。
        logger.error(f'{e} 売買を中止します。')
        return 1
    logger.info(f'損切ライン {loss_cut_rate!r} と算出されました。')
    logger.info(f'対象銘柄は {len(target_stocks)} 件です。')

    failures = 0
    for stock in target_stocks:
        # スクレイピング先に負荷をかけることを避けるため、待機します。
        sleep(5)

        # NOTE: 1 銘柄ずつ別トランザクションです。失敗した銘柄はロールバックしてスキップします。
        try:
            _ = functions.get_current_stock_price(stock['code'], session=session)
            current_stock_price = _['data_price']
            stock_short_name = _['data_short_name']

            with utils.DbClient(settings) as db_client:
                current_time = now()
                # stock_log 保存。
                # NOTE: これが必要なのかは微妙ですね。せっかく取得した情報がもったいないと思い、記録しています。
                db_client.create_stock_log(stock['id'], current_stock_price, current_time)
                # この stock の買付、売付を行います。
                result = functions.deal_in(
                    db_client,
                    stock_id=stock['id'],
                    user_id=settings.user_id,
                    current_stock_price=current_stock_price,
                    profit_booking_rate=profit_booking_rate,
                    loss_cut_rate=loss_cut_rate,
                    now=current_time,
                )
                db_client.commit()
        except (functions.StockDataError, utils.DbError, mysql.connector.Error) as e:
            failures += 1
            logger.error(f'{stock["id"]} {stock["code"]} をスキップしました: {e}')
            continue

        # NOTE: 銘柄の名称には stock['name'] を使うこともできます。
        #       ただ、スクレイピングで stock_price と一緒に取得した値のほうが正確だと考えこれを使っています。
        #       stock.name が間違っている可能性を考慮しているということです。
        logger.info(f'{stock["id"]} {stock_short_name} {result["message"]}')

    logger.info(f'Shuumulator finished at {now().astimezone(functions.JST).isoformat()}')
    if failures:
        logger.error(f'{failures} 件の銘柄が失敗しました。')
        return 1
    return 0


def parse_args(description: str, argv: list[str] | None) -> argparse.Namespace:
    """--execute を受け取る共通の引数パーサです。"""

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--execute', action='store_true',
                        help='本当に実行します。 DB への読み書きや株価の取得を行います。')
    return parser.parse_args(argv)


def load_settings_for_execution() -> consts.Settings | None:
    """カレントディレクトリの .env を読み、設定を返します。設定がおかしければ None です。"""

    # NOTE: 親ディレクトリはさかのぼりません。
    dotenv.load_dotenv(Path.cwd() / '.env')
    try:
        return consts.load_settings()
    except consts.ConfigError as e:
        print(f'設定エラー: {e}', file=sys.stderr)
        return None


def refuse_without_execute() -> int:
    print('何もしませんでした。実行するには --execute を付けてください。', file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    args = parse_args('仮想売買を 1 回行います。', argv)
    if not args.execute:
        return refuse_without_execute()
    settings = load_settings_for_execution()
    if settings is None:
        return 2
    with requests.Session() as session:
        return run(settings, session=session)


if __name__ == '__main__':
    sys.exit(main())
