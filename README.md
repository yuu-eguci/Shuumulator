Shuumulator
===

株の売買を固定の利確・損切ルールでシミュレーションするプログラム。
実際の売買注文は出さない。

- Docker: 対応!
- Python: 3.14.10
- Linter: ruff
- Test: pytest

## パッと実行してみたい

固定データと使い捨ての MySQL で lint とテストを実行する。

```bash
docker compose run --rm --build test
docker compose down
```

通常のコマンドは `--execute` を付けない限り、DB 接続や価格取得を行わない。

- [yuu-eguci/Shuumulator](https://github.com/yuu-eguci/Shuumulator)
- [yuu-eguci/ShuumulatorWeb](https://github.com/yuu-eguci/ShuumulatorWeb)
- [yuu-eguci/ShuumulatorApi](https://github.com/yuu-eguci/ShuumulatorApi)

![shuumulator](https://user-images.githubusercontent.com/28250432/122638209-ee7f8480-d12d-11eb-9ccc-e0f7c0ca9be1.png)

## Description

![readme](https://user-images.githubusercontent.com/28250432/109735015-518fee80-7c05-11eb-89a0-1c275fe81594.png)

- いんたーねっとから現在株価を取得
- その価格をでーたべーすに保存 (買付を表す) 

Hours later...

- いんたーねっとから現在株価を取得
- でーたべーすに保存した価格から「けっこう上がった」「けっこう下がった」ら、でーたべーすに現在価格を保存 (売付を表す) 
- 「けっこう」の基準は Mr.S (友達) の考えたロジックを使う

以上の処理を取引時間中に定期実行 (cron など) する。するとでーたべーすにこんなの↓が貯まる。

| 株    | 買った     | 売った     | 差額         |
| ----: | ---------: | ---------: | -----------: |
| A     | xxx yen    | xxx yen    | xxx yen      |
| B     | xxx yen    | xxx yen    | - xxx yen    |

## Purpose

- てきとうに買って、勝率が5割になるのか確認
- Mr.S のロジックは収支がプラマイゼロになることを意図している。そうなるのか確認

## How to check it out

![1](https://user-images.githubusercontent.com/28250432/109736652-0c20f080-7c08-11eb-9303-fcb2ce425e3e.png)

![2](https://user-images.githubusercontent.com/28250432/109736661-0d521d80-7c08-11eb-85db-c1c5e76b1b38.png)

![3](https://user-images.githubusercontent.com/28250432/109736667-0e834a80-7c08-11eb-85a0-3dd3caa345dc.png)

![4](https://user-images.githubusercontent.com/28250432/109736673-0f1be100-7c08-11eb-8dc6-67296ea83c44.png)

![5](https://user-images.githubusercontent.com/28250432/109736677-104d0e00-7c08-11eb-9040-a1f539327da5.png)

## How it works

動作する様子。

![shuumulator-screen-shot1](https://user-images.githubusercontent.com/28250432/109889788-5f0eac80-7cc9-11eb-9c54-cb2c6ab54070.png)

![shuumulator-screen-shot2](https://user-images.githubusercontent.com/28250432/109889791-5fa74300-7cc9-11eb-815e-f5855ad1dfbe.png)

## Rules

- 銘柄を持っていなければ買う。持っていれば「買値 × (1 + 利確ライン)」以上、または「買値 × (1 - 損切ライン)」以下で売る。それ以外はキープ。
- 利確ラインは 2.5% 固定 (`consts.PROFIT_BOOKING_RATE`)。
- 損切ラインは Mr.S の式 `100 * ((1 + 利確)^勝率 * (1 - 損切)^(100 - 勝率))^0.01 >= 100` を満たす最大の値を 10.0% → 0.1% の 0.1% 刻みで探す。
- 勝ちは「売値 > 買値」だけ。同値は引き分けで、勝率の分母には入る。売買も集計もこの定義。完了した取引がないときの勝率は 50%。
- 勝率が低すぎて (利確 2.5% なら約 4% 未満) 損切ラインが見つからないときは、式を変えずに実行を中止する。DB には何も書かず終了コード 1。
- 1 銘柄ずつ別トランザクション。株価の取得失敗・ページの形が想定外・価格がおかしい・DB エラーの銘柄はロールバックしてスキップし、ほかの銘柄は続ける。失敗が 1 件でもあれば終了コード 1。
- 同じ DB・同じユーザで実行が重なったら、あとから来たほうは何もせず終了コード 1 (MySQL の `GET_LOCK` を使う)。二重に買わないため。

## Market hours

[JPX の公表](https://www.jpx.co.jp/english/equities/trading/domestic/01.html) どおり、東証の立会時間 (前場 9:00-11:30、後場 12:30-15:30 JST) だけを「開いている」とする。土日、祝日、12/31、1/1-1/3 は休み。

- 休業日は [JPX のカレンダー](https://www.jpx.co.jp/english/corporate/about-jpx/calendar/index.html) を `data/tse_holidays.csv` に写したもの。いまは 2026 年と 2027 年だけ。
- CSV に載っていない年は判定せず、エラーで終了する (終了コード 1)。年が変わる前に追記してね。
- 臨時休場やシステム障害による停止は反映されない。
- 取得する株価がリアルタイムか遅延かは未確認。

## Configuration

`.env.example` を `.env` にコピーして埋める。`.env` は `--execute` 付きで実行したときだけ、カレントディレクトリのものを読む (親ディレクトリはさかのぼらない)。環境変数が設定済みならそちらが優先。

| 変数 | 既定値 | 説明 |
| --- | --- | --- |
| `MYSQL_HOST` | (必須) | |
| `MYSQL_PORT` | `3306` | |
| `MYSQL_USER` | (必須) | |
| `MYSQL_PASSWORD` | (必須) | |
| `MYSQL_DATABASE` | (必須) | すべてのテーブルをこの DB から読み書きする |
| `MYSQL_TLS` | `true` | `true` のときは `MYSQL_SSL_CA` 必須。証明書を検証できなければ接続しない |
| `MYSQL_SSL_CA` | なし | CA 証明書 (PEM) のパス |
| `MYSQL_SSL_VERIFY_IDENTITY` | `true` | 証明書のホスト名も検証する |
| `SHUUMULATOR_USER_ID` | `1` | 売買を記録するユーザ (`trading.user_id`) |

テーブル定義は `docs/schema.sql` (本リポジトリの SQL から推定したもの。本番のスキーマは ShuumulatorApi が管理)。

## Usage

DB への書き込みやスクレイピングをするコマンドは `--execute` を付けたときだけ動く。付けなければ何もせず終了コード 2。

```bash
# 売買シミュレーション。
python main.py --execute

# 東証が開いているときだけ main.py を実行。cron から 1 時間ごとに呼ぶ想定。
python execute_main_if_market_is_open.py --execute

# 売付まで済んだ取引を CSV と集計で表示 (読み取りのみ)。
python main_2_aggregation.py --execute
```

## Development

Python 3.14。依存は `Pipfile.lock` (ハッシュ付き) で固定している。

```bash
# lint とテスト。使い捨ての MySQL を立てて、インターネットにつながらないネットワークで動かします。
docker compose run --rm --build test
docker compose down

# 依存の脆弱性チェック (PyPI の脆弱性 DB に問い合わせます)。
docker compose run --rm --build audit
```

テストは固定の HTML、モックした HTTP、使い捨ての MySQL だけを使います。本番 DB や実サイトにはアクセスしない。CI (`.github/workflows/test.yml`) も同じコマンド。
