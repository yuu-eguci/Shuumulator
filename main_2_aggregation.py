"""Shuumulator aggregation module

Shuumulator main module が行った売買の集計を行い、標準出力に表示するモジュールです。
NOTE: DB は読むだけです。それでも本番 DB に接続するので、 --execute を付けたときだけ動きます。

"code","name","buy","bought_at","sell","sold_at","difference","difference_percentage"
...(CSV)...
total_trades_len: ****
wins_len: ****
loses_len: ****
draws_len: ****
win_rate: ****
total_earning: ****
total_gain: ****
total_lost: ****
"""

# Built-in modules.
import csv
import sys
from decimal import ROUND_HALF_UP, Decimal
from typing import TextIO

# Third-party modules.
import mysql.connector

# User modules.
import consts
import functions
import main as shuumulator_main
import utils

# ロガーを取得します。
logger = utils.get_my_logger(__name__)

CSV_COLUMNS = ['code', 'name', 'buy', 'bought_at', 'sell', 'sold_at',
               'difference', 'difference_percentage']


def summarize(tradings: list) -> dict:
    """売付の済んだ取引を集計します。金額はすべて Decimal で計算します。

    NOTE: 勝ち負けの定義は functions.is_win と同じです。同値は引き分けで、勝率の分母には入ります。
    """

    differences = [t['sell'] - t['buy'] for t in tradings]
    wins_len = sum(1 for t in tradings if functions.is_win(t))
    loses_len = sum(1 for d in differences if d < 0)
    total_gain = sum((d for d in differences if d > 0), Decimal('0'))
    total_lost = sum((d for d in differences if d < 0), Decimal('0'))
    return dict(
        total_trades_len=len(tradings),
        wins_len=wins_len,
        loses_len=loses_len,
        draws_len=len(tradings) - wins_len - loses_len,
        win_rate=functions.calculate_wins_rate(tradings),
        total_earning=total_gain + total_lost,
        total_gain=total_gain,
        total_lost=total_lost,
    )


def to_row(trading: dict) -> list:
    """CSV の 1 行を作ります。日時は UTC で保存されています。"""

    difference = trading['sell'] - trading['buy']
    difference_percentage = (difference / trading['buy'] * 100).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    return [
        trading['code'],
        trading['name'],
        trading['buy'],
        trading['bought_at'].strftime('%Y-%m-%dT%H:%M:%SZ'),
        trading['sell'],
        trading['sold_at'].strftime('%Y-%m-%dT%H:%M:%SZ'),
        difference,
        difference_percentage,
    ]


def write_report(tradings: list, out: TextIO) -> None:
    """取引一覧の CSV と集計結果を書き出します。"""

    # NOTE: excel にコピペすることを考えてダブルクォーテーションで囲います。
    writer = csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator='\n')
    writer.writerow(CSV_COLUMNS)
    writer.writerows(to_row(t) for t in tradings)
    for key, value in summarize(tradings).items():
        out.write(f'{key}: {value}\n')


def run(settings: consts.Settings, out: TextIO) -> int:
    """DB から売付の済んだ取引を読み、集計を書き出します。"""

    logger.info('以下に、売付の済んだ取引一覧を表示します。')
    try:
        with utils.DbClient(settings) as db_client:
            tradings = db_client.fetch_completed_tradings(settings.user_id, with_stock=True)
    except mysql.connector.Error as e:
        logger.error(f'DB の読み込みに失敗しました: {e}')
        return 1
    if not tradings:
        logger.info('表示する取引はありません。')
        return 0
    write_report(tradings, out)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = shuumulator_main.parse_args('売付の済んだ取引を集計して表示します。', argv)
    if not args.execute:
        return shuumulator_main.refuse_without_execute()
    settings = shuumulator_main.load_settings_for_execution()
    if settings is None:
        return 2
    return run(settings, sys.stdout)


if __name__ == '__main__':
    sys.exit(main())
