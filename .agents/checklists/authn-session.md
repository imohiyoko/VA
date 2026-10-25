---
id: authn-session
tags: [auth, session]
langs: [any]
categories: [authn, session, csrf, cors]
---
- JWT: 署名を検証しているか、`alg` を固定しているか（`none` や HS/RS の混同）、有効期限を確認しているか
- パスワード: bcrypt/scrypt/argon2/PBKDF2 以外（MD5, SHA1, SHA256 単体）で保存していないか。比較は定数時間か
- ログイン・パスワードリセット・OTP にレート制限や試行回数制限があるか
- リセットトークン・セッション ID が推測可能、または期限なしになっていないか
- Cookie に `Secure`, `HttpOnly`, `SameSite` が付いているか
- 状態を変える Cookie 認証のリクエストに CSRF 対策があるか
- CORS: Origin をそのまま反射、または `*` と credentials を併用していないか
