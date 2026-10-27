"""Shuumulator のビジネスロジックです。"""

# Built-in modules.
import csv
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

# Third-party modules.
import requests
from bs4 import BeautifulSoup

# User modules.
import consts
import utils

JST = ZoneInfo('Asia/Tokyo')

# 東証の立会時間です。 [開始, 終了) で判定します。
# NOTE: https://www.jpx.co.jp/english/equities/trading/domestic/01.html (2026-10-27 確認)
TSE_SESSIONS = (
    (time(9, 0), time(11, 30)),
    (time(12, 30), time(15, 30)),
)
TSE_HOLIDAYS_CSV = Path(__file__).resolve().parent / 'data' / 'tse_holidays.csv'

# 銘柄コードは 4 桁です。 2024 年からは英字を含むコード (例: 130A) もあります。
STOCK_CODE_PATTERN = re.compile(r'[0-9][0-9A-Z]{3}')
# 株価取得のタイムアウト (接続, 読み込み) 秒です。
SCRAPING_TIMEOUT = (5, 20)


class StockDataError(Exception):
    """1 銘柄ぶんのデータがおかしいときのエラーです。この銘柄だけスキップします。"""


class LossCutRateUnavailableError(Exception):
    """勝率が低すぎて損切ラインが決まらないときのエラーです。"""


class CalendarNotCoveredError(Exception):
    """休業日データに載っていない年なので、市場が開いているか判定できないときのエラーです。"""


@dataclass(frozen=True)
class TseHolidays:
    """休業日データです。 years は判定可能な年です。"""

    years: frozenset[int]
    dates: frozenset[date]


def load_tse_holidays(path: Path = TSE_HOLIDAYS_CSV) -> TseHolidays:
    """休業日 CSV (date,name) を読みます。 # で始まる行はコメントです。"""

    with open(path, encoding='utf-8', newline='') as f:
        rows = csv.DictReader(line for line in f if not line.startswith('#'))
        dates = frozenset(date.fromisoformat(row['date']) for row in rows)
    return TseHolidays(years=frozenset(d.year for d in dates), dates=dates)


def market_is_open(now: datetime, holidays: TseHolidays | None = None) -> bool:
    """東証の立会時間中なら True を返します。

    Args:
        now (datetime): タイムゾーン付きの現在時刻。
        holidays (TseHolidays, optional): 省略時は data/tse_holidays.csv。

    Raises:
        ValueError: now にタイムゾーンがない。
        CalendarNotCoveredError: 休業日データに now の年が載っていない。

    Returns:
        bool: 立会時間中なら True。
    """

    if now.tzinfo is None:
        raise ValueError('タイムゾーン付きの datetime を渡してください。')
    if holidays is None:
        holidays = load_tse_holidays()

    current_jst = now.astimezone(JST)
    today = current_jst.date()
    if today.year not in holidays.years:
        raise CalendarNotCoveredError(
            f'{today.year} 年の休業日データがありません。 data/tse_holidays.csv に追記してください。')

    # 土日、祝日、年末年始は休み。
    if today.weekday() >= 5 or today in holidays.dates:
        return False
    if (today.month, today.day) in ((12, 31), (1, 1), (1, 2), (1, 3)):
        return False

    current_time = current_jst.time()
    return any(start <= current_time < end for start, end in TSE_SESSIONS)


def get_profit_booking_rate() -> Decimal:
    """利確ラインを取得します。"""

    return Decimal(consts.PROFIT_BOOKING_RATE)


def is_win(trading: dict) -> bool:
    """勝ちかどうかを返します。売値が買値より高いときだけ勝ちです。同値は勝ちではありません。"""

    return trading['sell'] > trading['buy']


def calculate_wins_rate(tradings: list) -> Decimal:
    """完了済み取引の勝率を算出します。

    Args:
        tradings (list): 完了済みの trading。

    Returns:
        Decimal: wins_rate
    """

    # NOTE: 取引がないときは勝率 50% とします。
    if not tradings:
        return Decimal('0.5')

    wins_count = sum(1 for t in tradings if is_win(t))
    return Decimal(wins_count) / Decimal(len(tradings))


