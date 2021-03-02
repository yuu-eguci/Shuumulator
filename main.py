# Built-in modules.
import datetime
import pytz
import time

# User modules.
import utils
import functions


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
    # TODO: GitHub Actions で動かすときは有効化
    # time.sleep(5)

    # スクレイピングで現在の価格を取得します。
    # NOTE: テスト中につき実際の値は取得せずテスト値で処理を進めています。
    # current_stock_price = functions.get_current_stock_price(stock['code'])
    import decimal
    current_stock_price = decimal.Decimal('1412.0')

    # stock_log 保存。
    # NOTE: これが必要なのかは微妙ですね。せっかく取得した情報がもったいないと思い、記録しています。
    with utils.DbClient() as db_client:
        db_client.create_stock_log(
            stock['id'],
            current_stock_price
        )

    # この stock の最新 trading 情報を取得します。
    with utils.DbClient() as db_client:
        newest_trading = db_client.fetch_newest_trading(
            stock['id']
        )
    print(dict(newest_trading=newest_trading))

    # この stock は手持ちがあるかどうかを判断します。
    # NOTE: そもそも trading が無い -> 当然、手持ち無し
    # NOTE: sold_at が埋まっている -> 売却済み -> 手持ち無し
    holds_this_stock = (not newest_trading['sold_at']
                        if newest_trading
                        else False)
    print(
        dict(
            holds_this_stock=holds_this_stock,
            sold_at=newest_trading['sold_at'] if newest_trading else None))

    # 手持ちがなければ、有無を言わさず買います。
    if not holds_this_stock:
        # NOTE: 買うということは trading に一件追加するということです。
        with utils.DbClient() as db_client:
            db_client.create_trading(
                stock_id=stock['id'],
                user_id=1,
                price=current_stock_price,
            )
        # TODO: WIP につき break 実際は continue です
        break

    # この stock の手持ちがある場合は、売るかどうかの判断に進みます。
    # 売るのは、利確ラインを超えているとき、あるいは損切ラインを下回っているときです。
    buy_price = newest_trading['buy']
    profit_booking_price = (buy_price + buy_price * profit_booking_rate)
    loss_cut_price = (buy_price - buy_price * loss_cut_rate)
    print(
        dict(
            buy_price=buy_price,
            profit_booking_price=profit_booking_price,
            loss_cut_price=loss_cut_price))
    if (current_stock_price >= profit_booking_price
            or current_stock_price <= loss_cut_price):
        # NOTE: 売るということは trading.sell を埋めるということです。
        with utils.DbClient() as db_client:
            db_client.update_trading(
                trading_id=newest_trading['id'],
                sell_price=current_stock_price,
            )

    # TODO: WIP につき break
    break

current_utc = datetime.datetime.now(tz=pytz.utc)
logger.info(f'Shuumulator finished at {current_utc.isoformat()}')
current_jst = datetime.datetime.now(tz=pytz.timezone('Asia/Tokyo'))
logger.info(f'Shuumulator finished at {current_jst.isoformat()}')
