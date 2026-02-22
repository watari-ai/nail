# Phase 2 Experiment — Problem Set

## 目的
同じ仕様をPython（人間向け言語）とNAIL（AIネイティブ言語）で実装したとき、
LLMが生成するコードのバグ率・トークン数・曖昧さの扱いを比較する。

## 問題一覧

### P1: is_even
**仕様:**
- 入力: `n: int64`
- 出力: `bool`
- 制約: 副作用なし
- 動作: n が偶数なら true、奇数なら false

### P2: abs_val
**仕様:**
- 入力: `n: int64`
- 出力: `int64 (overflow: panic)`
- 制約: 副作用なし
- 動作: n の絶対値を返す

### P3: max_of_two
**仕様:**
- 入力: `a: int64, b: int64`
- 出力: `int64 (overflow: panic)`
- 制約: 副作用なし
- 動作: a と b のうち大きい方を返す

### P4: clamp
**仕様:**
- 入力: `val: int64, lo: int64, hi: int64`
- 出力: `int64 (overflow: panic)`
- 制約: 副作用なし、`lo <= hi` を前提とする
- 動作: val を [lo, hi] の範囲に収める（val < lo なら lo、val > hi なら hi、それ以外は val）

### P5: factorial
**仕様:**
- 入力: `n: int64 (0 <= n <= 20)`
- 出力: `int64 (overflow: panic)`
- 制約: 副作用なし、ループで実装（再帰は NAIL v0.1 では対応外）
- 動作: n! を返す（0! = 1）

## 測定項目
1. L0-L2チェック通過（NAIL）/ Syntax + テスト通過（Python）: Pass / Fail
2. 生成トークン数（プログラム本体のみ）
3. 型の曖昧さ（Pythonでの型アノテーション欠落等）
4. エラーの種類と原因分析
