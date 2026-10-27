from datetime import datetime
from decimal import Decimal

import pytest

import functions

PROFIT = Decimal('0.025')
LOSS = Decimal('0.024')


@pytest.mark.parametrize(('profit', 'wins', 'expected'), [
    # NOTE: もともと functions.py の __main__ で確認していた値です。
    ('0.05', '0.5', '0.047'),
    ('0.03', '0.5', '0.029'),
    ('0.025', '0.5', '0.024'),
    # 10.0% から探し始めるので、全勝なら 10% です。
    ('0.025', '1', '0.1'),
    ('0.025', '0.2', '0.006'),
    ('0.025', '0.04', '0.001'),
])
def test_loss_cut_rate_reference_values(profit, wins, expected):
    assert functions.get_loss_cut_rate(Decimal(profit), Decimal(wins)) == Decimal(expected)


@pytest.mark.parametrize('wins', ['0', '0.03'])
def test_loss_cut_rate_unavailable_for_too_low_win_rate(wins):
    with pytest.raises(functions.LossCutRateUnavailableError):
        functions.get_loss_cut_rate(PROFIT, Decimal(wins))


@pytest.mark.parametrize(('profit', 'wins'), [
    ('0.025', '-0.1'),
    ('0.025', '1.1'),
    ('0', '0.5'),
    ('-0.01', '0.5'),
])
def test_loss_cut_rate_rejects_invalid_input(profit, wins):
    with pytest.raises(ValueError):
        functions.get_loss_cut_rate(Decimal(profit), Decimal(wins))


def trade(buy, sell):
    return {'buy': Decimal(buy), 'sell': Decimal(sell)}


@pytest.mark.parametrize(('buy', 'sell', 'expected'), [
    ('100', '101', True),
    ('100', '100', False),
    ('100', '99', False),
])
def test_is_win(buy, sell, expected):
    assert functions.is_win(trade(buy, sell)) is expected


def test_wins_rate_is_half_without_trades():
    assert functions.calculate_wins_rate([]) == Decimal('0.5')


def test_draw_counts_as_trade_but_not_as_win():
    tradings = [trade('100', '101'), trade('100', '100'), trade('100', '99'), trade('100', '120')]

    assert functions.calculate_wins_rate(tradings) == Decimal('0.5')


def held(buy='1000'):
    return {'id': 7, 'buy': None if buy is None else Decimal(buy), 'sold_at': None}


def test_buys_when_never_traded():
    assert functions.decide(None, Decimal('1000'), PROFIT, LOSS)['action'] == 'buy'


def test_buys_again_after_selling():
    sold = dict(held(), sell=Decimal('1030'), sold_at=datetime(2026, 10, 27, 1, 0))

    assert functions.decide(sold, Decimal('1000'), PROFIT, LOSS)['action'] == 'buy'


@pytest.mark.parametrize(('price', 'action'), [
    # 利確ライン 1000 * 1.025 = 1025
    ('1025', 'sell'),
    ('1025.01', 'sell'),
    ('1024.99', 'keep'),
    # 損切ライン 1000 * (1 - 0.024) = 976
    ('976', 'sell'),
    ('975', 'sell'),
    ('976.01', 'keep'),
    ('1000', 'keep'),
])
def test_sells_at_or_beyond_lines_otherwise_keeps(price, action):
    assert functions.decide(held(), Decimal(price), PROFIT, LOSS)['action'] == action


@pytest.mark.parametrize('buy', [None, '0', '-1'])
def test_held_trading_with_invalid_buy_price_is_bad_data(buy):
    with pytest.raises(functions.StockDataError):
        functions.decide(held(buy), Decimal('1000'), PROFIT, LOSS)