def get_loss_cut_rate(profit_booking_rate: Decimal,
                      user_wins_rate: Decimal) -> Decimal:
    """損切ラインを算出します。
    損切ラインは Mr.S の計算式で算出します。

    NOTE: 計算式は次のとおり。
          100*((1+利確ライン)^勝率*(1-損切ライン)^(100-勝率))^0.01=理論上資産が到達する %
    NOTE: 正直ここは自分ではよくわかってない。
          もっとシンプルな計算式になればいいんだけどうまく出来ないので、泥臭い方法で求めます。
    NOTE: 損切ラインはなるべく 0% から遠いほうがいい。
          だからとりあえず 10% から始めてだんだん 0% に近づけていきます。
          理論上資産到達割合が 100% を超えたタイミングで損切ライン決定とします。

    Args:
        profit_booking_rate (Decimal): 利確ライン
        user_wins_rate (Decimal): 勝率

    Raises:
        ValueError: 利確ラインが 0 以下、あるいは勝率が 0〜1 の範囲外。
        LossCutRateUnavailableError: 0.1% まで下げても 100% に届かない (勝率が低すぎる)。

    Returns:
        Decimal: 損切ライン
    """

    if profit_booking_rate <= 0:
        raise ValueError(f'利確ラインは正の値にしてください: {profit_booking_rate}')
    if not 0 <= user_wins_rate <= 1:
        raise ValueError(f'勝率は 0〜1 にしてください: {user_wins_rate}')

    # 0.01 -> 1% 単位変換します。
    # NOTE: 参考にしている計算式が % 表記なので、 % で統一して記述します。
    #       return 時にはもとの割合表記に戻します。
    profit_booking_per = profit_booking_rate * 100
    user_wins_per = user_wins_rate * 100

    # 10.0% -> 0.1%
    for i in range(100, 0, -1):
        # NOTE: *0.1 は不可。
        loss_cut_per_decimal = Decimal(str(i)) / 10

        # NOTE: 改行するとわけわからなくなるので noqa します。どうやってこんな式作ったんだ……
        #              100 * ((1 + 利確ライン%        *0.01) ^  勝率          * (1 - 損切ライン           *0.01) ^  (100 - 勝率         )) ^  0.01             # noqa: E501
        mystery_rate = 100 * ((1 + profit_booking_per / 100) ** user_wins_per * (1 - loss_cut_per_decimal / 100) ** (100 - user_wins_per)) ** Decimal('0.01')  # noqa: E501

        # NOTE: 返却は割合単位で行います。
        if mystery_rate >= 100:
            return loss_cut_per_decimal / 100

    # NOTE: 計算式は変えず、損切ラインなしで売買を続けることもしません。呼び出し元で実行を止めます。
    raise LossCutRateUnavailableError(
        '損切ラインの算出がうまくいきませんでした。機械割が 100% を超えません。'
        f'利確ライン:{profit_booking_per}%, 勝率:{user_wins_per}%')


