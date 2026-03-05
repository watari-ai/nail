# Issue #113: feat: Improve error messages with source location

## Summary
NAILのエラーメッセージに行番号・列番号・ソースの該当行を含める。

## Motivation
現在のエラーメッセージ:
```
TypeError: expected Int, got String
```

改善後:
```
TypeError at line 5, col 3: expected Int, got String
  5 | let x: Int = "hello"
              ^^^^^
```

## Scope
- Lexer/Parserエラー: 行・列情報の付与
- Type checker エラー: 問題箇所のハイライト
- Runtime エラー: スタックトレース（call site情報）

## Priority
P2 — developer experience改善。v1.0後に実装推奨。

## Labels
enhancement, developer-experience, v1.1
