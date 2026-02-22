# NAIL Language Specification v0.1

> ⚠️ Draft. This specification evolves. Last updated by: Watari AI

---

## 1. 概要

NAILプログラムは **JSONドキュメントの集合** である。テキスト構文は存在しない。人間が「コードを書く」という行為はNAILにおいて存在しない。AIが構造データを生成し、検証器がそれを検証し、実行環境が実行する。

**NAILの唯一の表現形式：構造化JSONデータ**

---

## 2. 基本型システム

```json
{ "type": "int",    "bits": 64,  "overflow": "panic" }
{ "type": "int",    "bits": 64,  "overflow": "wrap"  }
{ "type": "int",    "bits": 64,  "overflow": "sat"   }
{ "type": "float",  "bits": 64  }
{ "type": "bool" }
{ "type": "string", "encoding": "utf8" }
{ "type": "bytes" }
{ "type": "option", "inner": <type> }
{ "type": "list",   "inner": <type>, "len": "dynamic" }
{ "type": "list",   "inner": <type>, "len": <n> }
{ "type": "map",    "key": <type>, "value": <type> }
{ "type": "unit" }
```

**設計原則：**
- `null` は存在しない。代わりに `option` 型を使用
- 整数オーバーフロー時の挙動は宣言必須（`panic` / `wrap` / `sat`）
- 暗黙の型変換は一切存在しない

---

## 3. 副作用システム（エフェクト）

すべての副作用は関数シグネチャに宣言する。宣言のない副作用はコンパイルエラー。

```json
"effects": []          // 純粋関数（副作用ゼロ）
"effects": ["IO"]      // 標準入出力
"effects": ["FS"]      // ファイルシステム
"effects": ["NET"]     // ネットワーク
"effects": ["TIME"]    // 現在時刻の取得
"effects": ["RAND"]    // 乱数
"effects": ["MUT"]     // 可変グローバル状態
```

複数のエフェクトは配列で列挙。`["IO", "NET"]` など。

---

## 4. 関数定義

```json
{
  "nail": "0.1.0",
  "kind": "fn",
  "id": "add",
  "effects": [],
  "params": [
    { "id": "a", "type": { "type": "int", "bits": 64, "overflow": "panic" } },
    { "id": "b", "type": { "type": "int", "bits": 64, "overflow": "panic" } }
  ],
  "returns": { "type": "int", "bits": 64, "overflow": "panic" },
  "body": [
    { "op": "return", "val": { "op": "+", "l": { "ref": "a" }, "r": { "ref": "b" } } }
  ]
}
```

**フィールド仕様：**
| フィールド | 必須 | 説明 |
|---|---|---|
| `nail` | ✅ | 仕様バージョン |
| `kind` | ✅ | `"fn"` |
| `id` | ✅ | 関数識別子（英数字とアンダースコアのみ） |
| `effects` | ✅ | エフェクトリスト（空配列 = 純粋関数） |
| `params` | ✅ | パラメータリスト |
| `returns` | ✅ | 戻り値の型 |
| `body` | ✅ | 命令リスト |

---

## 5. 演算子

### 算術
```json
{ "op": "+",   "l": <expr>, "r": <expr> }
{ "op": "-",   "l": <expr>, "r": <expr> }
{ "op": "*",   "l": <expr>, "r": <expr> }
{ "op": "/",   "l": <expr>, "r": <expr> }
{ "op": "%",   "l": <expr>, "r": <expr> }
```

### 比較（型が一致しない場合はコンパイルエラー）
```json
{ "op": "eq",  "l": <expr>, "r": <expr> }
{ "op": "neq", "l": <expr>, "r": <expr> }
{ "op": "lt",  "l": <expr>, "r": <expr> }
{ "op": "lte", "l": <expr>, "r": <expr> }
{ "op": "gt",  "l": <expr>, "r": <expr> }
{ "op": "gte", "l": <expr>, "r": <expr> }
```

### 論理
```json
{ "op": "and", "l": <expr>, "r": <expr> }
{ "op": "or",  "l": <expr>, "r": <expr> }
{ "op": "not", "v": <expr> }
```

---

## 6. 制御フロー

### 条件分岐
```json
{
  "op": "if",
  "cond": <bool_expr>,
  "then": [ <statements> ],
  "else": [ <statements> ]
}
```

`else` は省略不可。すべての分岐でreturnが必要。

### ループ
```json
{
  "op": "loop",
  "bind": "i",
  "from": { "lit": 0 },
  "to":   { "lit": 10 },
  "step": { "lit": 1 },
  "body": [ <statements> ]
}
```

無限ループは存在しない。終了条件は必須（停止性証明のため）。

---

## 7. リテラル

```json
{ "lit": 42 }
{ "lit": 3.14 }
{ "lit": true }
{ "lit": "hello" }
{ "lit": null, "type": { "type": "option", "inner": { "type": "int", "bits": 64, "overflow": "panic" } } }
```

---

## 8. 変数

```json
{ "op": "let", "id": "x", "type": <type>, "val": <expr> }
{ "ref": "x" }
```

変数はイミュータブルがデフォルト。再代入には `"mut": true` を付与。

---

## 9. 副作用付き操作

```json
{ "op": "print", "val": <string_expr>, "effect": "IO" }
{ "op": "read_file", "path": <string_expr>, "effect": "FS" }
{ "op": "http_get", "url": <string_expr>, "effect": "NET" }
```

エフェクト付き操作は、関数の `effects` に対応するエフェクトが宣言されていない場合はコンパイルエラー。

---

## 10. モジュール構造

```json
{
  "nail": "0.1.0",
  "kind": "module",
  "id": "math",
  "exports": ["add", "multiply"],
  "defs": [
    { ... },
    { ... }
  ]
}
```

---

## 11. プロジェクト構造（AIプロジェクト標準）

NAILは言語仕様と同時に、**AIが最小コンテキストでプロジェクトを理解できるディレクトリ構造**を定義する。

```
project/
├── SPEC.md          必須: プロジェクトの仕様（機能・制約・非機能要件）
├── AGENTS.md        必須: AIエージェントへの指示
├── ARCHITECTURE.md  推奨: システム構成図・依存関係
├── TODO.md          推奨: 現在のタスクリスト
├── src/             NAILソースファイル（*.nail）
├── tests/           テストケース（*.nail）
└── proofs/          形式証明ファイル（*.proof）
```

**SPEC.mdの必須フィールド（YAML形式）:**
```yaml
name: <project_name>
version: <semver>
language: nail@<version>
entry: <module_id>
effects_allowed: [IO, FS, NET]
constraints:
  - <制約を自然言語で>
```

これらのファイルの存在と形式は、NAILプロジェクトの検証器がチェックする。

---

## 12. 検証レベル

| レベル | 内容 |
|---|---|
| L0 | 構文的正しさ（JSONスキーマ検証） |
| L1 | 型整合性（型推論と型チェック） |
| L2 | エフェクト整合性（宣言されたエフェクトのみ使用） |
| L3 | 停止性証明（すべてのループが終了することを証明） |
| L4 | メモリ安全性（バッファオーバーフロー不可能であることを証明） |

v0.1はL0-L2を実装対象とする。

---

## 13. 未定義事項（v0.1では対象外）

- 代数的データ型（Enum）
- クロージャ
- 非同期処理
- エラーハンドリング（Result型）
- ジェネリクス
- トレイト/インターフェース

これらはv0.2以降でAIが仕様提案を行い、採択されたものを追加する。
