import importlib

import pytest

import consts
import utils

ENV = {
    'MYSQL_HOST': 'db.test',
    'MYSQL_USER': 'shuumulator',
    'MYSQL_PASSWORD': 'pw-sentinel',
    'MYSQL_DATABASE': 'shuumulator_db',
    'MYSQL_TLS': 'false',
}


def test_import_does_not_require_environment():
    # NOTE: conftest で MYSQL_* を消しています。それでも import できること。
    importlib.reload(consts)
    importlib.reload(utils)


def test_load_settings_reads_environment():
    settings = consts.load_settings(ENV)

    assert settings.mysql_host == 'db.test'
    assert settings.mysql_port == 3306
    assert settings.mysql_user == 'shuumulator'
    assert settings.mysql_password == 'pw-sentinel'
    assert settings.mysql_database == 'shuumulator_db'
    assert settings.mysql_tls is False
    assert settings.user_id == 1


def test_load_settings_reads_optional_values(tmp_path):
    ca = tmp_path / 'ca.pem'
    ca.write_text('dummy')
    env = dict(ENV, MYSQL_PORT='3307', MYSQL_TLS='TRUE', MYSQL_SSL_CA=str(ca),
               MYSQL_SSL_VERIFY_IDENTITY='false', SHUUMULATOR_USER_ID='2')

    settings = consts.load_settings(env)

    assert settings.mysql_port == 3307
    assert settings.mysql_tls is True
    assert settings.mysql_ssl_ca == str(ca)
    assert settings.mysql_ssl_verify_identity is False
    assert settings.user_id == 2


@pytest.mark.parametrize('name', ['MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE'])
def test_missing_variable_is_reported_without_values(name):
    env = dict(ENV)
    del env[name]

    with pytest.raises(consts.ConfigError) as e:
        consts.load_settings(env)

    assert name in str(e.value)
    assert 'pw-sentinel' not in str(e.value)


def test_empty_variable_counts_as_missing():
    with pytest.raises(consts.ConfigError, match='MYSQL_USER'):
        consts.load_settings(dict(ENV, MYSQL_USER=''))


def test_repr_hides_password():
    assert 'pw-sentinel' not in repr(consts.load_settings(ENV))


def test_tls_is_on_by_default_and_requires_ca():
    env = dict(ENV)
    del env['MYSQL_TLS']

    with pytest.raises(consts.ConfigError, match='MYSQL_SSL_CA'):
        consts.load_settings(env)


def test_tls_ca_must_exist(tmp_path):
    env = dict(ENV, MYSQL_TLS='true', MYSQL_SSL_CA=str(tmp_path / 'missing.pem'))

    with pytest.raises(consts.ConfigError, match='MYSQL_SSL_CA'):
        consts.load_settings(env)


@pytest.mark.parametrize(('name', 'value'), [
    ('MYSQL_TLS', 'yes'),
    ('MYSQL_SSL_VERIFY_IDENTITY', '1'),
    ('MYSQL_PORT', 'abc'),
    ('MYSQL_PORT', '0'),
    ('SHUUMULATOR_USER_ID', '0'),
    ('SHUUMULATOR_USER_ID', 'one'),
])
def test_invalid_values_are_rejected(name, value):
    with pytest.raises(consts.ConfigError, match=name):
        consts.load_settings(dict(ENV, **{name: value}))


def test_connection_config_disables_tls_explicitly():
    config = utils.get_connection_config(consts.load_settings(ENV))

    assert config['database'] == 'shuumulator_db'
    assert config['ssl_disabled'] is True
    assert 'ssl_ca' not in config


def test_connection_config_verifies_certificate_when_tls_is_on(tmp_path):
    ca = tmp_path / 'ca.pem'
    ca.write_text('dummy')
    settings = consts.load_settings(dict(ENV, MYSQL_TLS='true', MYSQL_SSL_CA=str(ca)))

    config = utils.get_connection_config(settings)

    # NOTE: ssl_verify_cert が False だと、 TLS 非対応のサーバに平文で接続してしまいます。
    assert config['ssl_disabled'] is False
    assert config['ssl_ca'] == str(ca)
    assert config['ssl_verify_cert'] is True
    assert config['ssl_verify_identity'] is True
