---
id: memory-safety
tags: [memory-unsafe]
langs: [c, cpp, rust]
categories: [memory-safety, integer-overflow]
---
- `strcpy`, `strcat`, `sprintf`, `gets`, 長さ未確認の `memcpy` に外部入力の長さが関わるか
- 外部入力から計算したサイズでの確保・インデックス（整数オーバーフロー、符号の混同）
- 解放後の使用、二重解放の可能性がある所有権の扱い
- Rust: `unsafe` ブロック内での境界外アクセス・生ポインタの扱い
