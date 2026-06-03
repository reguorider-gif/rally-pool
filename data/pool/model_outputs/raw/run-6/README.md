# Model Output Dropbox — run-6

## 用途

把每个模型对 run-6 的原始回答（raw output）放到此目录，供 `ops/ai_judge_daily_pool.py ingest` 读取。

## 文件命名规则

每个文件名必须匹配 `data/pool/model_accounts/current.json` 中的 `model_account` 字段：

```
<model_account>.txt
```

例如：

```
data/pool/model_outputs/raw/run-6/
├── DeepSeek-V3.2.txt
├── Qwen3-235B-A22B.txt
├── GLM-4.5.txt
├── Hunyuan-2.0.txt
├── Ernie-5.0.txt
├── ByteDance-Seed.txt
├── Moonshot-K2.5.txt
├── MiniMax-M1.txt
├── Yi-Lightning-3.0.txt
├── Baidu-DeepSeek.txt
├── Step-3.5.txt
├── SenseNova-Nova.txt
└── InternLM-3.0.txt
```

## 内容要求

- 必须是该模型对 run-6 prompt 的原始回答，不得复制 run-5 的输出。
- 即使是 Markdown 或自然语言格式，也原样保存（不要人工修成 JSON）。
- 空文件会导致该席位被标记为 `placeholder_only`。
- 文件大小应 > 100 bytes（否则可能是空输出）。

## 状态说明

运行 `python3 ops/check_model_output_dropbox.py --round run-6` 后，状态可为：

| 状态 | 含义 |
|---|---|
| `waiting_for_manual_ingest` | 0 个文件，`ingest` 不会执行 |
| `partial_outputs_found` | 1–12 个文件，可部分 ingest |
| `ready_for_ingest` | 13 个文件，可完整 ingest |

## 下一步

文件放好后执行：

```bash
python3 ops/ai_judge_daily_pool.py ingest \
  --round run-6 \
  --input-dir data/pool/model_outputs/raw/run-6

python3 ops/classify_model_output.py --round run-6
python3 ops/validate_model_outputs.py --round run-6 --date 2026-06-03 --snapshot-label T-1h
```
