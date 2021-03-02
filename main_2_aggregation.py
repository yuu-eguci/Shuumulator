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
import time

# User modules.
import utils
import functions


# 売買履歴(trading)をすべて取得します。

# 各 dict にロギング用の項目を足します。
# NOTE: code,name,buy,bought_at,sell,sold_at,difference,difference_percentage

# 集計項目を算出します。
# Total trades
# Wins
# Loses
# Win rate
# Total earning
# Average plus
# Average minus
# Total gain
# Total lose
