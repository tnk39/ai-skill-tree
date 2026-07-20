# AI Partner Skill Tree / Living AI Skill Graph v2

The existing root `index.html` remains the published legacy site. The v2 implementation is additive on `v2-living-skill-graph` and is local-first: SQLite is authoritative, `events.jsonl` is an audit mirror, FastAPI and stdio MCP expose the graph locally, and `public/public-snapshot.json` is a filtered static projection.

## Local v2 run

```powershell
.\.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8765
.\.venv\Scripts\python.exe -m pytest -q
```

No API keys, paid services, Codex auto-start, remote push, or GitHub Pages deployment is performed by v2. The local graph UI deliberately uses browser SVG rather than a D3 CDN dependency so it makes no external browser request.

---

AI Partner Skill Tree は、ユーザーが設定した到達目標を頂点に置き、その目標を達成するために AI パートナーが保有・獲得・検証・改善するスキルを可視化する静的 Web サイトです。

ユーザーはプレイヤーではなく、目標所有者、優先順位決定者、成果の最終判定者です。プレイヤーおよび成長対象は AI パートナーです。AI はスキル所有者、実行担当、検証担当、改善担当として、ユーザーとタッグを組んで目標地点を攻略します。

## 主な機能

- 目的別 AI スキル樹形図
- 目標の切り替え
- 新規目標の追加
- AI スキルの追加・編集・削除
- スキル状態の 5 段階管理
- 依存スキル、解放条件、証拠・実績の記録
- スキル状態に基づく目的到達率の自動計算
- 次の解放候補の表示
- 攻略ログの追加
- JSON 書き出し、JSON 読み込み
- localStorage によるブラウザ内保存
- PC およびスマートフォン対応

## スキル状態

- 未解放
- 試用可能
- 実証済み
- 安定運用
- 改善待ち

## 保存方式

保存方式はブラウザの localStorage です。外部 DB、ログイン機能、サーバー保存は使っていません。

- PC とスマートフォンのデータは自動同期されません。
- 別ブラウザには自動同期されません。
- ブラウザデータを削除すると保存内容が消える可能性があります。
- 重要なデータは JSON 書き出しでバックアップすることを推奨します。

## 使い方

`index.html` をブラウザで開くだけで利用できます。GitHub Pages ではリポジトリ直下の `index.html` が公開ページになります。

## 公開予定 URL

https://tnk39.github.io/ai-skill-tree/
