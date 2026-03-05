# Multi-layer LLM Interface Contracts — 設計メモ

> Issue: #110  
> 担当: watari-ai  
> 作成日: 2026-03-05  
> ステータス: 調査・提案段階（実装前）

---

## Issue サマリー

デュアルレイヤー（Persona層 + Capability層）LLMアーキテクチャにおいて、層間インターフェースが「無型かつ暗黙的」という根本的設計問題が存在する。

NAILの既存の委譲エフェクト修飾子（#107）は関数レベルでこれを解決しているが、#110はそれを**アーキテクチャレベルの層コントラクト**に拡張する提案。

主な追加概念は3つ：
1. **`locality`** — 層の実行コンテキスト（`local` / `cloud` / `hybrid`）の宣言
2. **`retain`/`pass`** — 委譲時に保持すべきフィールドと渡すフィールドの明示的分離
3. **新エラーコード** — `DELEGATION_LEAK`（保持フィールドが委譲ペイロードに含まれた場合）、`LOCALITY_VIOLATION`

目標はランタイムやルーターではなく「設計の上流にある仕様言語」としての位置づけ。

---

## 関連 Issue との関係図

```
#107 Effect Qualifiers (Phase 1) ← 基盤
  │
  ├── #108 Delegation Depth (Phase 2 Draft)
  │     ・max_delegation_depth: N → 委譲チェーンの深さを制限
  │     ・静的検査 or 動的検査の設計判断がブロッカー
  │     ・mcp-fw との境界未定義
  │
  ├── #110 Multi-layer Contracts ← このIssue
  │     ・layer {} トップレベルキー追加
  │     ・locality 宣言 + エフェクト allow/deny
  │     ・retain/pass による委譲フィールド契約
  │     ・DELEGATION_LEAK チェッカー
  │     ・依存: #107（grants セマンティクスを継承）
  │     ・関連: #108（depth 制限と組み合わせ可能）
  │
  └── #112 Routing Hints
        ・complexity_tier / persona_required / memory_depth
        ・#110 の locality 宣言の自然な補完
        ・タスク定義に付けるアノテーション
        ・#110 の layer {} と組み合わせて
          「どの層にルーティングすべきか」を検証可能にする

依存関係まとめ:
  #107 → #110 → #112 (推奨実装順)
  #107 → #108 (並列可、ただし設計判断待ち)
```

---

## 実装の複雑度見積もり

| コンポーネント | 複雑度 | 理由 |
|---|---|---|
| `layer` トップレベルキー / パーサー拡張 | Medium | 新しいスコープ概念。既存 `function` との共存設計が必要 |
| `locality` フィールドと検査ルール | Low | ローカル変数のように宣言的、静的検査で完結 |
| `retain`/`pass` と `DELEGATION_LEAK` | Medium | フィールド参照のトラッキングが必要。型安全性と組み合わせると複雑化 |
| 委譲グラフのサイクル検出 | Low | 標準的なDAGチェック |
| 新エフェクト型 (`PERSONA`, `MEMORY`, `KNOWLEDGE`) | Low | 既存エフェクト定義パターンに追加するだけ |
| テスト (10件以上) | Medium | 有効/無効の組み合わせが多い |
| SPEC.md セクション追加 | Low | ドキュメント作業 |

**総合複雑度: Medium**  
→ #107 実装が安定していれば着手可能。ただし `retain`/`pass` のフィールドトラッキングは慎重な設計が必要。

---

## 先に実装すべき依存 Issue

### 必須
- **#107 Effect Qualifiers (Phase 1)** — `grants`/`delegation=explicit` のセマンティクスを #110 の `retain`/`pass` が継承するため、完成していることが前提

### 推奨（先行または並列確認）
- **#109 `can_delegate` qualifier (PR)** — `#112` の routing hints が参照している。#110 との概念整合性を確認してから着手するのが望ましい

### 後回し可
- **#108 Delegation Depth** — #110 と組み合わせ可能だが、静的/動的検査の設計判断が未解決。#110 とは独立して後から追加できる設計になっている

---

## Open Questions

### Q1. `layer` と既存の `function` の共存スコープをどう設計するか？
`layer {}` ブロックの中に `function {}` 定義を入れ子にするのか、`layer` は既存ファイルに `layer` キーを追加するフラット参照にするのか。
前者はスコープが明確だが仕様ファイルが巨大化。後者は柔軟だが循環参照のリスクがある。

### Q2. `retain` 違反（`DELEGATION_LEAK`）は Error か Warning か？
エフェクト系の他のチェック（`FC-E010` 等）は原則 Error 扱い。ただし `retain` は設計上の制約であり、ランタイムが必ずしも強制できない。
Checker での Error + mcp-fw での実行時 Warning という二段階にするか、一本化するか。

### Q3. `hybrid` locality の検証ポリシーは誰が持つか？
`locality: "hybrid"` の場合、実行コンテキストが動的に変わる可能性がある。
Checker は「より厳しい方の制約（cloud + local 両方）を適用」するのか、それとも `hybrid` 層に固有のルールセットを設けるのか。
これは #108 の静的 vs 動的論争と共通する根本問題でもある。

---

## 補足メモ

- 提案構文（JSON形式）は現行 NAIL の表現方法と異なる可能性あり。実装前に SPEC.md の文法定義と整合性確認が必要。
- `KNOWLEDGE` エフェクトは `NET` を暗黙的に含むとされているが、その継承関係を型システムでどう表現するかは別途設計が必要。
- `examples/multi-layer/dual-llm.nail` のサンプル作成は実装後で良いが、設計検証として先行してドラフトを書くと判断が早まる可能性あり。
