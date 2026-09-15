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

なお Colmi R02 のリアルタイム取得 API は個々の心拍（拍動）ごとの RR インターバルではなく、約1秒間隔の bpm サンプルを返す仕様のため、`HeartBeatToggle` / `isHRBeat` は実際の1拍ごとではなく「新しい bpm サンプルを受信するたび」に発火する近似的な動作になります。

## セットアップ

### 1. インストール

Python 3.11 以上 3.14 未満が必要です（依存する `colmi_r02_client` の制約）。Windows で `py --list` を実行して該当バージョンが無い場合は [python.org](https://www.python.org/downloads/) からインストールしてください（インストーラーの "Add python.exe to PATH" にチェックを入れてください）。

```bash
pip install -e .
```

`-e`（editable install）を付けてください。付けずに `pip install .` すると、その時点のソースコードが Python の `site-packages` にコピーされるため、後で `git pull` してもインストール済みのコードには反映されず、修正が効いていないように見えてしまいます。`-e` を付けておけば、リポジトリのソースを直接参照するようになるので、`git pull` するだけで最新のコードがすぐ使われるようになります。

（すでに `-e` 無しでインストール済みの場合は、`git pull` のたびに `pip install .` を実行し直すか、一度 `pip install -e .` で入れ直してください）

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

実行中はリングを装着した状態にしてください。装着していない、または指がずれている場合は心拍値が取得できず、パラメータは最後に受信した値のまま更新されなくなります。

### 5. Windows でワンクリック起動する

リポジトリに `run.bat` を用意しています。

1. `run.bat` をテキストエディタで開き、`ADDRESS` を自分のリングのアドレスに、`PYVER` をインストールした Python のバージョン（`-3.11` など）に書き換えて保存する
2. ダブルクリックして起動することを確認する（コンソール画面にログが表示されます。閉じるには何かキーを押すかウィンドウを閉じてください）
3. 問題なければ `run.bat` を右クリック →「送る」→「デスクトップ（ショートカットを作成）」を選ぶと、デスクトップのアイコンをダブルクリックするだけで起動できるようになります

## 仕組み

Colmi R02 には心拍数を取るコマンドが実は2種類あり、`colmi_r02_client` 本体（および公式アプリの「今すぐ測定」）が使っているのはそのうち「単発のスポット測定」用のコマンド（`0x69`）でした。これは最大30秒ほど値を送ったら自動的に止まる設計で、VRChatに常時配信するような用途には向いていません。

本ツールは、[Gadgetbridge](https://codeberg.org/Freeyourgadget/Gadgetbridge) がこのリングの「ライブアクティビティ」表示のために実装している、本当の意味で連続ストリーミングするコマンド（`0x1e`）を直接叩いています（`src/colmi_r02_vrchat/ring.py`）。流れは以下の通りです。

1. `[0x1e, 0x01]` で連続測定を有効化
2. リングが概ね1秒おきに心拍値を通知してくる
3. リング側に60秒のセッションタイムアウトがあるため、20秒おきに `[0x1e, 0x03]`（continue）を送って延長し続ける
4. 終了時・切断時は `[0x1e, 0x02]` で無効化

BLE 接続が切れた場合は自動的に再接続を試みます。

なお `scripts/list_services.py` は、リングが公開している BLE の GATT サービス一覧を確認するための診断用スクリプトです（標準の Bluetooth Heart Rate Service には対応していないことをこの過程で確認済みです）。

## ライセンス

このリポジトリ自体にライセンスの指定はありません。利用している `colmi_r02_client` のライセンスは [本家リポジトリ](https://github.com/tahnok/colmi_r02_client) を参照してください。
