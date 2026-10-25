---
id: crypto-random
tags: [crypto]
langs: [any]
categories: [weak-crypto, weak-random]
---
- トークン・パスワード・ID 生成に暗号論的でない乱数（`Math.random`, Python `random`, `rand()`）を使っていないか
  - 安全: `secrets`, `crypto.randomBytes`, `crypto.getRandomValues`, `SecureRandom`
- ECB モード、固定 IV/nonce、自前の暗号アルゴリズム
- 証明書検証の無効化（`verify=False`, `rejectUnauthorized: false`, `InsecureSkipVerify: true`）
- MD5/SHA1 は**整合性チェック以外**（署名・パスワード）に使っている場合のみ候補
