---
id: llm-app
tags: [llm]
langs: [any]
categories: [llm-prompt-injection, llm-excessive-agency, llm-data-leak]
---
- 外部由来のテキスト（Web ページ、メール、ファイル、ユーザー入力）を LLM に渡し、その出力でツール実行・コード実行・DB 更新をしているか
- LLM の出力を検証せずに HTML 描画・SQL・シェルに渡しているか
- システムプロンプトや他ユーザーのデータが、プロンプト経由で取り出せる構成か
- LLM に与えたツールの権限が必要以上に広いか（ファイル削除、任意 URL 取得、送信）
