# colmi_r02_vrchat

[Colmi R02](https://github.com/tahnok/colmi_r02_client) スマートリングからリアルタイムの心拍数を取得し、OSC 経由で VRChat のアバターに配信するツールです。

内部では [tahnok/colmi_r02_client](https://github.com/tahnok/colmi_r02_client) を BLE クライアントとして利用し、[python-osc](https://github.com/attwad/python-osc) で VRChat に OSC メッセージを送信します。

## 送信する OSC パラメータ

[iron-heart](https://github.com/nullstalgia/iron-heart) と、それに合わせている [HeartOSC](https://github.com/hizkifw/HeartOSC) のデフォルトパラメータ規約に合わせています。[PIXEL PULSE](https://pixelpulse.nsuke5.workers.dev/) をはじめ、iron-heart / HeartOSC 対応をうたっているアバターギミックにそのまま使えます。

| パラメータ | 型 | 範囲 | 用途 |
| --- | --- | --- | --- |
| `isHRConnected` | Bool | - | リングと BLE 接続中かどうか |
| `HeartBeatToggle` | Bool | - | 新しい心拍値を受信するたびに true/false が反転 |
| `isHRBeat` | Bool | - | 新しい心拍値を受信すると一定時間 (デフォルト0.1秒) true になるパルス |
| `HR` | Int | 0 〜 255 | 心拍数（bpm） |
| `floatHR` | Float | -1 〜 1 (0-255bpm) | 心拍数の正規化値 |

なお Colmi R02 のリアルタイム取得 API は個々の心拍（拍動）ではなく一定間隔で平均化された bpm 値を返す仕様のため、`HeartBeatToggle` / `isHRBeat` は実際の1拍ごとではなく「新しい bpm サンプルを受信するたび」に発火する近似的な動作になります。

## セットアップ

### 1. インストール

Python 3.10 以上が必要です。

```bash
pip install .
```

(Bluetooth を使うため Linux では BlueZ、macOS/Windows は OS 標準の Bluetooth スタックが必要です。詳細は [bleak](https://github.com/hbldh/bleak) を参照してください。)

### 2. リングの Bluetooth アドレスを調べる

`colmi_r02_client` に付属のユーティリティでスキャンします。

```bash
colmi_r02_util scan
```

リングをペアリングモード（充電器に乗せる、またはボタン操作でウェイクさせる）にしてから実行すると、`XX:XX:XX:XX:XX:XX` 形式のアドレスが表示されます。

### 3. VRChat 側で OSC を有効化する

VRChat 内の Action Menu → Options → OSC → Enabled をオンにしてください。デフォルトでは `127.0.0.1:9000` で OSC メッセージを待ち受けます。

アバター側には上記のパラメータ（必要なものだけで構いません）を Bool / Int / Float として Expression Parameters に追加し、Animator でそれらを使ってシェーダーやアニメーションを駆動してください。PIXEL PULSE など iron-heart 対応済みのアバターギミックを使う場合は、ギミック側の説明に従ってパラメータを設定するだけで動作します。

### 4. 実行

```bash
colmi-r02-vrchat --address XX:XX:XX:XX:XX:XX
```

主なオプション:

- `--osc-ip` : VRChat が OSC を待ち受けているアドレス（デフォルト: `127.0.0.1`）
- `--osc-port` : VRChat の OSC 受信ポート（デフォルト: `9000`）
- `--reconnect-delay` : リングとの接続が切れた際の再接続待機秒数（デフォルト: `5`）
- `--debug` : デバッグログを有効化

実行中はリングを装着した状態にしてください。装着していない、または指がずれている場合は心拍値が取得できず `isHRActive` が false のままになります。

## 仕組み

`colmi_r02_client.Client.get_realtime_reading()` は「開始パケットを送り、有効な心拍値が最大6件たまるか約40秒経過するまで待って、停止パケットを送る」という1回きりのバッチ取得です。本ツールはこれを接続が続く限りループで呼び出し続けることで、擬似的な連続ストリームとして扱っています（`src/colmi_r02_vrchat/ring.py`）。BLE 接続が切れた場合は自動的に再接続を試みます。

## ライセンス

このリポジトリ自体にライセンスの指定はありません。利用している `colmi_r02_client` のライセンスは [本家リポジトリ](https://github.com/tahnok/colmi_r02_client) を参照してください。
