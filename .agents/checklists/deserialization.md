---
id: deserialization
tags: [deserialize, xml]
langs: [any]
categories: [insecure-deserialization, xxe, prototype-pollution]
---
- 外部入力を安全でないデシリアライザに渡しているか（`pickle.loads`, `yaml.load`（SafeLoader なし）, `Marshal.load`, Java `ObjectInputStream`, .NET `BinaryFormatter`, PHP `unserialize`）
- XML パーサで外部実体（DTD）を無効化しているか（XXE）
- JS: 外部入力のキーでオブジェクトを再帰マージしていないか（`__proto__`, `constructor` を弾いているか）→ プロトタイプ汚染
