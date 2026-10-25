# 参考 4: シークレット

> 実際の実行は `scripts/va.py`（ツール実行）と `checklists/` が担う。ここは人が読むための背景説明。

1. 作業ツリー: `gitleaks detect --no-git --redact`
2. 履歴: `gitleaks detect --redact`（shallow clone の場合はその旨を記録）
3. ツールが無い場合は、キー形式（`AKIA`, `ghp_`, `sk-`, `xox`, `-----BEGIN` 等）と
   `password|secret|token|api_key` 付近の代入を Grep で確認する

## 判定
- テスト用ダミー・例示値（`example`, `dummy`, `xxxx`）は除外するが、本物の形式に一致するものは除外しない
- 履歴にだけ残っている場合も finding にする（ローテーションが必要なため）

## 記録のルール
値そのものは**絶対に**書かない。`先頭4文字…(長さN)` と場所、種類だけを書く。
