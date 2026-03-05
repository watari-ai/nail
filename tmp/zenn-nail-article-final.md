---
title: "AIエージェントのための言語、NAIL ── エフェクトをJSONで宣言する"
emoji: "🔨"
type: "tech"
topics: ["nail", "ai", "llm", "programminglanguage", "json"]
published: false
---

## はじめに

**NAIL（Native AI Language）** は、LLMが生成し、機械が検証するために設計されたプログラミング言語です。テキスト構文はなく、プログラムはJSONドキュメントそのものです。

なぜ作ったか。LLMに「副作用のないコードを書いて」と頼んでも、それが本当に副作用のない実装になっているかを確認する手段がほぼありません。コードレビューは人間の目に依存し、テストは「考えたケース」しかカバーできない。NAILは、**エフェクト（副作用）を型システムに組み込むことで、この問題を構造的に解決します**。v0.9.2は現在PyPIで公開中です。

---

## 問題: LLMが生成するコードは信頼できるか

現代のサンドボックスは「このプロセスはネットワークにアクセスできる/できない」という粗い粒度の制御しか持っていません。しかし実際に必要なのは、もっと細かい制御です。

- このLLMが呼び出すツールは、**意図的に** ファイルシステムを読んでいるのか？
- ネットワークアクセスは仕様として宣言されたものか、それともうっかり紛れ込んだものか？
- エージェントAがエージェントBに仕事を委譲したとき、BはAが持っていない権限を行使できてしまわないか？

これは「LLMの能力」の問題ではなく、**言語設計の問題**です。現在の言語には、副作用を型として表現する仕組みがないため、LLMが意図と非意図のアクセスを区別して生成することができません。

---

## NAILの解決策: エフェクトを言語に組み込む

NAILのプログラムはJSONで書きます。すべての副作用は関数シグネチャの `effects` フィールドに宣言しなければなりません。

```json
{
  "nail": "0.9",
  "kind": "fn",
  "id": "read_config",
  "effects": [
    { "type": "FS", "op": "read" }
  ],
  "params": [
    { "id": "path", "type": { "type": "str" } }
  ],
  "returns": { "type": "str" },
  "body": [
    { "op": "return", "val": { "builtin": "fs_read", "args": [{ "ref": "path" }] } }
  ]
}
```

`effects: []` と宣言した関数がファイルを読もうとすれば、**型チェック時にエラーになります**。実行前に検出できます。

エフェクトタグは以下の種類があります:

| タグ | 意味 |
|------|------|
| `FS` | ファイルシステム読み書き |
| `NET` | ネットワークアクセス |
| `IO` | ログ出力 / stdin / stdout |
| `REPO` | バージョン管理操作 |
| `DB` | データベースアクセス |

人間が読むためのコードではなく、**機械が検証するための宣言**です。LLMはこのJSON構造を生成し、NAILチェッカーが即座に検証します。

---

## 実際の動き: 3つのデモ

v0.9.2には、APIキー不要で動作する3つのデモが含まれています（`examples/demos/`）。

### 1. Agent Handoff — エージェント間の権限分離

マルチエージェントシステムでは、各エージェントに必要最小限の権限だけを渡すべきです。NAILでは `filter_by_effects()` を使って、共有ツールレジストリからエージェントごとのサブセットを切り出せます。

```bash
cd examples/demos/agent_handoff && python3 demo.py
```

```
Planner  → FS:read のみ（read-only）
Executor → FS:read + FS:write + NET（フルアクセス）
Reporter → IO のみ（出力専用）
```

NAIL仕様を変えずに、エージェントの役割に応じた権限分割が宣言的に行えます。

### 2. API Routing — 1つの仕様、複数のプロバイダー

LLMプロバイダーはそれぞれ独自のfunction calling形式を持っています。NAILの `convert_tools()` を使えば、1つのNAIL仕様からOpenAI・Anthropic・Gemini形式を生成できます。

