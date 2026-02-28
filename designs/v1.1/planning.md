# NAIL v1.1 設計計画

> **ドキュメントの目的**: v1.0 RC 後に Boss と設計を議論するための資料。
> 2026-03-01 夜の設計セッション（DeepMind論文との対話）から生まれたアイデアを整理する。

---

## 1. v1.0 の成果と、v1.1 への課題

### 1.1 v1.0 で凍結したもの

v1.0 では以下を「コア仕様」として凍結した。これらは v1.1 以降も変更しない（後方互換性の保証対象）。

| 項目 | 状態 |
|------|------|
| **L0–L3 言語層** (Primitive / Expression / Task / Delegation) | ✅ 凍結 |
| **FC Standard** (Function Call 標準フォーマット) | ✅ 凍結 |
| **Effect System** (FS / NET / EXEC / UI / STATE) | ✅ 凍結 |
| **Delegation Phase 1** (qualifier 構文 + `reversible` メタデータ) | ✅ 凍結（PR #109） |
| **型規則 v1** | ✅ 凍結 |

### 1.2 v1.0 で意図的に延期したもの

以下は仕様として認識しているが、v1.0 スコープ外として残した。

| 項目 | 理由 |
|------|------|
| **Delegation Phase 2** (`max_delegation_depth` / authority gradient) | 設計オプションが未決定（静的 vs 動的） |
| **NATP** (NAIL Agent Transfer Protocol) | nail-a2a が v0.1.0 段階、プロトコル仕様検討前 |
| **WASM compilation target** | v1.0 stable 後のランタイム整備が先 |
| **Async / Concurrency model** | コミュニティフィードバック待ち |
| **L4 Memory safety layer** | v1.1 以降の上位層として保留 |
| **Effect System 拡張** (AUDIT / DELEG) | Phase 2 と同時設計が望ましい |

### 1.3 v1.1 の設計原則

> **「凍結した核を広げず、周辺を充実させる」**

- L0–L3 / FC Standard / Effect System コアには**手を加えない**
- 既存の拡張点（qualifier 構文 / effect label 名前空間）を使って機能を追加する
- 後方互換性: v1.0 準拠の仕様書・実装は v1.1 でも valid であり続ける
- 破壊的変更が必要な場合は必ず Boss 承認 + Issue 化してから着手

---

## 2. Delegation Phase 2 (Issue #108)

### 2.1 `max_delegation_depth` の設計オプション

#### 課題

Phase 1 で `can_delegate` qualifier は定義済み。Phase 2 では「何段階まで再委譲を許可するか」を表現する `max_delegation_depth` を追加したい。現在の未解決問題は **静的 vs 動的** の判断。

#### 静的実装案

コンパイル時（または lint 時）にコールグラフ解析を行い、depth 宣言の整合性をチェックする。

```nail
# 例: depth=2 を宣言したタスクが depth=3 のタスクを呼ぶ → 静的エラー
task A { can_delegate: { max_delegation_depth: 2 } }
task B { can_delegate: { max_delegation_depth: 3 } }  # A → B は NG
```

**メリット:**
- ランタイムコストゼロ
- 静的保証が明確

**デメリット:**
- モジュール境界をまたぐ場合（A が外部ライブラリの B を呼ぶ）にコールグラフが不完全になる
- 動的ディスパッチ（ツール名を変数で渡す）には対応できない
- ツールチェーンが複雑化（言語サーバ / lint ルールが必要）

#### 動的実装案

`mcp-fw`（NAIL ランタイム / フレームワーク）でランタイム hop カウンターを管理し、depth 超過時にエラーを返す。

```nail
# 実行時コンテキストに hop_count が注入される
task write_sensitive {
  effects: [FS]
  can_delegate: { max_delegation_depth: 1 }
}
# runtime: A → B (hop=1, OK) → C (hop=2, REJECT: depth exceeded)
```

**メリット:**
- 動的ディスパッチにも対応
- モジュール境界を気にしない
- 実装が単純（hop カウンターをコンテキストに付与するだけ）

