"""Shuumulator aggregation module

Shuumulator main module が行った売買の集計を行いログ上で可視化するモジュールです。

code,name,buy,bought_at,sell,sold_at,difference,difference_percentage
...(CSV)...

Total trades: ****
Wins: ****
Loses: ****
Win rate: ****
Total earning: ****
Average plus: ****
Average minus: ****
Total gain: ****
Total lose: ****
"""

# Built-in modules.
import datetime
import pytz

# User modules.
import utils


# ロガーを取得します。
logger = utils.get_my_logger(__name__)
current_utc = datetime.datetime.now(tz=pytz.utc)
logger.info(f'Shuumulator started at {current_utc.isoformat()}')
current_jst = datetime.datetime.now(tz=pytz.timezone('Asia/Tokyo'))
logger.info(f'Shuumulator started at {current_jst.isoformat()}')
logger.info('以下に、売付の済んだ取引一覧を表示します。')

# 売買履歴(trading)をすべて取得します。
with utils.DbClient() as db_client:
    tradings = db_client.fetch_completed_tradings_with_stock(user=1)

# 各 dict にロギング用の項目を足します。
# NOTE: code,name,buy,bought_at,sell,sold_at,difference,difference_percentage
logs = []
for i in range(len(tradings)):
    _ = tradings.pop()
    # _ の例は次の通り。
    # {'id': 1, 'stock': 1, 'user': 1,
    # 'buy': Decimal('1443.00'),
    # 'bought_at': datetime.datetime(2021, 3, 2, 13, 32, 39),
    # 'sell': Decimal('1500.00'),
    # 'sold_at': datetime.datetime(2021, 3, 2, 13, 32, 39),
    # 'created_at': datetime.datetime(2021, 3, 2, 13, 32, 39),
    # 'code': '9434', 'name': 'ソフトバンク'}
    logs.append(dict(
        code=_['code'],
        name=_['name'],
        buy=float(_['buy']),
        bought_at=_['bought_at'].strftime('%Y-%m-%dT%H:%M:%SZ'),
        sell=float(_['sell']),
        sold_at=_['sold_at'].strftime('%Y-%m-%dT%H:%M:%SZ'),
        difference=float(_['sell'] - _['buy']),
        difference_percentage=float((_['sell'] - _['buy']) / _['buy'] * 100),
    ))

# 勝ち一覧。
logs_win = list(filter(lambda x: x['difference'] >= 0, logs))
# 負け一覧。
logs_lose = list(filter(lambda x: x['difference'] < 0, logs))
# difference 一覧。
differences = list(map(lambda x: x['difference'], logs))
# difference_percentage 一覧。
difference_percentages = list(map(lambda x: x['difference_percentage'], logs))

# 集計項目を算出します。
total_trades_len = len(logs)
wins_len = len(logs_win)
loses_len = total_trades_len - wins_len
win_rate = wins_len / total_trades_len
total_earning = sum(differences)
total_gain = sum(list(filter(lambda x: x >= 0, differences)))
total_lost = total_earning - total_gain

# 出力します。
print(','.join([
    '"code"',
    '"name"',
    '"buy"',
    '"bought_at"',
    '"sell"',
    '"sold_at"',
    '"difference"',
    '"difference_percentage"',
]))
for _ in logs:
    # NOTE: excel にコピペすることを考えてダブルクォーテーションで囲います。
    print(','.join([
        '"' + str(_['code']) + '"',
        '"' + str(_['name']) + '"',
        '"' + str(_['buy']) + '"',
        '"' + str(_['bought_at']) + '"',
        '"' + str(_['sell']) + '"',
        '"' + str(_['sold_at']) + '"',
        '"' + str(_['difference']) + '"',
        '"' + str(_['difference_percentage']) + '"',
    ]))
print(f'total_trades_len: {total_trades_len}')
print(f'wins_len: {wins_len}')
print(f'loses_len: {loses_len}')
print(f'win_rate: {win_rate}')
print(f'total_earning: {total_earning}')
print(f'total_gain: {total_gain}')
print(f'total_lost: {total_lost}')