```bash
cd examples/demos/api_routing && python3 demo.py
```

```python
# 1つのNAIL仕様 → 3つのフォーマット
nail.convert_tools(tools, source="nail", target="openai")    # OpenAI形式
nail.convert_tools(tools, source="nail", target="anthropic") # Anthropic形式
nail.convert_tools(tools, source="nail", target="gemini")    # Gemini形式
```

仕様の単一ソース化により、プロバイダー間の定義ドリフトを防ぎます。

### 3. Delegation Qualifiers — 委譲深度の制御（FC-E010）

**これがv0.9.2の目玉機能です。**

A→B→C→D のような多段委譲チェーンで、危険な権限がDまで「黙って」伝播してしまう問題があります。DeepMindの論文「Intelligent AI Delegation」（arXiv:2602.11865）が指摘する *Zone of Indifference* 問題です。

NAILでは `delegation: "explicit"` 修飾子によってこれを型レベルで防ぎます。

```json
{
  "effects": {
    "allow": [
      {
        "type": "FS",
        "op": "write_file",
        "delegation": "explicit",
        "grants": ["FS:write_file"],
        "reversible": false
      }
    ]
  }
}
```

`delegation: "explicit"` を付けた権限は、委譲チェーンの各ステップで明示的に `grants` フィールドに宣言し直さなければなりません。宣言なしに渡そうとすると **FC-E010 `ExplicitDelegationViolation`** が型チェック時に発生します。

```bash
cd examples/demos/delegation_qualifiers && python3 demo.py
```

実行環境に達する前に、意図しない権限エスカレーションを検出できます。

---

## v0.9.2 の現状

- **PyPI公開済み**: `pip install nail-lang`
- **954テスト全通過**（2026-03-01時点）
- **Delegation Qualifiers実装済み**: `nail_lang/fc_ir_v2` モジュール
  - `EffectQualifier`（後方互換: `effects.allow` は文字列・オブジェクト両方受け付ける）
  - `delegation: "explicit"` による委譲制御
  - `grants` フィールドによる明示的権限列挙
  - FC-E010 エラーコード
- **3つのデモ**: `examples/demos/` に収録、APIキー不要
- **Playground**: [naillang.com](https://naillang.com) でインタラクティブに試せる
- **`nail-lens` CLIツール**: `inspect` / `diff` / `validate` / `effects` サブコマンドで仕様を人間が読める形式で確認できる

---

## 使ってみる

```bash
pip install nail-lang
```

インストール後、すぐに使えるコマンド:

```bash
# 仕様ファイルをチェック
nail check myspec.nail

# インタラクティブデモ（6種類）
nail demo rogue-agent
nail demo verifiability
nail demo mcp-firewall

# 仕様のインスペクション（人間向け）
nail-lens inspect myspec.nail
nail-lens effects myspec.nail
```

デモは `examples/demos/` を直接実行することもできます:

```bash
git clone https://github.com/joh-luck/nail
cd nail
python3 examples/demos/agent_handoff/demo.py
python3 examples/demos/api_routing/demo.py
python3 examples/demos/delegation_qualifiers/demo.py
```

---

## おわりに・フィードバックについて

NAILはまだ実験段階です。「エフェクトを型として宣言する」というアプローチが、LLMが生成するコードの信頼性問題に対して有効かどうか、まだ証明できていません。

ただ、方向性は正しいと思っています。**意図と非意図を区別できない言語に、信頼できるAIエージェントは書けない**。

フィードバックはGitHub Issuesか、[naillang.com](https://naillang.com) のPlaygroundで試した感想をいただければ。特に「このユースケースでは使えない」という否定的なフィードバックを歓迎しています。仕様はまだ固まっていないので、今が意見を反映できるタイミングです。

---

*NAIL v0.9.2 / MIT License / [github.com/joh-luck/nail](https://github.com/joh-luck/nail)*
