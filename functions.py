# NOTE: ざくざく実装するためひとつのファイルにすべてまとめています。のちに整理します。

# Built-in modules.
from decimal import Decimal

# User modules.
import consts
import utils


def get_profit_booking_rate() -> Decimal:
    """利確ラインを取得します。"""

    return Decimal(consts.PROFIT_BOOKING_RATE)


def get_user_wins_rate(user_id: int) -> Decimal:
    """ユーザの現在の勝率を算出します。

    Args:
        user_id (int): trading.user

    Returns:
        Decimal: wins_rate
    """

    # このユーザの完了済み取引記録を取得します。
    with utils.DbClient() as db_client:
        tradings = db_client.fetch_completed_tradings(user_id)

    # 取引数。
    tradings_count = len(tradings)
    # NOTE: 取引がないときは勝率 50% とします。
    if not tradings_count:
        return Decimal('0.5')

    # 勝ち数。
    wins_count = len(filter(lambda t: t['sell'] > t['buy'], tradings))

    # 勝率。
    wins_rate = Decimal(str(wins_count)) / Decimal(str(tradings_count))

    return wins_rate
