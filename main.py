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

    # スクレイピングで現在の価格を取得します。
    # NOTE: テスト中につき実際の値は取得せずテスト値で処理を進めています。
    # current_stock_price = functions.get_current_stock_price(stock['code'])
    import decimal
    current_stock_price = decimal.Decimal('1377.0')

    # stock_log 保存。
    # NOTE: これが必要なのかは微妙ですね。せっかく取得した情報がもったいないと思い、記録しています。
    with utils.DbClient() as db_client:
        tradings = db_client.create_stock_log(
            stock['id'],
            current_stock_price
        )

    # この stock の最新 trading 情報を取得します。

    # 売却済みであれば、有無を言わさず買います。
    # NOTE: sold_at があるということが売却済みの証です。
    # NOTE: 買うということは trading に一件追加するということです。

    # この stock の手持ちがある場合は、売るかどうかの判断に進みます。
    # 売るのは、利確ラインを超えているとき、あるいは損切ラインを下回っているときです。

    # スクレイピング先に負荷をかけることを避けるため、待機します。
    time.sleep(5)
    break

current_utc = datetime.datetime.now(tz=pytz.utc)
logger.info(f'Shuumulator finished at {current_utc.isoformat()}')
current_jst = datetime.datetime.now(tz=pytz.timezone('Asia/Tokyo'))
logger.info(f'Shuumulator finished at {current_jst.isoformat()}')