def get_current_stock_price(stock_code: str, session) -> dict:
    """株価と短縮名を取得します。
    NOTE: 短縮名はロギングのために取得しています。

    Args:
        stock_code (str): 銘柄コード
        session: requests.Session (テストでは get(url, timeout) を持つ偽物)

    Raises:
        StockDataError: 銘柄コード、通信、ページの内容のどれかがおかしい。

    Returns:
        dict: {data_price=現在の株価, data_short_name=銘柄の短縮名}
    """

    # NOTE: DB の値をそのまま URL に入れるので、形式を確認してから使います。
    if not isinstance(stock_code, str) or not STOCK_CODE_PATTERN.fullmatch(stock_code):
        raise StockDataError(f'銘柄コードの形式がおかしいです: {stock_code!r}')

    url = f'https://minkabu.jp/stock/{stock_code}'
    try:
        response = session.get(url, timeout=SCRAPING_TIMEOUT)
    except requests.RequestException as e:
        raise StockDataError(f'株価のスクレイピングに失敗しました。アクセス先: {url}') from e
    if response.status_code != 200:
        raise StockDataError(
            f'株価のスクレイピングに失敗しました。アクセス先: {url}, status: {response.status_code}')

    # 株価が格納されているのは #stock-for-securities-company の data-price attribute です。
    soup = BeautifulSoup(response.text, 'lxml')
    element = soup.select_one('#stock-for-securities-company')
    if element is None:
        raise StockDataError(f'株価の要素が見つかりません。アクセス先: {url}')
    data_price = element.get('data-price')
    data_short_name = element.get('data-short-name')
    if not data_price or not data_short_name:
        raise StockDataError(f'株価か短縮名が空です。アクセス先: {url}')

    # NOTE: リポジトリ全体で Decimal を使っています。ここも Decimal で返却します。
    try:
        price = Decimal(data_price)
    except InvalidOperation as e:
        raise StockDataError(f'株価が数値ではありません: {data_price!r}') from e
    if not price.is_finite() or price <= 0:
        raise StockDataError(f'株価が正の数ではありません: {data_price!r}')

    return dict(data_price=price, data_short_name=data_short_name)


def decide(newest_trading: dict | None,
           current_stock_price: Decimal,
           profit_booking_rate: Decimal,
           loss_cut_rate: Decimal) -> dict:
    """対象 stock を買うか、売るか、キープするかを決めます。
    - もってない -> 買う
    - 現在価格が利確ライン以上 -> 売る
    - 現在価格が損切ライン以下 -> 売る
    - それ以外 -> キープ

    Raises:
        StockDataError: 手持ちの trading の買値がおかしい。

    Returns:
        dict: {action='buy'|'sell'|'keep', message=ログ用メッセージ}
    """

    # この stock は手持ちがあるかどうかを判断します。
    # NOTE: そもそも trading が無い -> 当然、手持ち無し
    # NOTE: sold_at が埋まっている -> 売却済み -> 手持ち無し
    if newest_trading is None or newest_trading['sold_at'] is not None:
        return dict(action='buy', message=f'現在の価格:{current_stock_price}, 買付しました。')

    buy_price = newest_trading['buy']
    if buy_price is None or buy_price <= 0:
        raise StockDataError(f'手持ちの買値がおかしいです。 trading.id: {newest_trading["id"]}')

    # 売るのは、利確ラインを超えているとき、あるいは損切ラインを下回っているときです。
    profit_booking_price = buy_price + buy_price * profit_booking_rate
    loss_cut_price = buy_price - buy_price * loss_cut_rate
    message = (
        f'利確:{profit_booking_price},'
        f'損切:{loss_cut_price},'
        f'現在の価格:{current_stock_price}')
    if current_stock_price >= profit_booking_price or current_stock_price <= loss_cut_price:
        return dict(action='sell', message=f'{message}, 売付しました。')
    return dict(action='keep', message=f'{message}, 売付しません。')


def deal_in(db_client: utils.DbClient,
            stock_id: int,
            user_id: int,
            current_stock_price: Decimal,
            profit_booking_rate: Decimal,
            loss_cut_rate: Decimal,
            now: datetime) -> dict:
    """対象 stock の買付と売付を行います。 commit は呼び出し元で行います。

    Returns:
        dict: decide() の結果です。
    """

    newest_trading = db_client.fetch_newest_trading(stock_id, user_id)
    result = decide(newest_trading, current_stock_price, profit_booking_rate, loss_cut_rate)

    # NOTE: 買うということは trading に一件追加するということです。
    if result['action'] == 'buy':
        db_client.create_trading(stock_id=stock_id, user_id=user_id,
                                 price=current_stock_price, bought_at=now)
    # NOTE: 売るということは trading.sell を埋めるということです。
    elif result['action'] == 'sell':
        db_client.update_trading(trading_id=newest_trading['id'], user_id=user_id,
                                 sell_price=current_stock_price, sold_at=now)
    return result
