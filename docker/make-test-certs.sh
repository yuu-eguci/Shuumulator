#!/bin/sh
# テスト用の CA とサーバ証明書を作ります。有効期限まで 1 日以上あれば作り直しません。
# NOTE: 使い捨ての MySQL 用です。本番では使わないでください。
# NOTE: 証明書はボリュームに残ります。作り直したら MySQL も起動し直してください (docker compose down)。
set -eu

dir="$1"
if [ -f "$dir/server-cert.pem" ] && openssl x509 -checkend 86400 -noout -in "$dir/server-cert.pem"; then
    exit 0
fi
cd "$dir"

# MySQL のサーバ証明書を署名する CA です。
openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj '/CN=Shuumulator Test CA' \
    -keyout ca-key.pem -out ca.pem
# サーバ証明書とは無関係な CA です。検証に失敗することを確かめるために使います。
openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj '/CN=Shuumulator Other CA' \
    -keyout other-ca-key.pem -out other-ca.pem

# compose のサービス名 mysql をホスト名として持つサーバ証明書です。
openssl req -newkey rsa:2048 -nodes -subj '/CN=mysql' -keyout server-key.pem -out server.csr
printf 'subjectAltName=DNS:mysql\n' > server-ext.cnf
openssl x509 -req -days 30 -in server.csr -CA ca.pem -CAkey ca-key.pem -CAcreateserial \
    -extfile server-ext.cnf -out server-cert.pem

rm -f ca-key.pem other-ca-key.pem server.csr server-ext.cnf ca.srl
# NOTE: MySQL コンテナの mysql ユーザが読めるようにします。テスト用なので鍵も 644 にしています。
chmod 644 ./*.pem
