# User modules.
import utils
import functions


# ロガーを取得します。
logger = utils.get_my_logger(__name__)
logger.info('Shuumulator starts.')

# 利確ラインを定義します。
profit_booking_rate = functions.get_profit_booking_rate()
logger.info(f'利確ライン {repr(profit_booking_rate)} で実行します。')

# ユーザの勝率を取得します。
user_wins_rate = functions.get_user_wins_rate(user_id=1)
logger.info(f'現在のユーザ勝率は {repr(user_wins_rate)} です。')

# DB から監視対象銘柄を取得します。

# スクレイピングで現在の価格を取得します。

