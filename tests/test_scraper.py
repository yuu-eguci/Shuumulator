from decimal import Decimal
from pathlib import Path

import pytest
import requests
from helpers import FakeResponse, FakeSession

import functions

PAGE = (Path(__file__).parent / 'fixtures' / 'minkabu_stock.html').read_text(encoding='utf-8')


def session_for(code, response):
    return FakeSession({f'https://minkabu.jp/stock/{code}': response})


def page_with(attributes):
    return f'<html><body><div id="stock-for-securities-company" {attributes}></div></body></html>'


def test_reads_price_and_short_name():
    session = session_for('1357', FakeResponse(200, PAGE))

    result = functions.get_current_stock_price('1357', session=session)

    assert result == {'data_price': Decimal('1443.5'), 'data_short_name': '日経ダブルインバース'}
    [(url, timeout)] = session.calls
    assert url == 'https://minkabu.jp/stock/1357'
    assert timeout is not None


def test_accepts_alphanumeric_code():
    session = session_for('130A', FakeResponse(200, PAGE))

    assert functions.get_current_stock_price('130A', session=session)['data_price'] == Decimal('1443.5')


@pytest.mark.parametrize('code', ['', '13570', '135', '../1357', '1357?x=1', '1357/', 'abcd', None])
def test_rejects_invalid_code_without_request(code):
    session = FakeSession()

    with pytest.raises(functions.StockDataError):
        functions.get_current_stock_price(code, session=session)

    assert session.calls == []


def test_non_200_is_bad_data():
    with pytest.raises(functions.StockDataError, match='503'):
        functions.get_current_stock_price('1357', session=session_for('1357', FakeResponse(503, PAGE)))


def test_network_error_is_bad_data():
    session = FakeSession(error=requests.Timeout('timed out'))

    with pytest.raises(functions.StockDataError):
        functions.get_current_stock_price('1357', session=session)


@pytest.mark.parametrize('html', [
    '<html><body>no element</body></html>',
    page_with('data-short-name="X"'),
    page_with('data-price="1443.5"'),
    page_with('data-price="" data-short-name="X"'),
    page_with('data-price="abc" data-short-name="X"'),
    page_with('data-price="1,443" data-short-name="X"'),
    page_with('data-price="0" data-short-name="X"'),
    page_with('data-price="-5" data-short-name="X"'),
    page_with('data-price="NaN" data-short-name="X"'),
    page_with('data-price="Infinity" data-short-name="X"'),
])
def test_unexpected_page_is_bad_data(html):
    with pytest.raises(functions.StockDataError):
        functions.get_current_stock_price('1357', session=session_for('1357', FakeResponse(200, html)))
