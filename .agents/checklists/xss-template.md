---
id: xss-template
tags: [template, http-input]
langs: [any]
categories: [xss, ssti, open-redirect]
---
- 自動エスケープを無効化して外部入力を出力していないか（`dangerouslySetInnerHTML`, `v-html`, `innerHTML`, `|safe`, `mark_safe`, `html_safe`, `raw`, `{{{ }}}`）
- 外部入力をテンプレート**そのもの**として描画していないか（`render_template_string(user_input)`, `new Function`）→ SSTI
- 外部入力の URL を `href`/`src`/リダイレクト先に使っているか（`javascript:` スキーム、オープンリダイレクト）
- JSON を `<script>` 内に埋め込むときにエスケープしているか
- React/Vue/Angular 等で通常のバインディングだけなら候補にしない（自動エスケープされる）
