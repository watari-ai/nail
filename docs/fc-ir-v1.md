# fc_ir_v1 — NAIL Tool-Calling IR 正式仕様書

**仕様バージョン**: v0.9（凍結候補）  
**ステータス**: Draft — Boss最終レビュー待ち (Issue #88)  
**作成日**: 2026-02-25  
**対象 NAIL バージョン**: 0.9.x

---

## 凍結宣言

本仕様書は NAIL v0.9 において **fc_ir_v1** を凍結するためのリファレンスドキュメントである。

凍結後は以下のルールが適用される:

- `kind: "fc_ir_v1"` の意味論は変更禁止
- 既存フィールドの削除・型変更は禁止
- 後方互換を壊す追加変更は禁止
- 将来の非互換変更は `fc_ir_v2` として新バージョンで定義する

任意フィールド (`annotations`) は後方互換を保証した上で拡張可能とする。

---

## 目次

1. [Scope](#1-scope)
2. [Canonicalization](#2-canonicalization)
3. [ToolDef Schema](#3-tooldef-schema)
4. [Name Sanitization](#4-name-sanitization)
5. [Type Subset](#5-type-subset)
6. [Effects Representation](#6-effects-representation)
7. [Provider Mapping](#7-provider-mapping)
8. [Diagnostics](#8-diagnostics)

---

## 1. Scope

### fc_ir_v1 とは

`fc_ir_v1` は **NAIL ネイティブの Tool 定義中間表現（Intermediate Representation）** である。Provider（OpenAI / Anthropic / Gemini 等）に依存しない統一フォーマットで Tool を定義し、各 provider の schema に変換するための橋渡し層として機能する。

主要な設計目標:

- **Provider 非依存**: 1つの定義から複数 provider の schema を生成できる
- **変換の透明性**: provider への変換が lossy（情報損失あり）か non-lossy かを明示する
- **nail check との統合**: 型検査・effects 検証を `nail check` と同一の型システムで実施できる
- **機械生成向け**: NAIL コンパイラ・ツールチェインが生成・変換するフォーマット

### このフォーマットが対象とするユースケース

- NAIL コードから自動生成された Tool 定義の保存・配布
- CI/CD での Tool schema 検証 (`nail fc check`)
- 複数 provider へのデプロイ自動化

### このフォーマットが対象としないこと（非目標）

| 非目標 | 理由 |
|--------|------|
| 汎用プログラミング IR | NAIL の Tool-Calling に特化した仕様。汎用 IR（LLVM IR 等）ではない |
| 人間が手書きするフォーマット | 機械生成・機械変換を前提としている。人間が読む場合は NAIL ソースを参照すること |
| ランタイム実行仕様 | Tool の呼び出しプロトコル・レスポンス処理は別仕様で定義する |
| プロバイダ固有の拡張管理 | `annotations` フィールドを通じてヒントは渡せるが、プロバイダ固有の semantics は本仕様の範囲外 |

---

## 2. Canonicalization

### 正規形とは

`fc_ir_v1` には一意の正規形（Canonical Form）が定義されており、ツールチェインは常に正規形で出力しなければならない。正規形によりファイル比較・ハッシュ検証・差分表示が一意になる。

### ルートキー順序

ルートオブジェクトのキーは以下の順序で出力しなければならない:

```
kind → tools → meta
```

### ToolDef キー順序

`tools` 配列の各要素（ToolDef）のキーは以下の順序で出力しなければならない:

```
id → name → title → doc → effects → input → output → examples → annotations
```

存在しないキーは省略する。仕様外の未知キーが存在する場合は FC011 WARN を発行したうえで既知キーの後に出力する（通常モード）。`annotations` 内の追加キーは仕様外キーとはみなされない。

### JSON フォーマット規則

- **空白なし（compact JSON）**: スペース・改行を含まない最小表現
- **`ensure_ascii=False`**: 非 ASCII 文字（日本語等）はエスケープしない
- **キーのソート**: 上記定義順に従い、アルファベット順ではない

### 正規化コマンド

```bash
nail fc canonicalize <input.json> [-o <output.json>]
```

オプション:
- `-o / --output`: 出力先ファイルパス（省略時は stdout）
- `--in-place`: 入力ファイルを上書き

### 正規形チェック

```bash
nail fc check --strict <input.json>
```

`--strict` フラグを付けると canonical 違反を **FC005 ERROR** として報告する。CI 環境での使用を推奨する。

### 未知キーの扱い

`annotations` 以外の場所に仕様外フィールド（未知キー）が含まれる場合、ツールチェインは以下の動作をする:

<!-- 設計判断: 通常の canonicalize が中断するのは開発者体験として厳しすぎる。
     canonicalize の責務は「正規化」であり、未知情報の保持はその責務の範囲内。
     厳格な検証は check --strict に委ねる。 -->

**通常モード:**
- **`nail fc check`**: 未知キーを **FC011 WARN** として報告する（エラーにはならない）
- **`nail fc canonicalize`**: 未知キーを**そのまま保持する**（情報破壊しない）。キー並べ替え・値正規化は実行され、未知キーは既知キーの後に置かれる（安定した位置）。**未知キー同士の順序は辞書順（lexicographic）でソートする**（例: `{"z_unknown": ..., "m_unknown": ...}` → canonical では `m_unknown`, `z_unknown` の順）。**FC011 WARN** を出力する

**strict モード（`--strict`）:**
- **`nail fc check --strict`**: 未知キーを **FC011 ERROR** として報告する
- **`nail fc canonicalize --strict`**: 未知キーを検出したら変換を中断し、エラーを返す

WARN メッセージ例:
```
FC011 WARN: Unknown key 'timeout' in ToolDef 'weather.get'. Consider moving to 'annotations'.
```

未知キーを許可フィールドに移動するには `annotations` を使用すること:
```json
{
  "id": "weather.get",
  "annotations": {
    "timeout": 30
  }
}
```

### 正規形の例

正規形 (compact, ensure_ascii=False):
```json
{"kind":"fc_ir_v1","tools":[{"id":"weather.get","name":"weather_get","title":"現在の天気を取得","doc":"指定した都市の現在の天気情報を取得します。気温・湿度・天気概況を返します。","effects":{"kind":"capabilities","allow":["NET:http_get"]},"input":{"type":"object","properties":{"city":{"type":"string"},"units":{"type":"enum","values":["celsius","fahrenheit"]}},"required":["city"]},"output":{"type":"object","properties":{"temperature":{"type":"float"},"humidity":{"type":"float"},"description":{"type":"string"}},"required":["temperature","humidity","description"]}}],"meta":{"nail_version":"0.9.0","created_at":"2026-02-25T10:00:00Z","source_hash":"sha256:abc123","spec_rev":"abc1234"}}
```

---

## 3. ToolDef Schema

### ルート構造

```json
{
  "kind": "fc_ir_v1",
  "tools": [
    { /* ToolDef */ },
    { /* ToolDef */ }
  ],
  "meta": {
    "nail_version": "0.9.0",
    "created_at": "2026-02-25T10:00:00Z",
    "source_hash": "sha256:...",
    "spec_rev": "abc1234"
  }
}
```

#### `meta` フィールド

| フィールド | 必要性 | 説明 |
|-----------|-------|------|
| `nail_version` | 推奨（recommended） | 生成に使用した NAIL バージョン |
| `created_at` | 推奨（recommended） | ISO 8601 UTC (Z) 形式の生成日時 |
| `source_hash` | 任意（optional） | 生成元ソースファイルの SHA-256 ハッシュ |
| `spec_rev` | 任意（optional） | この仕様書のリビジョン（git commit hash 等） |

> `created_at` は **UTC ISO 8601（Z サフィックス固定）** で記述すること。例: `"2026-02-25T10:00:00Z"`。タイムゾーンオフセット（`+09:00` 等）は不可。

### ToolDef フィールド仕様

#### 必須フィールド

| フィールド | 型 | 説明 |
|-----------|----|------|
| `id` | string | 安定識別子。ドット区切り可（例: `weather.get`）。**一度公開したら変更禁止**。 |
| `doc` | string | LLM が Tool の用途を理解するための説明文。1〜2段落。LLM 誘導の核となるフィールド。 |
| `effects` | object | Tool が持つ副作用の宣言。capabilities 形式（§6 参照）。 |
| `input` | Type | 引数の型定義。**必ず `type: "object"` でなければならない**（FC003）。`input.required` が省略または空配列で `input.properties` が2件以上ある場合は **FC012 WARN** を出す。 |

#### 推奨フィールド

| フィールド | 型 | 説明 |
|-----------|----|------|
| `name` | string | Provider-safe な Tool 名。省略時は `sanitize(id)` で自動生成（§4 参照）。 |
| `title` | string | 人間・LLM 向けの短い表示名。UI での表示や LLM の選択判断に使用。 |
| `output` | Type | 戻り値の型定義。省略時は FC006 WARN を発行。型検証の網羅性が低下する。 |
| `examples` | array | 入出力の具体例。`[{ "input": {...}, "output": {...}, "description": "..." }]` 形式。 |

#### 任意フィールド

| フィールド | 型 | 説明 |
|-----------|----|------|
| `annotations` | object | Provider ヒントや将来拡張のための任意キー置き場。後方互換を保証。未知のキーはツールチェインが無視する。 |

### 完全な ToolDef の例

```json
{
  "id": "weather.get",
  "name": "weather_get",
  "title": "現在の天気を取得",
  "doc": "指定した都市の現在の天気情報を外部 API から取得します。\n気温・湿度・天気の概況を含む構造化データを返します。都市名は英語または日本語で指定可能です。",
  "effects": {
    "kind": "capabilities",
    "allow": ["NET:http_get"]
  },
  "input": {
    "type": "object",
    "properties": {
      "city": {
        "type": "string"
      },
      "units": {
        "type": "optional",
        "inner": {
          "type": "enum",
          "values": ["celsius", "fahrenheit"]
        }
      }
    },
    "required": ["city"]
  },
  "output": {
    "type": "object",
    "properties": {
      "temperature": { "type": "float" },
      "humidity": { "type": "float" },
      "description": { "type": "string" }
    },
    "required": ["temperature", "humidity", "description"]
  },
  "examples": [
    {
      "input": { "city": "Tokyo", "units": "celsius" },
      "output": { "temperature": 22.5, "humidity": 60.0, "description": "晴れ" },
      "description": "東京の天気を摂氏で取得する例"
    }
  ],
  "annotations": {
    "openai.strict": true,
    "cache_ttl_seconds": 300
  }
}
```

### 最小限の ToolDef の例（PURE Tool）

```json
{
  "id": "math.add",
  "doc": "2つの整数を加算して結果を返します。副作用はありません。",
  "effects": {
    "kind": "capabilities",
    "allow": []
  },
  "input": {
    "type": "object",
    "properties": {
      "a": { "type": "int" },
      "b": { "type": "int" }
    },
    "required": ["a", "b"]
  }
}
```

---

## 4. Name Sanitization

### 正規化後の name が満たすべき形式

```
name = /^[a-z][a-z0-9_]*$/
```

先頭は小文字英字（`[a-z]`）必須、以降は `[a-z0-9_]` の任意長。例えば `t_123abc` は先頭が `t`（小文字英字）であるため通過するが、これは `t_` が特別扱いされるわけではなく、先頭が小文字英字であるという一般ルールを満たしているに過ぎない。

最終的に name は `/^[a-z][a-z0-9_]*$/` に適合しなければならない。適合しない場合は `nail fc check` で **FC002 ERROR** を発生させる。

### 自動生成規則

`name` フィールドが省略された場合、`id` から以下のルールで自動生成する:

1. `.` と `-` を `_` に置換
2. `[a-z0-9_]` 以外の文字をすべて `_` に置換
3. 連続する `_` を1つに圧縮
4. 小文字に正規化
5. 先頭が数字の場合は `t_` プレフィックスを付与
6. 末尾の `_` をトリム
7. sanitize 後の文字列が空文字になった場合（例: `id="---"` や `id="🎉"` など、有効な文字が存在しないケース）:
   - **FC002 ERROR**: `"Tool name cannot be empty after sanitization"`
   - `name` フィールドの自動生成は行わない（空文字のまま使用しない）

### 変換例

| `id` | 生成される `name` |
|------|------------------|
| `weather.get` | `weather_get` |
| `my-tool` | `my_tool` |
| `123abc` | `t_123abc` |
| `File/Reader` | `file_reader` |
| `my..double.dot` | `my_double_dot` |
| `hello world` | `hello_world` |
| `net.http.GET` | `net_http_get` |

### 衝突検出

同一の `tools` リスト内で、2つ以上の tool が同じ `name`（明示・自動生成の両方を含む）を持つ場合は **FC002 ERROR** となる。

衝突例:
```json
{
  "tools": [
    { "id": "weather.get", /* name → weather_get */ ... },
    { "id": "weather_get", /* name → weather_get (衝突!) */ ... }
  ]
}
```

エラーメッセージ:
```
[FC002] ERROR: Name collision: tools 'weather.get' and 'weather_get' both generate name 'weather_get'. Specify 'name' explicitly.
```

衝突解決方法:
```json
{
  "tools": [
    { "id": "weather.get",  "name": "weather_get_v1", ... },
    { "id": "weather_get",  "name": "weather_get_v2", ... }
  ]
}
```

---

## 5. Type Subset

`fc_ir_v1` の `input` / `output` に使用可能な型は、NAIL 型システムのサブセットである。

### 型一覧と Provider マッピング

| 型 | fc_ir_v1 表現 | OpenAI | Anthropic | Gemini |
|----|--------------|--------|-----------|--------|
| bool | `{"type":"bool"}` | `boolean` | `boolean` | `boolean` |
| int（精度なし） | `{"type":"int"}` | `integer` | `integer` | `integer` |
| int（精度付き） | `{"type":"int","bits":64,"overflow":"panic"}` | `integer` ＋ lossy | `integer` ＋ lossy | `integer` ＋ lossy |
| float | `{"type":"float"}` | `number` | `number` | `number` |
| string | `{"type":"string"}` | `string` | `string` | `string` |
| array | `{"type":"array","items":T}` | `array` | `array` | `array` |
| object | `{"type":"object","properties":{...},"required":[...]}` | `object` | `object` | `object` |
| optional | `{"type":"optional","inner":T}` | T（required から除外） | T（required から除外） | T（required から除外） |
| enum | `{"type":"enum","values":["a","b"]}` | `string` + `enum` | `string` + `enum` | `string` + `enum` |

### 型表現の詳細

#### bool

```json
{ "type": "bool" }
```

#### int（精度なし）

```json
{ "type": "int" }
```

#### int（精度付き）

```json
{
  "type": "int",
  "bits": 64,
  "overflow": "panic"
}
```

`overflow` の有効値: `"panic"` | `"wrap"` | `"saturate"`

#### float

```json
{ "type": "float" }
```

#### string

```json
{ "type": "string" }
```

#### array

```json
{
  "type": "array",
  "items": { "type": "string" }
}
```

#### object

```json
{
  "type": "object",
  "properties": {
    "name": { "type": "string" },
    "age":  { "type": "int" }
  },
  "required": ["name"]
}
```

`required` を省略した場合、全フィールドがオプションとみなされる。

#### optional

```json
{
  "type": "optional",
  "inner": { "type": "string" }
}
```

Provider 変換時: `inner` 型をそのまま使いつつ、`required` 配列からこのフィールドを除外する。

#### enum

```json
{
  "type": "enum",
  "values": ["celsius", "fahrenheit", "kelvin"]
}
```

Provider 変換時: `type: "string"` + `enum: [...]` として出力する。

### Lossy 型情報の記録

`int.bits` / `int.overflow` 等、provider schema で表現できない精度情報は **lossy** として扱う。変換時に失われた情報は `tools.meta.json`（または同等のメタデータファイル）の `lossy` フィールドに記録する:

```json
{
  "lossy": {
    "weather.get": {
      "name": "weather_get",
      "fields": ["int.bits", "int.overflow"]
    }
  }
}
```

`lossy` フィールドの仕様:
- キーは **`id` 基準**（安定参照のため。`name` は rename で変わる可能性があるため使わない）
- `name` フィールドは対応する provider-safe name（rename しても追跡可能）
- `fields` は損失したフィールドパスのリスト

---

## 6. Effects Representation

### 標準形式（capabilities）

```json
{
  "kind": "capabilities",
  "allow": ["FS:read_file", "NET:http_get", "IO:stdout"]
}
```

`allow` 配列の各要素は `{カテゴリ}:{操作}` 形式、または `{カテゴリ}` のみの形式を取る。

### カテゴリ一覧

| カテゴリ | 説明 |
|---------|------|
| `PURE` | 副作用なし。`allow` 配列が空の場合と等価。 |
| `IO` | 標準入出力（stdin/stdout/stderr）へのアクセス |
| `FS` | ファイルシステムへのアクセス |
| `NET` | ネットワーク通信 |
| `SYS` | システムコール（プロセス生成・シグナル等） |

### PURE Tool の宣言

`allow` が空配列の場合、その Tool は副作用なし（PURE）として扱われる:

```json
{
  "kind": "capabilities",
  "allow": []
}
```

PURE Tool が `FS`/`NET`/`IO` カテゴリを `allow` に含む場合は **FC004 ERROR**。

### 操作レベルの指定例

```json
{
  "kind": "capabilities",
  "allow": [
    "FS:read_file",
    "FS:write_file",
    "NET:http_get",
    "NET:http_post",
    "IO:stdout"
  ]
}
```

カテゴリのみ指定（`"FS"` 等）も有効だが、可能な限り操作レベルで指定することを推奨する。

### Legacy 形式（非推奨）

以下の形式は後方互換のために受理するが、**FC009 WARN** を発行する:

```json
["FS", "NET"]
```

`nail fc canonicalize` を実行することで標準の capabilities 形式に変換される:

```json
{
  "kind": "capabilities",
  "allow": ["FS", "NET"]
}
```

### fc check による Effects 検証

- `allow` が空（PURE）なのに `FS`/`NET`/`IO` が含まれる → **FC004 ERROR**
- 未知のカテゴリ（`PURE` / `IO` / `FS` / `NET` / `SYS` 以外）→ **FC009 WARN** ※FC009は legacy 形式にも使用するが文脈で区別
- legacy 文字列配列形式を使用 → **FC009 WARN**

### Effects の Provider への変換

provider schema に構造化された effects 情報を渡す標準的な方法はない。`effects` は **lossy フィールド** として扱われる。

オプションとして、OpenAI の `function.description` に注記を付加する機能を `nail fc convert --provider openai --annotate-effects` で提供する（デフォルト OFF）:

```json
{
  "function": {
    "name": "read_log_file",
    "description": "ログファイルを読み込んで内容を返します。\n\n[effects: FS:read_file]"
  }
}
```

---

## 7. Provider Mapping

### 概要

`nail fc convert <tools.nail> --provider <name>` で各 provider の schema 形式に変換できる。

```bash
nail fc convert <tools.nail> --provider openai   -o openai-tools.json
nail fc convert <tools.nail> --provider anthropic -o anthropic-tools.json
nail fc convert <tools.nail> --provider gemini    -o gemini-tools.json
```

### OpenAI

フィールドマッピング:

| fc_ir_v1 | OpenAI | 備考 |
|----------|--------|------|
| `name` | `function.name` | |
| `doc` | `function.description` | |
| `input` | `function.parameters` | JSON Schema 形式 |
| `effects` | （lossy） | `--annotate-effects` で description に注記 |
| `output` | （lossy） | |
| `examples` | （lossy） | |
| `annotations.openai.*` | 対応フィールド | `strict` 等 |

変換例:

```json
{
  "type": "function",
  "function": {
    "name": "weather_get",
    "description": "指定した都市の現在の天気情報を外部 API から取得します。\n気温・湿度・天気の概況を含む構造化データを返します。",
    "parameters": {
      "type": "object",
      "properties": {
        "city": { "type": "string" },
        "units": { "type": "string", "enum": ["celsius", "fahrenheit"] }
      },
      "required": ["city"]
    },
    "strict": true
  }
}
```

### Anthropic

フィールドマッピング:

| fc_ir_v1 | Anthropic | 備考 |
|----------|-----------|------|
| `name` | `name` | |
| `doc` | `description` | |
| `input` | `input_schema` | JSON Schema 形式 |
| `effects` | （lossy） | |
| `output` | （lossy） | |
| `examples` | （lossy） | |

変換例:

```json
{
  "name": "weather_get",
  "description": "指定した都市の現在の天気情報を外部 API から取得します。\n気温・湿度・天気の概況を含む構造化データを返します。",
  "input_schema": {
    "type": "object",
    "properties": {
      "city": { "type": "string" },
      "units": { "type": "string", "enum": ["celsius", "fahrenheit"] }
    },
    "required": ["city"]
  }
}
```

### Gemini

フィールドマッピング:

| fc_ir_v1 | Gemini | 備考 |
|----------|--------|------|
| `name` | `name` | |
| `doc` | `description` | |
| `input` | `parameters` | JSON Schema 形式（Gemini は OpenAPI Subset） |
| `effects` | （lossy） | |
| `output` | （lossy） | |
| `examples` | （lossy） | |

変換例:

```json
{
  "name": "weather_get",
  "description": "指定した都市の現在の天気情報を外部 API から取得します。\n気温・湿度・天気の概況を含む構造化データを返します。",
  "parameters": {
    "type": "object",
    "properties": {
      "city": { "type": "string" },
      "units": { "type": "string", "enum": ["celsius", "fahrenheit"] }
    },
    "required": ["city"]
  }
}
```

### Lossy フィールド一覧

以下のフィールドは provider schema で表現できないため、変換時に情報が失われる（lossy）:

| フィールド / 情報 | 理由 |
|-----------------|------|
| `int.bits` / `int.overflow` | provider の integer 型は精度情報を持たない |
| `effects` 構造情報 | provider の Tool schema に effects フィールドが存在しない |
| `examples` | provider の Tool 定義に example フィールドが存在しない |
| `output` 型 | provider は出力型の schema を Tool 定義に持たない |
| `annotations` | provider 固有キー以外は変換先がない |

lossy 情報は変換時に `--lossy-report <file>` または `--emit-meta` オプションで JSON ファイルに出力できる。

`--emit-meta` 出力例（lossy キーは `id` 基準で統一）:
```json
{
  "lossy": {
    "math.add": {
      "name": "math_add",
      "fields": ["int.bits", "int.overflow"]
    }
  }
}
```

---

## 8. Diagnostics

`nail fc check` が報告する全 ERROR / WARN の一覧。

### エラーコード一覧

| コード | 種別 | 条件 | メッセージ |
|--------|------|------|-----------|
| **FC001** | ERROR | tool `id` が一意でない | `Duplicate tool id: '{id}'` |
| **FC002** | ERROR | `name` 衝突（生成含む） | `Name collision: tools '{id1}' and '{id2}' both generate name '{name}'. Specify 'name' explicitly.` |
| **FC003** | ERROR | `input` が object でない | `Tool '{id}': 'input' must be of type object, got '{type}'` |
| **FC004** | ERROR | PURE tool が effects を持つ | `Tool '{id}': pure tool declares effects {effects}` |
| **FC005** | ERROR | strict モードで canonical 違反 | `Input is not in canonical form. Run 'nail fc canonicalize' to fix.` |
| **FC006** | WARN | `output` 未指定 | `Tool '{id}': output type not declared — verification coverage is reduced` |
| **FC007** | WARN | provider 表現不能な型（非 strict） | `Tool '{id}': type '{type}' is not representable in {provider} schema; will be degraded` |
| **FC008** | ERROR | provider 表現不能な型（`--strict-provider`） | `Tool '{id}': type '{type}' cannot be represented in {provider} schema` |
| **FC009** | WARN | legacy effects 形式を使用中 | `Tool '{id}': effects uses legacy string array format; run 'nail fc canonicalize' to normalize` |
| **FC010** | WARN | `doc` が空または短すぎる（<20文字） | `Tool '{id}': doc is too short (<20 chars); LLM guidance may be insufficient` |
| **FC011** | WARN（通常） / ERROR（`--strict`） | ToolDef に `annotations` 以外の未知キーが存在 | `Unknown key '{key}' in ToolDef '{id}'. Consider moving to 'annotations'.` |
| **FC012** | WARN | `input.required` 省略/空、かつ properties ≥ 2 | `Tool '{id}': 'input.required' is absent or empty but 'input.properties' has {n} fields — required args may be unintentionally optional` |

### チェックモード

```bash
# 標準チェック（ERROR のみ終了コード 1）
nail fc check input.json

# strict チェック（canonical 違反も ERROR）
nail fc check --strict input.json

# provider strict チェック（特定 provider で表現不能な型を ERROR）
nail fc check --strict-provider openai input.json
nail fc check --strict-provider anthropic input.json
nail fc check --strict-provider gemini input.json

# WARN も終了コード 1 にする（CI 推奨）
nail fc check --strict --fail-on-warn input.json
```

### 出力フォーマット

```
[FC001] ERROR: Duplicate tool id: 'weather.get'
  at tools[3].id

[FC006] WARN: Tool 'math.add': output type not declared — verification coverage is reduced
  at tools[1]

[FC010] WARN: Tool 'fs.read': doc is too short (<20 chars); LLM guidance may be insufficient
  at tools[2].doc
```

### CI 推奨設定

```yaml
# .github/workflows/nail-check.yml
- name: nail fc check
  run: |
    nail fc check --strict --fail-on-warn tools.fc.json
```

---

## Appendix A: 完全な fc_ir_v1 ファイルの例

```json
{
  "kind": "fc_ir_v1",
  "tools": [
    {
      "id": "weather.get",
      "name": "weather_get",
      "title": "現在の天気を取得",
      "doc": "指定した都市の現在の天気情報を外部 API から取得します。\n気温・湿度・天気の概況を含む構造化データを返します。都市名は英語または日本語で指定可能です。",
      "effects": {
        "kind": "capabilities",
        "allow": ["NET:http_get"]
      },
      "input": {
        "type": "object",
        "properties": {
          "city": { "type": "string" },
          "units": {
            "type": "optional",
            "inner": { "type": "enum", "values": ["celsius", "fahrenheit"] }
          }
        },
        "required": ["city"]
      },
      "output": {
        "type": "object",
        "properties": {
          "temperature": { "type": "float" },
          "humidity": { "type": "float" },
          "description": { "type": "string" }
        },
        "required": ["temperature", "humidity", "description"]
      },
      "examples": [
        {
          "input": { "city": "Tokyo", "units": "celsius" },
          "output": { "temperature": 22.5, "humidity": 60.0, "description": "晴れ" },
          "description": "東京の天気を摂氏で取得"
        }
      ],
      "annotations": {
        "openai.strict": true,
        "cache_ttl_seconds": 300
      }
    },
    {
      "id": "math.add",
      "name": "math_add",
      "title": "整数の加算",
      "doc": "2つの整数を加算して結果を返します。副作用はありません。オーバーフロー時は panic します。",
      "effects": {
        "kind": "capabilities",
        "allow": []
      },
      "input": {
        "type": "object",
        "properties": {
          "a": { "type": "int", "bits": 64, "overflow": "panic" },
          "b": { "type": "int", "bits": 64, "overflow": "panic" }
        },
        "required": ["a", "b"]
      },
      "output": {
        "type": "int",
        "bits": 64,
        "overflow": "panic"
      }
    },
    {
      "id": "fs.read_file",
      "name": "fs_read_file",
      "title": "ファイル読み込み",
      "doc": "指定したパスのファイルを読み込んで内容を文字列として返します。\nファイルが存在しない場合はエラーを返します。UTF-8 エンコーディングを前提とします。",
      "effects": {
        "kind": "capabilities",
        "allow": ["FS:read_file"]
      },
      "input": {
        "type": "object",
        "properties": {
          "path": { "type": "string" },
          "encoding": {
            "type": "optional",
            "inner": { "type": "string" }
          }
        },
        "required": ["path"]
      },
      "output": {
        "type": "string"
      }
    }
  ],
  "meta": {
    "nail_version": "0.9.0",
    "created_at": "2026-02-25T10:00:00Z",
    "source_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "spec_rev": "abc1234"
  }
}
```

---

## Appendix B: NAIL ソースからの自動生成フロー

```
NAIL source (.nail)
       │
       ▼
  nail compile
       │
       ▼
 fc_ir_v1 JSON        ← 本仕様書が定義するフォーマット
       │
       ├─► nail fc check         （型・effects・canonical 検証）
       │
       ├─► nail fc convert <tools.nail> --provider openai      → OpenAI tools JSON
       ├─► nail fc convert <tools.nail> --provider anthropic   → Anthropic tools JSON
       └─► nail fc convert <tools.nail> --provider gemini      → Gemini tools JSON
```

---

## Appendix C: 変更履歴

| バージョン | 日付 | 変更内容 |
|-----------|------|---------|
| v0.9-draft | 2026-02-25 | 初稿作成（Issue #88） |
| v0.9-draft | 2026-02-25 | FC011: canonicalize は未知キーを保持して WARN（中断しない）。--strict 時のみ ERROR に昇格 |

---

*本仕様書は NAIL v0.9 における fc_ir_v1 の凍結候補ドラフトです。Boss 最終レビュー後に v0.9 として確定します。*
