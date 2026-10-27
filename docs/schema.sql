-- Shuumulator が読み書きするテーブルです。
-- NOTE: 本番 DB のスキーマは ShuumulatorApi 側が管理しています。
--       これは本リポジトリの SQL から推定した、ローカル検証用の最小スキーマです。
--       型の桁数やインデックスは本番と一致する保証がありません。
-- NOTE: 日時カラムはすべて UTC (タイムゾーンなし) で保存します。

CREATE TABLE stock (
    id INT NOT NULL AUTO_INCREMENT,
    code VARCHAR(16) NOT NULL,
    name VARCHAR(255) NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE trading (
    id INT NOT NULL AUTO_INCREMENT,
    stock_id INT NOT NULL,
    user_id INT NOT NULL,
    buy DECIMAL(12, 2) NOT NULL,
    bought_at DATETIME(6) NOT NULL,
    sell DECIMAL(12, 2) NULL,
    sold_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    KEY trading_stock_user_created (stock_id, user_id, created_at),
    CONSTRAINT trading_stock_fk FOREIGN KEY (stock_id) REFERENCES stock (id)
);

CREATE TABLE stock_log (
    id INT NOT NULL AUTO_INCREMENT,
    stock_id INT NOT NULL,
    price DECIMAL(12, 2) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT stock_log_stock_fk FOREIGN KEY (stock_id) REFERENCES stock (id)
);
