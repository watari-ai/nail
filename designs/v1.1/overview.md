# NAIL v1.1 — Issue Overview

最終更新: 2026-03-06
ステータス: 全件 OPEN・Boss確認待ち

---

## 概要

v1.1 では「AIエージェントの委譲・ルーティング・多層呼び出し」をNAIL言語レベルでサポートする。
v0.9.x で実装したエフェクトシステム（FC-E010）の自然な拡張。

---

## Issue マップ

| # | タイトル | 依存 | 複雑度 | 推定テスト数 | 状態 |
|---|---------|------|--------|-------------|------|
| #108 | Delegation depth tracking (Phase 2) | #107✅ | Medium | +40 | Draft・設計確定待ち |
| #110 | Multi-layer LLM interface contracts | #107✅ | Medium | +35 | 設計ノートあり |
| #111 | RAG Context Kind | なし | Low | +20 | Boss承認済み・実装待ち |
| #112 | Routing hints as declarative qualifiers | #110推奨 | Medium | +30 | 設計ドキュメントあり |

---

## 推奨実装順

```
#111（Low・独立）
  → #108（Medium・Phase 2）
    → #110（Medium・多層）
      → #112（Medium・ルーティング）
```

**#111 から始める理由:**
- 依存なし・低複雑度・独立実装可能
- RAG統合という具体的ユースケースで訴求力あり
- Boss承認済みのためGO確認が最も速い

---

## 各 Issue サマリー

### #111: RAG Context Kind
- **目的**: NAIL を RAG パイプラインの中間フォーマットとして使えるようにする
- **変更**: 新 kind `context`、provenance/confidence/validity フィールド追加
- **インパクト**: LlamaIndex・LangChain との統合デモが書ける
- **実装コスト**: 低（既存 kind 追加パターンと同じ）

### #108: Delegation depth tracking
- **目的**: `max_delegation_depth` でエフェクト委譲の深さを制限
- **変更**: FC-E010 拡張、checker に depth 検証追加、runtime depth counter
- **依存**: #107（マージ済み）
- **実装コスト**: Medium（ランタイム追跡が要注意）

### #110: Multi-layer LLM interface contracts
- **目的**: `locality: retain|pass` でエフェクトの層間伝播を宣言
- **変更**: 新フィールド `locality`、DELEGATION_LEAK エラーコード追加
- **背景**: persona layer ↔ capability layer 間の無型インターフェース問題を解決
- **実装コスト**: Medium（フィールドトラッキングが最難所）

### #112: Routing hints as declarative qualifiers
- **目的**: `complexity_tier`・`persona_required` 等でルーティングを宣言的に
- **変更**: 新 qualifier 群（complexity_tier, persona_required, memory_depth）、FC チェッカー opt-in パス
- **依存**: #110 推奨（単独実装も可）
- **実装コスト**: Medium

---

## Boss へのアクション依頼

以下のどれか1件でも「GO」をいただければ実装を開始できます:

1. **#111 のみ** → 最小コスト・最速（1〜2日）
2. **#108 + #111** → Phase 2 + RAG（3〜4日）
3. **全件一括** → v1.1 フルリリース（1〜2週間）

詳細は各 issue と設計ドキュメントを参照ください。
