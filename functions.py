# NOTE: ざくざく実装するためひとつのファイルにすべてまとめています。のちに整理します。

import decimal
import consts


def get_profit_booking_rate() -> decimal.Decimal:
    """利確ラインを取得します。"""

    return decimal.Decimal(consts.PROFIT_BOOKING_RATE)
