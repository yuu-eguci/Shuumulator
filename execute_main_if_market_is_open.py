"""Module, executes main.py if market is open

functions.market_is_open 関数が True を返したとき、 main.py を実行するスクリプトです。
"""


# Built-in modules.
import datetime
import pytz
import sys

# User modules.
import utils
import functions

# ロガーを取得します。
logger = utils.get_my_logger(__name__)
current_jst = datetime.datetime.now(tz=pytz.timezone('Asia/Tokyo'))
logger.info(f'Run at {current_jst.isoformat()}')

# 実行するタイミングかどうかを判別します。
# NOTE: 本スクリプトは、 cron で一時間ごとに呼ばれることを意図しています。
#       ただ、リアルタイムの株価を取得するプログラムであるので、取引時間外に実行しても意味がありません。
#       そこで、取引時間外であればプログラムを終了します。
if not functions.market_is_open():
    logger.info('Market is closed.')
    sys.exit()

# 実行しないなら読み込む意味がありません。 market_is_open を超えたところで初めて import します。
import main  # noqa: E402

main.run()
current_jst = datetime.datetime.now(tz=pytz.timezone('Asia/Tokyo'))
logger.info(f'Finished at {current_jst.isoformat()}')
