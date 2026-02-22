# Proposal #001: 可変変数と if_expr

**提案者:** Watari AI
**日付:** 2026-02-22
**理由:** Phase 2 実験で factorial が意味的に失敗 (実験データ: experiments/phase2/ANALYSIS.md)

## 提案内容

### 1. `assign` op の追加
```json
{ "op": "assign", "id": "acc", "val": <expr> }
```
- `mut: true` で宣言された変数のみ再代入可能
- スコープ: 内側のスコープから外側のミュータブル変数を変更できる
- 未宣言変数への assign → コンパイルエラー (L1)

### 2. `if_expr` の追加（式としての if）
```json
{
  "op": "if_expr",
  "cond": <bool_expr>,
  "then": <expr>,
  "else": <expr>
}
```
- `then` と `else` の型が一致しない場合 → L1 エラー

## 影響範囲
- SPEC.md セクション 6 (制御フロー) に追加
- checker.py: assign の型チェック、if_expr の型推論
- runtime.py: assign の実行、if_expr の評価

## 承認条件
- SPEC.md 更新 → Watari AI がレビュー → Boss が承認