**デメリット:**
- ランタイムコスト（コンテキスト伝播）
- ランタイムエラーが実行時まで検出されない

#### 推奨: 動的優先

**動的実装を v1.1 のデフォルトとして採用する。**

理由:
1. NAIL のターゲット環境（エージェントフレームワーク / LLM ツールチェーン）では動的ディスパッチが多い
2. 静的実装に必要な「モジュール境界の定義」は NAIL の現在のスコープ外
3. mcp-fw は既にコンテキスト伝播の仕組みを持つ — hop カウンターの追加は低コスト
4. 将来的に静的チェックを追加する「静的 + 動的の両立」パスを閉じない

> **Note**: 静的チェックは将来の lint ツール（`nail-lint`）として別途提供できる。v1.1 では dynamic のみ。

### 2.2 Authority Gradient: Origin 追跡

委譲チェーン `A → B → C → D` において、D が持つ権限は「元の呼び出し元 A の権限に依存する」という考え方。

```
origin_id: A のエージェント ID を伝播し続ける
authority: A の grant に紐づいた効果範囲
```

設計ポイント:
- `origin_id` はコンテキストの immutable フィールドとして伝播
- 各 hop で `hop_count++`、`origin_id` は変更しない
- D が FS 操作を行う際、ランタイムは `origin_id = A` の grant を参照して許可判定

### 2.3 ChatGPT 分析（Issue #108 コメント）の要点

> （Issue #108 の ChatGPT 分析コメントより要約）
>
> - `max_delegation_depth` は「信頼の伝播距離」を制限するセーフティネットである
> - 静的解析では "open world assumption" が崩れる（外部エージェントを静的に知れない）
> - 動的 hop カウンターは A2A / MCP プロトコルの "request context" に自然にマッピングできる
> - authority gradient の概念は Google の BeyondCorp モデルや OAuth のスコープ継承と類似している

---

## 3. `reversible: false` の活用（Phase 2）

### 3.1 Phase 1 での位置づけ（参考）

Phase 1（PR #109）では `reversible` は **メタデータのみ**。型規則には影響しない。

```nail
task write_file {
  effects: [FS]
  reversible: false   # 情報として記録するが、型チェックには使わない
}
```

### 3.2 Phase 2 での活用: 不可逆操作の委譲深度制限

Phase 2 では `reversible: false` と `max_delegation_depth` を **組み合わせる**。

**設計案:**

```nail
# 不可逆操作は直接呼び出しのみ許可（depth = 1）
task delete_record {
  effects: [FS, STATE]
  reversible: false
  can_delegate: { max_delegation_depth: 1 }  # 明示的に制限
}

# または、ランタイムがデフォルトルールを持つ
# "reversible: false → max_delegation_depth は暗黙的に 1"
```

**推奨ルール案:**

| 条件 | デフォルト `max_delegation_depth` |
|------|----------------------------------|
| `reversible: true` (default) | 無制限（または設定値） |
| `reversible: false` | **1**（直接呼び出しのみ） |
| 明示的に `max_delegation_depth` を指定 | 指定値が優先 |

**根拠:**
- 不可逆操作（ファイル削除、外部 API への送信、DB 書き込み）は人間が承認したエージェントが直接実行すべき
- 委譲チェーンを通じて「誰が実行したのかわからない」状態を防ぐ
- ZoI（Zone of Indifference）理論との整合: 上位エージェントが委任を承認している操作のみ伝播させる

---

## 4. NATP (NAIL Agent Transfer Protocol)

### 4.1 現在の状態

- **post-v1.0 reserved** — v1.0 仕様書では名称のみ予約
- `zyom45/nail-a2a` リポジトリが v0.1.0 をリリース済み（NAIL を A2A プロトコルのアダプター層として実装する実験的プロジェクト）

### 4.2 コンセプト

> NAILをエージェント間通信の **中間言語（intermediate language）** として使う

従来の状況:
```
Agent A --[独自プロトコル]--> Agent B
```

NATP の目指す姿:
```
Agent A --[NAIL task spec]--> NATP layer --[NAIL task spec]--> Agent B
```

