"""Shuumulator main module

株価をスクレイピングで取得し、一定のルール(Shuumulator)で算出した利確ラインと損切ラインによって仮想売買を行うモジュールです。
実行すると stock テーブルに登録されている銘柄について売買を行います。
"""


# Built-in modules.
import datetime
import pytz
import time

# User modules.
import utils
import functions


def run():
    """メインの実行関数です。
    他のモジュール…… execute_main_if_market_is_open から呼ばれることになったため、
    関数化しました。
    """

    # ロガーを取得します。
    logger = utils.get_my_logger(__name__)
    current_utc = datetime.datetime.now(tz=pytz.utc)
    logger.info(f'Shuumulator started at {current_utc.isoformat()}')
    current_jst = datetime.datetime.now(tz=pytz.timezone('Asia/Tokyo'))
    logger.info(f'Shuumulator started at {current_jst.isoformat()}')

    # 利確ラインを定義します。
    profit_booking_rate = functions.get_profit_booking_rate()
    logger.info(f'利確ライン {repr(profit_booking_rate)} で実行します。')

    # ユーザの勝率を取得します。
    user_wins_rate = functions.get_user_wins_rate(user_id=1)
    logger.info(f'現在のユーザ勝率は {repr(user_wins_rate)} です。')

    # 損切ラインを算出します。
    # NOTE: 利確ラインと勝率がわかると損切ラインがわかります。
    loss_cut_rate = functions.get_loss_cut_rate(profit_booking_rate,
                                                user_wins_rate)
    logger.info(f'損切ライン {repr(loss_cut_rate)} と算出されました。')

    # DB から監視対象銘柄を取得します。
    target_stocks = functions.get_target_stocks()
    logger.info(f'対象銘柄は {len(target_stocks)} 件です。')

    for stock in target_stocks:
        # NOTE: stock は dict です。 { code, name }

        # スクレイピング先に負荷をかけることを避けるため、待機します。
        time.sleep(5)

        # スクレイピングで現在の価格を取得します。
        _ = functions.get_current_stock_price(stock['code'])
        current_stock_price = _['data_price']
        stock_short_name = _['data_short_name']

        # stock_log 保存。
        # NOTE: これが必要なのかは微妙ですね。せっかく取得した情報がもったいないと思い、記録しています。
        with utils.DbClient() as db_client:
            db_client.create_stock_log(
                stock['id'],
                current_stock_price
            )

        # この stock の買付、売付を行います。
        result_dic = functions.deal_in(
            stock_id=stock['id'],
            current_stock_price=current_stock_price,
            profit_booking_rate=profit_booking_rate,
            loss_cut_rate=loss_cut_rate,
        )

        # NOTE: 銘柄の名称には stock['name'] を使うこともできます。
        #       ただ、スクレイピングで stock_price と一緒に取得した値のほうが正確だと考えこれを使っています。
        #       stock.name が間違っている可能性を考慮しているということです。
        logger.info(f'{stock["id"]} {stock_short_name} {result_dic["message"]}')

    current_utc = datetime.datetime.now(tz=pytz.utc)
    logger.info(f'Shuumulator finished at {current_utc.isoformat()}')
    current_jst = datetime.datetime.now(tz=pytz.timezone('Asia/Tokyo'))
    logger.info(f'Shuumulator finished at {current_jst.isoformat()}')


if __name__ == '__main__':
    run()
