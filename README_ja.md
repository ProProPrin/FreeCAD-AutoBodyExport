# Auto Body Export

[English](README.md)

Auto Body Exportは、FreeCADドキュメントの保存後に、選択した
`PartDesign::Body` と `App::Part` 内の独立した形状オブジェクトを
STEP、STL、または両方へ出力する拡張機能です。

![出力対象選択ダイアログ](https://raw.githubusercontent.com/ProProPrin/FreeCAD-AutoBodyExport/main/docs/images/selection-dialog-ja.png)

このREADMEのスクリーンショットは、実際のFreeCAD 1.1のQt画面から直接取得
したもので、AI生成画像ではありません。

## 主な機能

- ドキュメントの保存成功後にSTEP、STL、または両方を出力
- 全体設定とドキュメント設定による明示的な二段階opt-in
- `.FCStd` ファイルごとに出力対象とグループを保存
- 同じ `App::Part` 内の複数対象を1ファイルへグループ出力
- 全メンバーの形状を検証してからグループファイルを作成
- ファイル名衝突を回避し、アドオン管理外の既存ファイルを保護
- 置換前と不要になった管理ファイルを世代数上限付きで履歴保存
- 形状と出力設定が未変更の場合に再出力を省略
- 出力先、ファイル名テンプレート、STL精度、進捗表示を設定可能
- アドオン固有UIの英語・日本語表示

## 動作要件

- FreeCAD 1.0以降
- 対応FreeCADに同梱されるPython 3.11以降
- `.FCStd` のパスへ保存済みのドキュメント

自動テストはFreeCAD 1.0と1.1を対象としています。Windowsで実機確認し、
CIでも公式Windows buildを使って同じcoreテストを実行します。

## インストール

### 手動インストール

1. FreeCADのPython consoleで次を実行します。

   ```python
   FreeCAD.getUserAppDataDir()
   ```

2. FreeCADを終了します。
3. 表示されたパス内の `Mod` ディレクトリへ、このリポジトリをcloneまたは
   展開します。配置先ディレクトリ名は `AutoBodyExport` とします。
4. FreeCADを再起動します。

一般的なWindows環境の例:

```powershell
git clone https://github.com/ProProPrin/FreeCAD-AutoBodyExport.git `
  "$env:APPDATA\FreeCAD\Mod\AutoBodyExport"
```

配置先の直下に `Init.py`、`InitGui.py`、`package.xml` があることを
確認してください。

## クイックスタート

1. **Edit > Preferences > Auto Body Export** を開きます。
2. **Auto Body Exportを全体で有効にする** を有効にし、出力形式を選びます。
3. ドキュメントを開くか作成し、`.FCStd` として保存します。
4. 選択ダイアログで、このドキュメントの自動出力を有効のままにします。
5. 出力するBodyとPart内の独立オブジェクトを選択します。
6. 同じ `App::Part` 内の対象をまとめる場合は **グループ** 列を使います。
7. **OK** を選択します。

初期状態では無効です。GUIからドキュメントをopt-inするまで自動出力は
開始しません。ダイアログのキャンセルは、その保存時の出力だけを中止します。

## 出力対象とグループ

次のオブジェクトを対象にします。

- `App::Part` の外にあるものを含む `PartDesign::Body`
- `App::Part` 直下にあり、Shapeを持つ独立オブジェクト
- Bodyに含まれるFeatureは独立対象にせず、Bodyと一緒に出力

グループ化できるのは、同じ直接親Partを持つ対象だけです。すべてのメンバーが
存在し、空でないShapeを持つ場合にだけグループファイルを作成します。
独立オブジェクトだけのグループには安定したhash suffixを付けるため、
複数グループが同名になることはありません。

## 出力動作

既定の出力先では、`assembly.FCStd` に対して次の構成になります。

```text
assembly.FCStd
step/
  assembly_Frame_Main Body.step
  old_versions/
    v0/
      assembly_Frame_Main Body_v0.step
stl/
  assembly_Frame_Main Body.stl
```

最新ファイルは通常名を維持します。置換時には、以前の管理ファイルを次の
`old_versions/vN/` へ移動します。履歴は設定した世代数まで自動整理され、
`0` の場合は履歴を残さず置換します。

対象の選択解除、名称変更、削除、再グループ化、形式の無効化で不要になった
管理ファイルは、出力処理全体が成功した後にだけ履歴へ移動します。アドオンが
作成していない既存ファイルは上書きせず、新しい出力側へ安定したhash suffixを
追加します。

共通出力先を使う場合、ドキュメントごとに `assembly_a1b2c3d4/` のような
サブディレクトリを作ります。hashは元ドキュメントのディレクトリから生成する
ため、別プロジェクトにある同名CADファイル同士が衝突しません。

## ファイル名テンプレート

既定値:

```text
{document}_{part}_{target}
```

利用可能なフィールド:

| フィールド | 内容 |
| --- | --- |
| `{document}` | 拡張子を除いた `.FCStd` ファイル名 |
| `{part}` | 直接親PartのLabel |
| `{target}` | BodyのLabelまたはグループ化したBodyのLabel |
| `{name}` | FreeCAD内部のオブジェクト名 |

ファイルシステムで使えない文字とWindows予約名は自動的に置換します。長い
名前は安定したhash付きで短縮し、変換後に重複した名前にもhashを追加します。

## 設定

**Edit > Preferences > Auto Body Export** で次を設定できます。

- 表示言語（FreeCADの設定に従う、英語、日本語）
- アドオン全体の有効・無効
- STEPとSTLの出力
- 各ドキュメントの隣または共通ディレクトリへの出力
- ファイル名テンプレートと履歴世代数
- 未変更時の省略と進捗表示
- STLの線形偏差と角度偏差
- 保存ごとに選択ダイアログを表示するか
- 既知のCADファイルごとの有効状態、選択数、管理ファイル数

![Auto Body Export設定](https://raw.githubusercontent.com/ProProPrin/FreeCAD-AutoBodyExport/main/docs/images/preferences-ja.png)

通常時のダイアログを無効にしても、新しいPart、Body、独立オブジェクトを
検出した場合は再表示します。初回ダイアログで無効にしたドキュメントは、
Preferencesの保存済みドキュメント一覧から再び有効にできます。

## 安全設計

- 全体とドキュメントの両方が有効な場合だけ出力
- このアドオンが生成したと記録しているファイルだけを履歴移動・削除
- 管理対象パスは記録済み出力root直下のSTEP/STLファイルに限定
- 一時ファイルへの出力成功後に最新ファイルを置換
- 出力や不要ファイル整理に失敗した場合は既存管理ファイルを追跡し続ける
- テストは専用のFreeCAD parameter namespaceを使い、実ユーザー設定を変更しない

重要なCADデータは別途backupしてください。本アドオンはファイル書き込みを
自動化しますが、プロジェクトbackupの代わりにはなりません。

## テスト

公開用metadataとPython構文を検証します。

```powershell
python tests\validate_release.py
```

FreeCAD 1.0と1.1でcoreテストを実行します。

```powershell
$env:AUTOBODYEXPORT_TEST_TMP = "C:\tmp\autobodyexport-tests"
& "C:\Program Files\FreeCAD 1.0\bin\freecadcmd.exe" tests\run_tests.py
& "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" tests\run_tests.py
```

失敗時はtest runnerがnonzeroで終了します。GitHub Actionsではrelease検証、
Ruff、公式FreeCAD 1.0.2・1.1.1によるcoreテストを実行します。

## トラブルシューティング

- **出力されない:** 全体設定とドキュメント設定を有効にし、`.FCStd` へ保存し、
  出力形式と対象を1つ以上選択してください。
- **Preferencesに表示されない:** `FreeCAD.getUserAppDataDir()` が示す場所の
  `Mod` 内に配置されていることを確認し、FreeCADを再起動してください。
- **対象が表示されない:** 独立オブジェクトはShapeを持ち、`App::Part` 直下に
  ある必要があります。Body内のFeatureはBodyと一緒に出力します。
- **ファイル名にhashが付く:** 名前の重複、長すぎる名前、または同名の
  管理外ファイルが存在しています。
- **グループが出力されない:** FreeCADのReport viewを確認してください。
  メンバーが削除済み、またはShapeが空の可能性があります。

## Contributionとsecurity

開発とテスト方法は [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。
脆弱性の疑いは [SECURITY.md](SECURITY.md) に従って非公開で報告してください。

## ライセンス

[MIT](LICENSE)