NAIL の task 宣言（effects + grants + qualifiers）が「何をどこまで許可するか」の envelope として機能する。

### 4.3 nail-a2a プロジェクトとの関係

| 項目 | nail-a2a (現在) | NATP v1.0 (目標) |
|------|----------------|-----------------|
| スコープ | Google A2A プロトコルへのアダプター | プロトコル非依存の NAIL envelope |
| バージョン | v0.1.0 | 未定義 |
| 委譲チェーン追跡 | なし | あり（origin_id + hop_count） |
| Effects 伝播 | なし | あり |
| Grant 伝播 | なし | あり |

### 4.4 NATP v1.0 の要件案

1. **NAIL spec を envelope として使う**
   - `tasks` セクション: 実行するタスクの宣言
   - `effects` セクション: 必要な副作用の宣言
   - `grants` セクション: 委譲元が付与する権限

2. **A2A プロトコルとの互換性**
   - Google A2A / Anthropic MCP のメッセージ形式にマッピングできること
   - NAIL spec は JSON/YAML でシリアライズ可能（現在も可）

3. **委譲チェーン追跡**
   - `origin_id`: 委譲の起点エージェント ID
   - `hop_count`: 現在の委譲深度
   - `chain`: `[A_id, B_id, C_id]` の形式で委譲経路を記録

### 4.5 nail-a2a v0.2 への期待

- NATP の draft spec を nail-a2a v0.2 で実装する（PoC として）
- v0.2 で得たフィードバックを NATP v1.0 仕様に反映
- NAIL v1.1 spec に NATP v1.0 を含める（または別ドキュメントとして併記）

---

## 5. Effect System の拡張候補

### 5.1 既存の Effect Labels（v1.0）

```
FS     — ファイルシステムへのアクセス
NET    — ネットワーク通信
EXEC   — プロセス実行
UI     — ユーザーインターフェース操作
STATE  — 状態変更（メモリ / セッション）
```

### 5.2 新規候補: `AUDIT`

**概念**: 監査ログへの書き込み専用の effect label。

```nail
task log_event {
  effects: [AUDIT]   # 監査ログへの書き込みのみ
}
```

**設計意図:**
- `FS` は広すぎる（任意のファイル読み書き）
- 監査ログは「書き込みのみ、削除不可、改ざん不可」という特殊な FS アクセスパターン
- セキュリティポリシー上、`AUDIT` を持つタスクは常に許可するという設定が可能
- Compliance / コンプライアンス要件に対応しやすくなる

**制約案:**
- `AUDIT` effect を持つタスクは `reversible: false` が暗黙的
- `AUDIT` は append-only（削除・上書きを含む操作は `FS` を使うべき）

### 5.3 新規候補: `DELEG`

**概念**: 委譲操作そのものを effect として追跡する。

```nail
task delegate_task {
  effects: [DELEG]   # 委譲アクション自体を追跡
  can_delegate: { max_delegation_depth: 2 }
}
```

**設計意図:**
- 「このタスクは他のエージェントに委譲を行う」ことを明示的に宣言
- ランタイムが `DELEG` を検出した際に委譲チェーンの記録を開始できる
- `DELEG` を持たないタスクからの委譲を禁止するセキュリティポリシーが書ける

### 5.4 Effect Composition

複数 effect の合成宣言を明示的にサポートする。

```nail
task read_and_send {
  effects: [FS | NET]   # FS と NET の両方が必要
}

task audit_and_send {
  effects: [AUDIT | NET]  # 監査ログに書きつつネット送信
}
```

**現在の状態**: v1.0 では `effects: [FS, NET]` の配列形式で複数 effect を表現できる。
`|` 形式は syntactic sugar として v1.1 で検討。

**設計ポイント:**
- `FS | NET` は「どちらか一方が必要」ではなく「両方必要」（AND セマンティクス）
- 将来的に `FS & NET`（AND）vs `FS | NET`（OR、どちらか実行する可能性あり）の区別も検討余地あり

---

## 6. コミュニティ戦略

### 6.1 リリーススケジュールとの対応

