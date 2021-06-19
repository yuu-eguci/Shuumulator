Shuumulator
===

📈 Shuumulator project contains a program which continuously simulates stock trading with solid logic, a web page of Vue.js and a web application of Django. To tell the outline of the logic, it comes that if you trade following specified profit rate and loss rate, your total profit will become zero. It doesn't expect money; it is the trading for play.

- [yuu-eguci/Shuumulator](https://github.com/yuu-eguci/Shuumulator)
- [yuu-eguci/ShuumulatorWeb](https://github.com/yuu-eguci/ShuumulatorWeb)
- [yuu-eguci/ShuumulatorApi](https://github.com/yuu-eguci/ShuumulatorApi)

![shuumulator](https://user-images.githubusercontent.com/28250432/122638209-ee7f8480-d12d-11eb-9ccc-e0f7c0ca9be1.png)

## Description

![readme](https://user-images.githubusercontent.com/28250432/109735015-518fee80-7c05-11eb-89a0-1c275fe81594.png)

- いんたーねっとから現在株価を取得
- その価格をでーたべーすに保存(買付を表す)

Hours later...

- いんたーねっとから現在株価を取得
- でーたべーすに保存した価格から「けっこう上がった」「けっこう下がった」ら、でーたべーすに現在価格を保存(売付を表す)
- 「けっこう」の基準は Mr.S(友達)の考えたロジックを使う

以上の処理が GitHub Actions で常時回っています。するとでーたべーすにこんなの↓が貯まる。

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

動作する様子です。

![shuumulator-screen-shot1](https://user-images.githubusercontent.com/28250432/109889788-5f0eac80-7cc9-11eb-9c54-cb2c6ab54070.png)

![shuumulator-screen-shot2](https://user-images.githubusercontent.com/28250432/109889791-5fa74300-7cc9-11eb-815e-f5855ad1dfbe.png)

## Installation

Create .env file. But no one can use this program but I, because you need to know the database structure.

```env
MYSQL_HOST='xxxx'
MYSQL_USER='xxxx'
MYSQL_PASSWORD='xxxx'
MYSQL_DATABASE='xxxx'
SLACK_BOT_TOKEN='xxxx'
SLACK_MESSAGE_CHANNEL='xxxx'
```

```bash
pipenv install
pipenv shell

# Simulate trading.
python main.py

# Aggregate tradings.
python main_2_aggregation.py
```

