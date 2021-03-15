# NOTE: ざくざく実装するためひとつのファイルにすべてまとめています。のちに整理します。

# Built-in modules.
from decimal import Decimal
import datetime
import pytz

# Third-party modules.
import requests
from bs4 import BeautifulSoup

# User modules.
import consts
import utils


def market_is_open() -> bool:
    """9〜15時であれば True を返します。

    Returns:
        bool: 9〜15時であれば True。
    """

    # 現在時刻。
    current_jst = datetime.datetime.now(tz=pytz.timezone('Asia/Tokyo'))
    # 現在の「時」。
    current_hour = current_jst.hour
    return 9 <= current_hour <= 15


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
    wins_count = len(list(filter(lambda t: t['sell'] > t['buy'], tradings)))

    # 勝率。
    wins_rate = Decimal(str(wins_count)) / Decimal(str(tradings_count))

    return wins_rate


def get_target_stocks() -> list:
    """対象銘柄を取得します。

    Returns:
        list: stocks
    """

    # 処理対象の銘柄一覧を取得します。
    with utils.DbClient() as db_client:
        return db_client.fetch_stocks()


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
        Exception: [description]

    Returns:
        Decimal: 損切ライン
    """

    # 0.01 -> 1% 単位変換します。
    # NOTE: 参考にしている計算式が % 表記なので、 % で統一して記述します。
    #       return 時にはもとの割合表記に戻します。
    profit_booking_per = profit_booking_rate * 100
    user_wins_per = user_wins_rate * 100

    # 10.0% -> 0.0%
    for i in range(100, 0, -1):
        # NOTE: *0.1 は不可。
        loss_cut_per_decimal = Decimal(str(i)) / 10

        # NOTE: 改行するとわけわからなくなるので noqa します。どうやってこんな式作ったんだ……
        #              100 * ((1 + 利確ライン%        *0.01) ^  勝率          * (1 - 損切ライン           *0.01) ^  (100 - 勝率         )) ^  0.01             # noqa: E501
        mystery_rate = 100 * ((1 + profit_booking_per / 100) ** user_wins_per * (1 - loss_cut_per_decimal / 100) ** (100 - user_wins_per)) ** Decimal('0.01')  # noqa: E501

        # NOTE: 返却は割合単位で行います。
        if mystery_rate >= 100:
            return loss_cut_per_decimal / 100

    # NOTE: よくわからんがうまくいかなかった場合は終了します。
    raise Exception('損切ラインの算出がうまくいきませんでした。機械割が 100% を超えません。'
                    f'利確ライン:{profit_booking_per}%, 勝率:{user_wins_per}%')


def get_current_stock_price(stock_code: str) -> dict:
    """株価と短縮名を取得します。
    NOTE: 短縮名はロギングのために取得しています。

    Args:
        stock_code (str): 銘柄コード

    Returns:
        dict: {data_price=現在の株価, data_short_name=銘柄の短縮名}
    """

    # Web ページを取得します。
    response = requests.get(f'https://minkabu.jp/stock/{stock_code}')
    assert response.status_code == 200, (
        f'株価のスクレイピングに失敗しました。アクセス先: https://minkabu.jp/stock/{stock_code}'
    )

    # 株価が格納されているのは #stock-for-securities-company の data-price attribute です。
    # BeautifulSoup によって抽出します。
    soup = BeautifulSoup(response.text, 'lxml')
    data_price = soup.select_one(
        '#stock-for-securities-company')['data-price']
    data_short_name = soup.select_one(
        '#stock-for-securities-company')['data-short-name']

    # NOTE: リポジトリ全体で Decimal を使っています。ここも Decimal で返却します。
    return dict(
        data_price=Decimal(data_price),
        data_short_name=data_short_name)


def deal_in(stock_id: int,
            current_stock_price: Decimal,
            profit_booking_rate: Decimal,
            loss_cut_rate: Decimal) -> dict:
    """対象 stock の買付と売付を行います。
    - もってない -> 買う
    - 現在価格が利確ラインより上 -> 売る
    - 現在価格が損切ラインより下 -> 売る
    - それ以外 -> キープ
    判断結果は {message} の形式で返却します。

    Args:
        stock_id (int): trading.stock
        current_stock_price (Decimal): 現在価格
        profit_booking_rate (Decimal): 利確レート。取得価格にこれをかけて利確ラインを算出します。
        loss_cut_rate (Decimal): 損切レート。取得価格にこれをかけて損切ラインを算出します。

    Returns:
        dict: 行った処理を呼び出し元に伝えるメッセージを含む dict です。
    """

    # この stock の最新 trading 情報を取得します。
    with utils.DbClient() as db_client:
        newest_trading = db_client.fetch_newest_trading(
            stock_id
        )

    # この stock は手持ちがあるかどうかを判断します。
    # NOTE: そもそも trading が無い -> 当然、手持ち無し
    # NOTE: sold_at が埋まっている -> 売却済み -> 手持ち無し
    holds_this_stock = (not newest_trading['sold_at']
                        if newest_trading
                        else False)

    # 手持ちがなければ、有無を言わさず買います。
    if not holds_this_stock:
        # NOTE: 買うということは trading に一件追加するということです。
        with utils.DbClient() as db_client:
            db_client.create_trading(
                stock_id=stock_id,
                user_id=1,
                price=current_stock_price,
            )
        return dict(message=f'現在の価格:{current_stock_price}, 買付しました。')

    # この stock の手持ちがある場合は、売るかどうかの判断に進みます。
    # 売るのは、利確ラインを超えているとき、あるいは損切ラインを下回っているときです。
    buy_price = newest_trading['buy']
    profit_booking_price = (buy_price + buy_price * profit_booking_rate)
    loss_cut_price = (buy_price - buy_price * loss_cut_rate)
    message = (
        f'利確:{profit_booking_price},'
        f'損切:{loss_cut_price},'
        f'現在の価格:{current_stock_price}')
    if (current_stock_price >= profit_booking_price
            or current_stock_price <= loss_cut_price):
        # NOTE: 売るということは trading.sell を埋めるということです。
        with utils.DbClient() as db_client:
            db_client.update_trading(
                trading_id=newest_trading['id'],
                sell_price=current_stock_price,
            )
        return dict(message=f'{message}, 売付しました。')
    return dict(message=f'{message}, 売付しません。')


if __name__ == '__main__':
    # 損切ライン算出のテストです。
    # 利確ライン5% 勝率50% なら 損切ライン4.7% で「機械割」100% をこえます。
    print(
        Decimal('0.047') == get_loss_cut_rate(Decimal('0.05'), Decimal('0.5')))
    # 利確ライン3% 勝率50% なら 損切ライン2.9% で「機械割」100% をこえます。
    print(
        Decimal('0.029') == get_loss_cut_rate(Decimal('0.03'), Decimal('0.5')))
    # 利確ライン2.5% 勝率50% なら 損切ライン2.4% で「機械割」100% をこえます。
    print(
        Decimal('0.024') == get_loss_cut_rate(Decimal('0.025'), Decimal('0.5')))

    # 株価スクレイピングのテストです。
    print(
        '株価スクレイピングテスト:'
        ' stock_code->1357'
        f' data_price->{get_current_stock_price("1357")}'
    )

    # market_is_open の動作確認です。
    print('現在、市場は開いている:', market_is_open())