```
2026-03-27 (予定)  v1.0 RC リリース
                    └→ HN Show HN 投稿
PR #109 マージ後    └→ Reddit r/ProgrammingLanguages
v1.0 stable 後      └→ Dev.to 技術記事 (English)
                    └→ Zenn 日本語記事
```

### 6.2 HN Show HN

- **タイミング**: v1.0 RC リリース後（2026-03-27 予定）
- **アカウント**: `naillang`（カルマ積み中）
- **テーマ**: **Zone of Indifference × NAIL の型システム**
  - ZoI 理論（上位エージェントが「どうでもいい」操作に委任する領域）を軸にした説明
  - 「なぜ NAIL が必要か」を ZoI の文脈で語る
  - DeepMind の safety 論文との接続（今夜の設計セッションの成果）
- **ポイント**: 純粋な技術的アイデアとして提示。「LLM エージェントの委譲に型を付ける」

### 6.3 Reddit r/ProgrammingLanguages

- **タイミング**: PR #109 マージ後
- **フォーカス**: delegation qualifiers の型システム的側面
- **トーン**: 学術・型理論寄り

### 6.4 Dev.to（English）

- **タイミング**: v1.0 stable 後
- **テーマ**: "Delegation qualifiers in NAIL: controlling trust propagation in multi-agent systems"
- **内容**: Phase 1 実装解説 + Phase 2 の設計思想

### 6.5 Zenn（日本語）

- **タイミング**: Dev.to 記事と同時期
- **テーマ**: 「エージェント間委譲に型を付ける — NAIL 言語の設計思想」
- **内容**: 日本語コミュニティ向けに ZoI 理論から丁寧に解説

---

## 7. v1.1 ロードマップ（暫定）

| 機能 | 依存 | 優先度 | 備考 |
|------|------|--------|------|
| **Delegation Phase 2** (`max_delegation_depth`, authority gradient) | Phase 1 マージ（PR #109） | **P1** | Issue #108 |
| **`reversible: false` + depth 制限の統合** | Phase 2 設計確定 | **P1** | Phase 2 と同時 |
| **Effect 拡張** (`AUDIT`, `DELEG`) | Phase 2 設計確定 | **P1** | Phase 2 と同時設計 |
| **NATP v1.0 spec** | nail-a2a v0.2 PoC | **P2** | nail-a2a との協調 |
| **WASM compilation target** | v1.0 stable | **P2** | ランタイム整備が先 |
| **Effect Composition 構文** (`\|` 形式) | コミュニティフィードバック | **P2** | syntactic sugar |
| **Async / Concurrency model** | コミュニティフィードバック | **P3** | 設計未着手 |
| **L4 Memory safety layer** | v1.1 stable | **P3** | 上位層として保留 |

### 優先度の定義

| 優先度 | 意味 |
|--------|------|
| P1 | v1.1 の必須機能。これがないと v1.1 と呼べない |
| P2 | v1.1 に含めたいが、遅延しても v1.2 で対応可能 |
| P3 | 長期的なビジョン。コミュニティ成長後に着手 |

---

## 付録: 今夜の設計セッションのメモ

**日時**: 2026-03-01  
**背景**: DeepMind の multi-agent safety 論文との対話から生まれた以下の洞察を整理した。

1. **ZoI (Zone of Indifference) との接続**
   - 上位エージェントが「委譲していい」と判断する操作 = ZoI に収まる操作
   - `max_delegation_depth` は ZoI の「深さ」を型として表現したもの
   - 不可逆操作（`reversible: false`）は ZoI を外れやすい → depth 制限が自然

2. **静的 vs 動的の結論**
   - Open world（外部エージェントを知れない）前提では動的が現実的
   - 静的 lint は将来の `nail-lint` ツールとして追加可能

3. **NATP の位置づけ明確化**
   - NAIL は "language" だが NATP は "protocol"
   - nail-a2a が NATP の PoC として育ちつつある
   - v1.1 では spec のみ（実装は nail-a2a に委ねる）

---

*このドキュメントは Boss との設計議論のたたき台です。Issue #107/#108 はこのドキュメント確認後に更新予定。*
