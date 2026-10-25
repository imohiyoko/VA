---
id: command-injection
tags: [shell]
langs: [any]
categories: [command-injection]
---
- シェル経由の実行（`shell=True`, `os.system`, `exec()`/`child_process.exec`, バッククォート, `system()`, `Runtime.exec(String)`）に外部入力が入るか
  - 安全寄り: 引数を配列で渡す（`subprocess.run([...])`, `execFile`, `spawn` の shell なし）
- 配列で渡していても、入力が `-` で始まるとオプションとして解釈される箇所（引数インジェクション）。`--` で区切っていれば安全
- `eval`, `new Function`, `exec`（Python）等、文字列をコードとして実行する箇所に外部入力が入るか
