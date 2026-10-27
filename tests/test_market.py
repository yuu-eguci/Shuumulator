from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

import functions

JST = ZoneInfo('Asia/Tokyo')


def jst(*args):
    return datetime(*args, tzinfo=JST)


@pytest.mark.parametrize(('now', 'expected'), [
    # 2026-10-27 は火曜日です。
    (jst(2026, 10, 27, 8, 59), False),
    (jst(2026, 10, 27, 9, 0), True),
    (jst(2026, 10, 27, 11, 29, 59), True),
    (jst(2026, 10, 27, 11, 30), False),
    (jst(2026, 10, 27, 12, 29), False),
    (jst(2026, 10, 27, 12, 30), True),
    (jst(2026, 10, 27, 15, 29, 59), True),
    (jst(2026, 10, 27, 15, 30), False),
    (jst(2026, 10, 27, 16, 0), False),
    # 土日。
    (jst(2026, 10, 31, 10, 0), False),
    (jst(2026, 11, 1, 10, 0), False),
    # 祝日とその間の休日。
    (jst(2026, 9, 21, 10, 0), False),
    (jst(2026, 9, 22, 10, 0), False),
    (jst(2026, 9, 24, 10, 0), True),
    # 年末年始。
    (jst(2026, 12, 30, 10, 0), True),
    (jst(2026, 12, 31, 10, 0), False),
    (jst(2027, 1, 1, 10, 0), False),
    (jst(2027, 1, 4, 10, 0), True),
    # 振替休日。
    (jst(2027, 3, 22, 10, 0), False),
])
def test_market_is_open(now, expected):
    assert functions.market_is_open(now) is expected


def test_market_is_open_converts_to_jst():
    # UTC 0:00 は JST 9:00、 UTC 6:30 は JST 15:30 です。
    assert functions.market_is_open(datetime(2026, 10, 27, 0, 0, tzinfo=UTC)) is True
    assert functions.market_is_open(datetime(2026, 10, 27, 6, 30, tzinfo=UTC)) is False


def test_market_is_open_rejects_naive_datetime():
    with pytest.raises(ValueError):
        functions.market_is_open(datetime(2026, 10, 27, 10, 0))


def test_market_is_open_refuses_to_guess_for_uncovered_year():
    with pytest.raises(functions.CalendarNotCoveredError, match='2028'):
        functions.market_is_open(jst(2028, 1, 4, 10, 0))


def test_bundled_holidays_match_jpx_calendar():
    holidays = functions.load_tse_holidays()

    assert holidays.years == {2026, 2027}
    assert len(holidays.dates) == 41
    assert date(2026, 9, 22) in holidays.dates


def test_load_tse_holidays_from_file(tmp_path):
    path = tmp_path / 'holidays.csv'
    path.write_text('# comment\ndate,name\n2030-02-11,National Foundation Day\n', encoding='utf-8')

    holidays = functions.load_tse_holidays(path)

    assert holidays.years == {2030}
    assert holidays.dates == {date(2030, 2, 11)}
    assert functions.market_is_open(jst(2030, 2, 12, 10, 0), holidays) is True
    assert functions.market_is_open(jst(2030, 2, 11, 10, 0), holidays) is False
