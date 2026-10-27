import csv
import io
from datetime import datetime
from decimal import Decimal

import functions
import main_2_aggregation


def trading(code, name, buy, sell):
    return {
        'code': code,
        'name': name,
        'buy': Decimal(buy),
        'bought_at': datetime(2026, 10, 27, 0, 30),
        'sell': Decimal(sell),
        'sold_at': datetime(2026, 10, 27, 5, 45),
    }


TRADINGS = [
    trading('1357', 'A', '100', '110'),
    trading('1570', 'B', '100', '100'),
    trading('9434', 'C', '100', '90'),
]


def test_summarize_counts_draws_separately():
    summary = main_2_aggregation.summarize(TRADINGS)

    assert summary['total_trades_len'] == 3
    assert summary['wins_len'] == 1
    assert summary['loses_len'] == 1
    assert summary['draws_len'] == 1
    assert summary['total_earning'] == Decimal('0')
    assert summary['total_gain'] == Decimal('10')
    assert summary['total_lost'] == Decimal('-10')


def test_summarize_win_rate_matches_trading_logic():
    summary = main_2_aggregation.summarize(TRADINGS)

    # NOTE: 損切ラインの算出に使う勝率と同じ定義であること。
    assert summary['win_rate'] == functions.calculate_wins_rate(TRADINGS)


def test_summarize_keeps_decimal_exact():
    tradings = [trading('1', 'A', '0.1', '0.2'), trading('2', 'B', '0.1', '0.3')]

    summary = main_2_aggregation.summarize(tradings)

    # NOTE: float だと 0.30000000000000004 になります。
    assert summary['total_earning'] == Decimal('0.3')


def test_write_report_outputs_quoted_csv_and_summary():
    tradings = [trading('1357', 'A, "quoted" name', '100', '110.5')]
    out = io.StringIO()

    main_2_aggregation.write_report(tradings, out)

    lines = out.getvalue().splitlines()
    assert lines[0] == ('"code","name","buy","bought_at","sell","sold_at",'
                        '"difference","difference_percentage"')
    [row] = list(csv.reader(lines[1:2]))
    assert row == ['1357', 'A, "quoted" name', '100', '2026-10-27T00:30:00Z',
                   '110.5', '2026-10-27T05:45:00Z', '10.5', '10.50']
    assert 'total_trades_len: 1' in lines
    assert 'wins_len: 1' in lines
    assert 'draws_len: 0' in lines
    assert 'total_earning: 10.5' in lines
