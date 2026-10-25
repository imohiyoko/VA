# 学習内容の分類

run の後、retrospective は得られた知見を次の3種類に分ける。

| 種類 | 例 | 置き場所 | 上流へ |
|---|---|---|---|
| `target` | 「この repo の `/internal/*` は社内 VPN 前提」「`legacy/` は未使用」 | `operator/targets/<target>/learnings.md` | 出さない |
| `generic` | 「Next.js の Server Actions は CSRF の観点を追加すべき」「チェックXは誤検知が多い、条件Yを確認すべき」 | `operator/upstream-candidates/` | **出す** |
| `model` | 「モデルMは依存の到達性を確かめずに high を付けがち」 | `operator/upstream-candidates/`（type: model） | **出す** |

## 判断基準

**generic と言えるのは、対象のリポジトリ名・ドメイン・構造を知らなくても意味が通り、他のリポジトリにも当てはまるもの。**
迷ったら `target` にする。上流へ出すのは後からでもできるが、public に出したものは取り消せない。

## generic / model にする根拠

1回の観測だけで手法を変えない。候補には必ず根拠を付ける:
- 観測回数（何回の run で、いくつの target で見たか）
- 具体的な結果（誤検知 N 件、見逃し N 件 など。対象名は伏せる）

候補は `operator/upstream-candidates/<YYYYMMDD>-<slug>.md` に、次の形式で書く:

```markdown
---
type: generic | model
area: methodology/02-code-review | prompts/tasks/review-file | checklists/<id> | model-profiles/<model> | ...
model: <model のとき対象モデル ID>
observations: <回数>
targets_count: <対象数>
proposed_bump: minor | patch
status: draft
---
## 何が起きたか
## 提案する変更（どのファイルのどこをどう変えるか）
## 期待される効果
```

`status: draft` → 人がレビューして `ready` に変える → 上流提案エージェントが PR にする → `submitted` → VA でマージされたら `merged`。
