"""Module, executes main.py if market is open

functions.market_is_open 関数が True を返したとき、 main.py を実行するスクリプトです。
NOTE: 本スクリプトは、 cron で一時間ごとに呼ばれることを意図しています。
      ただ、リアルタイムの株価を取得するプログラムであるので、取引時間外に実行しても意味がありません。
      そこで、取引時間外であればプログラムを終了します。
"""

# Built-in modules.
import sys
from collections.abc import Callable
from datetime import UTC, datetime

# Third-party modules.
import requests

# User modules.
import functions
import main as shuumulator_main
import utils

# ロガーを取得します。
logger = utils.get_my_logger(__name__)


def main(argv: list[str] | None = None,
         now: Callable[[], datetime] = lambda: datetime.now(tz=UTC)) -> int:
    args = shuumulator_main.parse_args('東証が開いているときだけ仮想売買を 1 回行います。', argv)
    if not args.execute:
        return shuumulator_main.refuse_without_execute()
    # NOTE: 設定の間違いに市場の開閉と関係なく気づけるよう、先に設定を確認します。
    settings = shuumulator_main.load_settings_for_execution()
    if settings is None:
        return 2

    current_time = now()
    logger.info(f'Run at {current_time.astimezone(functions.JST).isoformat()}')
    try:
        is_open = functions.market_is_open(current_time)
    except functions.CalendarNotCoveredError as e:
        # NOTE: 開いているか分からないときは実行しません。
        logger.error(str(e))
        return 1
    if not is_open:
        logger.info('Market is closed.')
        return 0

    with requests.Session() as session:
        return shuumulator_main.run(settings, session=session)


if __name__ == '__main__':
    sys.exit(main())
