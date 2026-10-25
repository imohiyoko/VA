# 運用リポジトリ固有の調整

共通層（VA）を直接編集せず、この運用リポジトリだけで効かせたいルールをここに書く。

`- [summarize] ...` / `- [review] ...` / `- [triage] ...` / `- [all] ...` で始まる行は、
該当タスクのプロンプト末尾に自動で追加される（英語・命令形・1行1ルール）。

<!-- 例:
- [triage] Services in this organization run behind an authenticating proxy; treat "unauthenticated" as "user" unless the route is in the public allowlist.
-->

汎用的に役立つと分かったルールは `upstream-candidates/` に移して VA へ提案する。
