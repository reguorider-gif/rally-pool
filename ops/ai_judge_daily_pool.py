#!/usr/bin/env python3
"""
ops/ai_judge_daily_pool.py
P11.0 AI Judge 每日自动运行入口

用法:
  python3 ops/ai_judge_daily_pool.py run --date 2026-06-03 --round run-6 --dry-run
  python3 ops/ai_judge_daily_pool.py run --date 2026-06-03 --round run-6 --generate-prompts-only
  python3 ops/ai_judge_daily_pool.py ingest --round run-6 --input-dir data/pool/model_outputs/raw/run-6
  python3 ops/ai_judge_daily_pool.py status --round run-6

职责:
  1. 生成每轮 run manifest（运行清单）
  2. 为每个模型生成专属 prompt/context packet
  3. 支持 --generate-prompts-only（只生成 prompt，等待人工采集）
  4. 支持 ingest 原始输出到标准化目录
  5. 串联 pipeline: classify → validate → settle → daily_report
  6. 不强制依赖浏览器自动化
  7. 不编造模型输出
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------- 项目根目录 ----------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "pool"
sys.path.insert(0, str(ROOT_DIR))

try:
    from ops.generate_eligible_board import build_eligible_board, write_eligible_board
except Exception:  # pragma: no cover - script fallback for unusual import contexts
    build_eligible_board = None
    write_eligible_board = None

# ---------- 默认 snapshot label ----------
DEFAULT_SNAPSHOT_LABEL = "T-1h"

# ---------- 合规声明 ----------
COMPLIANCE_NOTICE = (
    "【合规与实验边界】\n"
    "这是虚拟 GP 预测研究，不涉及真钱下注，不构成现实博彩建议。\n"
    "所有投注均为模拟，仅用于算法研究与模型评估。"
)


def _now_iso():
    """返回当前 UTC ISO 时间戳"""
    return datetime.now(timezone.utc).isoformat()


def _read_json(relative_path, default=None):
    """安全读取 JSON 文件"""
    full_path = DATA_DIR / relative_path
    if not full_path.exists():
        return default
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _odds_snapshot_relpath(date_str, snapshot_label, provider):
    if provider and provider != "manual_stub":
        return f"odds_snapshots/{date_str}_{snapshot_label}_{provider}.json"
    return f"odds_snapshots/{date_str}_{snapshot_label}.json"


def _read_odds_snapshot(date_str, snapshot_label, provider="auto"):
    """
    读取 prompt 用赔率快照。
    auto 模式优先采用真实 provider 快照，避免已配置真实赔率后仍把 manual_stub
    的 valid_odds_rows=0 发给模型。
    """
    candidates = []
    if provider and provider != "auto":
        candidates.append(_odds_snapshot_relpath(date_str, snapshot_label, provider))
    else:
        index = _read_json("odds_snapshots/index.json", default={}) or {}
        indexed = []
        for snap in index.get("snapshots", []):
            if snap.get("date") != date_str or snap.get("snapshot_label") != snapshot_label:
                continue
            rel = snap.get("path", "").replace("data/pool/", "")
            if not rel:
                continue
            provider_name = snap.get("provider", "")
            provider_rank = 1 if provider_name and provider_name != "manual_stub" else 0
            indexed.append((provider_rank, snap.get("valid_odds_rows", 0), rel))
        for _, _, rel in sorted(indexed, reverse=True):
            candidates.append(rel)
        candidates.append(_odds_snapshot_relpath(date_str, snapshot_label, "the_odds_api"))
        candidates.append(_odds_snapshot_relpath(date_str, snapshot_label, "manual_stub"))

    seen = set()
    for rel in candidates:
        if rel in seen:
            continue
        seen.add(rel)
        data = _read_json(rel, default=None)
        if not isinstance(data, dict):
            continue
        summary = data.get("summary") or {}
        if provider == "auto":
            if data.get("provider") != "manual_stub" and (summary.get("valid_odds_rows", 0) > 0 or data.get("odds")):
                return rel, data
            if data.get("provider") == "manual_stub" and not any("_the_odds_api" in c for c in candidates[:1]):
                return rel, data
        else:
            return rel, data

    fallback = _odds_snapshot_relpath(date_str, snapshot_label, "manual_stub")
    return fallback, _read_json(fallback, default={}) or {}


def _write_json(relative_path, data, indent=2):
    """安全写入 JSON 文件"""
    full_path = DATA_DIR / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def _load_or_generate_eligible_board(round_id, date_str, snapshot_label, provider):
    """Load P14 eligible board, generating it from provider odds when possible."""
    rel = f"odds/eligible_board/{round_id}.json"
    data = _read_json(rel, default=None)
    if isinstance(data, dict) and data.get("items"):
        return rel, data
    if build_eligible_board is None or write_eligible_board is None:
        return rel, {"version": "p14.0", "round_id": round_id, "items": [], "summary": {"eligible_board_rows": 0}}
    provider_name = provider if provider and provider != "auto" else "the_odds_api"
    board = build_eligible_board(
        round_id=round_id,
        date=date_str,
        snapshot_label=snapshot_label,
        provider=provider_name,
    )
    write_eligible_board(board)
    return rel, board


def _load_model_accounts():
    """加载当前活跃模型席位"""
    data = _read_json("model_accounts/current.json", default=None)
    if data and "models" in data:
        return data["models"]
    # fallback
    return [
        {"model_account": "gemini", "display_name": "Gemini", "seat_id": "gemini"},
        {"model_account": "chatgpt", "display_name": "ChatGPT", "seat_id": "chatgpt"},
        {"model_account": "yuanbao", "display_name": "元宝", "seat_id": "yuanbao"},
        {"model_account": "wenxin", "display_name": "文心", "seat_id": "wenxin"},
        {"model_account": "deepseek", "display_name": "DeepSeek", "seat_id": "deepseek"},
        {"model_account": "mimo", "display_name": "MiMo", "seat_id": "mimo"},
        {"model_account": "kimi", "display_name": "Kimi", "seat_id": "kimi"},
        {"model_account": "qwen", "display_name": "通义", "seat_id": "qwen"},
        {"model_account": "xai", "display_name": "xAI", "seat_id": "xai"},
        {"model_account": "minimax", "display_name": "MiniMax", "seat_id": "minimax"},
        {"model_account": "doubao", "display_name": "豆包", "seat_id": "doubao"},
        {"model_account": "meta", "display_name": "Meta AI", "seat_id": "meta"},
    ]


def _build_run_marker(round_id, date_str):
    """构建 run_marker"""
    date_clean = date_str.replace("-", "")
    return f"AI_JUDGE_RUN_MARKER:POOL_{round_id.upper()}_{date_clean}"


def _compact_json(value, max_chars=6000):
    """安全压缩 JSON 为字符串，超出截断。"""
    try:
        text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        text = json.dumps({"error": f"json serialization failed: {exc}"}, ensure_ascii=False)
    if len(text) > max_chars:
        return text[:max_chars] + "\n...<truncated>"
    return text


def _is_real_model_output(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 50:
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:200]
    except Exception:
        return False
    return not head.lstrip().startswith("[WAITING")


def _build_prompt(seat, round_id, date_str, run_marker, snapshot_label,
                  match_results, odds_snapshot, eligible_board, leaderboard, previous_report):
    """
    为单个模型构建专属 prompt。
    使用 json.dumps() 输出 JSON 示例，用 "\\n".join(lines) 拼接文本，
    完全避免手写 JSON 大括号与 Python 字符串格式化冲突。
    """
    model_account = seat.get("model_account") or seat.get("seat_id") or seat.get("id")
    seat_id = seat.get("seat_id") or model_account
    display_name = seat.get("display_name") or model_account

    # ---------- P15 JSON 示例通过 dict + json.dumps 生成 ----------
    no_bet_output = {
        "seat_id": seat_id,
        "round_id": round_id,
        "bets": [],
        "no_bet_reason": "No provider-covered board row has positive expected value.",
        "sources_checked": [],
    }

    strict_schema_example = {
        "seat_id": seat_id,
        "round_id": round_id,
        "bets": [{
            "board_id": f"{round_id}:EXAMPLE_PROVIDER_ODDS_ROW_ID",
            "stake_gp": 100,
            "rationale": "Board row selected from eligible_board only; market and selection match the provider row.",
            "risk": "Cancel or reduce if lineup, injury, weather, or odds movement invalidates the edge.",
        }],
        "no_bet_reason": None,
        "sources_checked": [],
    }

    # ---------- 数据摘要 ----------
    odds_summary_data = {
        "snapshot_label": odds_snapshot.get("snapshot_label") if isinstance(odds_snapshot, dict) else None,
        "provider": odds_snapshot.get("provider") if isinstance(odds_snapshot, dict) else None,
        "summary": odds_snapshot.get("summary") if isinstance(odds_snapshot, dict) else {},
        "warning": "Do not bet from this snapshot directly. Use eligible_board rows only.",
    }

    board_items = eligible_board.get("items", []) if isinstance(eligible_board, dict) else []
    eligible_board_summary = _compact_json({
        "summary": eligible_board.get("summary", {}) if isinstance(eligible_board, dict) else {},
        "items": board_items,
        "warning": (
            "Only these provider-covered rows are eligible. Every bets item "
            "must cite board_id exactly; odds_row_id is resolved from the board row."
        ),
    }, max_chars=18000)
    results_summary = _compact_json(match_results)
    odds_summary = _compact_json(odds_summary_data)
    leaderboard_summary = _compact_json(leaderboard)
    previous_report_summary = _compact_json(previous_report)

    # ---------- 拼接 ----------
    lines = [
        run_marker,
        "",
        "# AI Judge 赛事预测池独立模型席位",
        "",
        f"seat_id: {seat_id}",
        f"model_account: {model_account}",
        f"display_name: {display_name}",
        f"round_id: {round_id}",
        f"date: {date_str}",
        "",
        COMPLIANCE_NOTICE,
        "",
        "## 当前任务",
        "你是 AI Judge 赛事预测池中的一个独立模型席位。",
        "你必须基于给定 eligible_board、赛果状态、资金/风控约束，输出 P15 单一 JSON 投注单。",
        "本轮有一个 Banker Judge（虚拟庄家/法官）在管理比赛池：它会根据排行榜、当前筹码、昨日营收、贷款额度和风控规则评估你的表现。",
        "你的目标是在合规的虚拟 GP 研究范围内提升排名；如果排名压力需要，可以申请虚拟贷款，但必须说明贷款用途、预期回报和止损规则。",
        "你还必须主动补充赛事资讯来源到 source_cards，例如伤停、首发、赛程密度、赔率异动、主客场、天气、新闻或统计页；不要把空 source_cards 当作默认答案。",
        "",
        "## 强制防污染要求",
        "- 不要回答旧任务。",
        "- 不要回答狼人杀、警长投票、守卫、平民、预言家等无关任务。",
        "- 不要输出 Markdown。",
        "- 不要输出解释性自然语言。",
        "- 不要输出 JSON 之外的任何内容。",
        "- JSON 必须能被 json.loads 解析。",
        "- 只能从 eligible_board 中选择下注对象。",
        "- 每条 bets 必须引用 eligible_board 内现有的 board_id。",
        "- odds_row_id 可选；如果省略，系统只允许从 board_id 解析。",
        "- 不得自由编写不存在于 eligible_board 的比赛、盘口或赔率。",
        "- 不得把 fallback match 写入 settlement bet。",
        "- 下注 market / selection 必须与 board row 一致；你不需要重复填写 market/selection，validator 会从 board_id 解析。",
        "- 如果没有合适下注，bets 必须为空，并填写 no_bet_reason。",
        "",
        "## Provider-covered eligible_board（唯一可下注来源）",
        eligible_board_summary,
        "",
        "## 赛果状态摘要",
        results_summary,
        "",
        "## 赔率快照摘要",
        odds_summary,
        "",
        "## 当前排行榜/账户摘要",
        leaderboard_summary,
        "",
        "## 上一轮日报摘要",
        previous_report_summary,
        "",
        "## 标准 JSON schema 示例",
        json.dumps(strict_schema_example, ensure_ascii=False, indent=2),
        "",
        "## 如果没有 provider-covered 可下注机会，必须输出以下结构",
        json.dumps(no_bet_output, ensure_ascii=False, indent=2),
        "",
        "【强制输出格式】",
        "你必须只输出一个 JSON 对象。",
        "JSON 顶层必须包含：",
        "- seat_id",
        "- round_id",
        "- bets",
        "- no_bet_reason",
        "- sources_checked",
        "",
        "bets 规则：",
        "- accepted 结算只认 provider-covered board row。",
        "- 每条 bets 必须包含 board_id；缺失会被 rejected_missing_provider_odds 拒收。",
        "- 可选 odds_row_id；如果填写，必须与 board_id 对应行一致。",
        "- stake_gp 必须为正数。",
        "- market、selection、odds 必须由 eligible_board 行决定，不要自由改写。",
        "- 不要写 fallback、manual_stub 或模型自造 odds。",
        "",
        "禁止输出任何 JSON 之外的内容。",
    ]

    return "\n".join(lines)


def _run_pipeline(round_id, date_str, snapshot_label, verbose=False):
    """执行完整 pipeline: classify → validate → settle → daily_report"""
    print("=== Pipeline 开始 ===")
    print()

    # 1. classify_model_output.py
    print("Step 1: classify_model_output.py")
    classify_cmd = f"python3 \"{ROOT_DIR / 'ops' / 'classify_model_output.py'}\" --round {round_id}"
    if verbose:
        classify_cmd += " --verbose"
    print(f"  执行: {classify_cmd}")
    ret = os.system(classify_cmd)
    if ret != 0:
        print(f"  ⚠️  classify 返回非零退出码: {ret}")
    else:
        print("  ✅ classify 完成")
    print()

    # 2. validate_model_outputs.py
    print("Step 2: validate_model_outputs.py")
    validate_cmd = f"python3 \"{ROOT_DIR / 'ops' / 'validate_model_outputs.py'}\" --round {round_id} --date {date_str} --snapshot-label {snapshot_label}"
    if verbose:
        validate_cmd += " --verbose"
    print(f"  执行: {validate_cmd}")
    ret = os.system(validate_cmd)
    if ret != 0:
        print(f"  ⚠️  validate 返回非零退出码: {ret}")
    else:
        print("  ✅ validate 完成")
    print()

    # 3. settle_pool_round.py
    print("Step 3: settle_pool_round.py")
    settle_cmd = f"python3 \"{ROOT_DIR / 'ops' / 'settle_pool_round.py'}\" --round {round_id} --date {date_str} --snapshot-label {snapshot_label}"
    if verbose:
        settle_cmd += " --verbose"
    print(f"  执行: {settle_cmd}")
    ret = os.system(settle_cmd)
    if ret != 0:
        print(f"  ⚠️  settle 返回非零退出码: {ret}")
    else:
        print("  ✅ settle 完成")
    print()

    # 4. generate_daily_pool_report.py
    print("Step 4: generate_daily_pool_report.py")
    report_cmd = f"python3 \"{ROOT_DIR / 'ops' / 'generate_daily_pool_report.py'}\" --date {date_str} --round {round_id}"
    print(f"  执行: {report_cmd}")
    ret = os.system(report_cmd)
    if ret != 0:
        print(f"  ⚠️  report 返回非零退出码: {ret}")
    else:
        print("  ✅ report 完成")
    print()

    print("=== Pipeline 完成 ===")


def cmd_run(args):
    """执行每日运行 pipeline"""
    round_id = args.round
    date_str = args.date
    snapshot_label = args.snapshot_label or DEFAULT_SNAPSHOT_LABEL
    dry_run = args.dry_run
    generate_prompts_only = args.generate_prompts_only
    skip_browser = args.skip_browser
    seats_filter = args.seats.split(",") if args.seats else None
    verbose = args.verbose

    run_marker = _build_run_marker(round_id, date_str)
    model_accounts = _load_model_accounts()

    if seats_filter:
        model_accounts = [m for m in model_accounts
                          if m.get("seat_id") in seats_filter or m.get("model_account") in seats_filter]

    seats_total = len(model_accounts)

    print("ai_judge_daily_pool")
    print(f"round_id: {round_id}")
    print(f"date: {date_str}")
    print(f"snapshot_label: {snapshot_label}")
    print(f"seats_total: {seats_total}")
    print(f"dry_run: {dry_run}")
    if generate_prompts_only:
        print("mode: generate_prompts_only")
    if skip_browser:
        print("skip_browser: true")
    if seats_filter:
        print(f"seats_filter: {seats_filter}")
    print()

    if dry_run:
        print("DRY RUN — no files will be written")
        print("would generate:")
        print(f"  - data/pool/run_manifests/{round_id}.json")
        print(f"  - data/pool/prompts/{round_id}/*.md ({seats_total} files)")
        print(f"  - data/pool/model_outputs/raw/{round_id}/*.txt ({seats_total} placeholders)")
        print()
        print("dry_run: true")
        print("no files written")
        return

    # Step 1: 生成 run manifest
    seats_list = []
    for m in model_accounts:
        sid = m.get("seat_id", m.get("model_account", "unknown"))
        prompt_path = f"prompts/{round_id}/{sid}.md"
        raw_output_path = f"model_outputs/raw/{round_id}/{sid}.txt"
        seats_list.append({
            "model_account": m.get("model_account", sid),
            "seat_id": sid,
            "display_name": m.get("display_name", sid),
            "prompt_path": prompt_path,
            "raw_output_path": raw_output_path,
            "status": "prompt_generated",
        })

    manifest = {
        "version": "p11.0",
        "round_id": round_id,
        "date": date_str,
        "run_marker": run_marker,
        "created_at": _now_iso(),
        "mode": "generate_prompts_only" if generate_prompts_only else "full_run",
        "snapshot_label": snapshot_label,
        "odds_provider": args.odds_provider,
        "seats_total": seats_total,
        "seats": seats_list,
        "source_files": [
            f"matches/current.json",
            f"match_results/{date_str}.json",
            "leaderboard/current.json",
            f"daily_reports/{date_str}_run-5.json",
        ],
    }

    _write_json(f"run_manifests/{round_id}.json", manifest)
    manifest_path = DATA_DIR / "run_manifests" / f"{round_id}.json"
    print(f"  ✅ Generated: {manifest_path}")

    # Step 2: 预加载数据源（只加载一次，传给所有 prompt）
    matches_data = _read_json("matches/current.json", default={})
    match_results_data = _read_json(f"match_results/{date_str}.json", default={})
    odds_relpath, odds_data = _read_odds_snapshot(date_str, snapshot_label, provider=args.odds_provider)
    board_relpath, eligible_board = _load_or_generate_eligible_board(round_id, date_str, snapshot_label, args.odds_provider)
    leaderboard_data = _read_json("leaderboard/current.json", default={})
    prev_report_data = _read_json(f"daily_reports/{date_str}_run-5.json", default={})
    manifest["source_files"].insert(2, odds_relpath)
    manifest["source_files"].insert(3, board_relpath)
    _write_json(f"run_manifests/{round_id}.json", manifest)
    odds_summary = odds_data.get("summary", {}) if isinstance(odds_data, dict) else {}
    board_summary = eligible_board.get("summary", {}) if isinstance(eligible_board, dict) else {}
    print(
        "  ✅ Prompt odds snapshot: "
        f"{odds_relpath} "
        f"(provider={odds_data.get('provider') if isinstance(odds_data, dict) else 'unknown'}, "
        f"valid_odds_rows={odds_summary.get('valid_odds_rows', 0)})"
    )
    print(
        "  ✅ Provider-covered eligible board: "
        f"{board_relpath} "
        f"(rows={board_summary.get('eligible_board_rows', 0)}, "
        f"markets={','.join(board_summary.get('markets', []))})"
    )

    # Step 3: 生成每个模型的 prompt
    prompts_dir = DATA_DIR / "prompts" / round_id
    prompts_dir.mkdir(parents=True, exist_ok=True)

    for m in model_accounts:
        prompt = _build_prompt(
            seat=m,
            round_id=round_id,
            date_str=date_str,
            run_marker=run_marker,
            snapshot_label=snapshot_label,
            match_results=match_results_data,
            odds_snapshot=odds_data,
            eligible_board=eligible_board,
            leaderboard=leaderboard_data,
            previous_report=prev_report_data,
        )
        sid = m.get("seat_id", m.get("model_account", "unknown"))
        prompt_path = prompts_dir / f"{sid}.md"
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)
        if verbose:
            print(f"  ✅ Prompt: {prompt_path}")

    print(f"  ✅ Generated {seats_total} prompts in {prompts_dir}")
    print()

    if generate_prompts_only:
        raw_dir = DATA_DIR / "model_outputs" / "raw" / round_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        for m in model_accounts:
            sid = m.get("seat_id", m.get("model_account", "unknown"))
            placeholder_path = raw_dir / f"{sid}.txt"
            if not placeholder_path.exists():
                placeholder_path.write_text(
                    f"[WAITING FOR P15 PROVIDER-COVERED MODEL OUTPUT]\nseat_id: {sid}\nround_id: {round_id}\n",
                    encoding="utf-8"
                )
        readme_path = raw_dir / "README.md"
        if not readme_path.exists():
            readme_path.write_text(
                "# P15 Provider-Covered Rerun Raw Outputs\n\n"
                f"Round: `{round_id}`\n\n"
                "Paste each active web seat's real raw response into `{seat_id}.txt`.\n"
                "Do not fabricate, backfill old run outputs, or add board ids after the model answered.\n",
                encoding="utf-8",
            )
        print(f"  ✅ Created raw output dropbox: {raw_dir}")
        print("PROMPTS GENERATED — 请手动将 prompt 发送给各模型，并保存原始输出到:")
        print(f"  {raw_dir}")
        print()
        print("完成后运行:")
        print(f"  python3 ops/ai_judge_daily_pool.py ingest --round {round_id} --input-dir data/pool/model_outputs/raw/{round_id}")
        return

    # Step 4: 创建 raw output 目录（占位符）
    raw_dir = DATA_DIR / "model_outputs" / "raw" / round_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    for m in model_accounts:
        sid = m.get("seat_id", m.get("model_account", "unknown"))
        placeholder_path = raw_dir / f"{sid}.txt"
        if not placeholder_path.exists():
            placeholder_path.write_text(
                f"[WAITING FOR MODEL OUTPUT]\nseat_id: {sid}\nround_id: {round_id}\n",
                encoding="utf-8"
            )

    print(f"  ✅ Created raw output directory: {raw_dir}")
    print()

    # Step 5: 判断是否跳过浏览器
    if skip_browser:
        print("SKIP_BROWSER = true")
        print("状态: waiting_for_manual_ingest")
        print()
        print("请手动采集模型输出并保存到:")
        print(f"  {raw_dir}")
        print()
        print("完成后运行:")
        print(f"  python3 ops/ai_judge_daily_pool.py ingest --round {round_id} --input-dir data/pool/model_outputs/raw/{round_id}")
        return

    # Step 6: 如果浏览器可用，调用采集器（预留）
    print("⚠️  浏览器采集器未配置，自动转为 waiting_for_manual_ingest")
    print("状态: waiting_for_manual_ingest")
    print()
    print("请手动采集模型输出并保存到:")
    print(f"  {raw_dir}")
    print()
    print("完成后运行:")
    print(f"  python3 ops/ai_judge_daily_pool.py ingest --round {round_id} --input-dir data/pool/model_outputs/raw/{round_id}")
    return


def cmd_ingest(args):
    """Ingest 原始模型输出"""
    round_id = args.round
    input_dir = Path(args.input_dir).resolve()
    snapshot_label = args.snapshot_label or DEFAULT_SNAPSHOT_LABEL
    verbose = args.verbose

    print("ai_judge_daily_pool ingest")
    print(f"round_id: {round_id}")
    print(f"input_dir: {input_dir}")
    print()

    if not input_dir.exists():
        print(f"ERROR: input_dir not found: {input_dir}")
        sys.exit(1)

    # 从 input_dir 推断 date_str（尝试从 run_manifest 读取）
    manifest = _read_json(f"run_manifests/{round_id}.json", default=None)
    date_str = manifest.get("date", "2026-06-03") if manifest else "2026-06-03"

    model_accounts = _load_model_accounts()
    outputs = []
    outputs_found = 0

    for m in model_accounts:
        sid = m.get("seat_id", m.get("model_account", "unknown"))
        raw_path = input_dir / f"{sid}.txt"
        found = _is_real_model_output(raw_path)
        bytes_count = raw_path.stat().st_size if raw_path.exists() else 0
        outputs.append({
            "model_account": m.get("model_account", sid),
            "seat_id": sid,
            "raw_output_path": str(raw_path.relative_to(ROOT_DIR)),
            "found": found,
            "bytes": bytes_count,
        })
        if found:
            outputs_found += 1

    outputs_missing = len(model_accounts) - outputs_found

    ingested = {
        "version": "p11.0",
        "round_id": round_id,
        "ingested_at": _now_iso(),
        "input_dir": str(input_dir.relative_to(ROOT_DIR)),
        "outputs_total": len(model_accounts),
        "outputs_found": outputs_found,
        "outputs_missing": outputs_missing,
        "outputs": outputs,
    }

    ingested_dir = DATA_DIR / "model_outputs" / "ingested" / round_id
    ingested_dir.mkdir(parents=True, exist_ok=True)
    _write_json(f"model_outputs/ingested/{round_id}/index.json", ingested)

    ingested_path = ingested_dir / "index.json"
    print(f"  ✅ Ingested: {outputs_found}/{len(model_accounts)} outputs found")
    print(f"  ✅ Missing: {outputs_missing}")
    print(f"  ✅ Written to: {ingested_path}")
    print()

    # 如果 raw outputs 存在，执行 pipeline
    if outputs_found > 0:
        print("检测到原始输出，执行 pipeline...")
        print()
        _run_pipeline(round_id, date_str, snapshot_label, verbose)
    else:
        print("未检测到原始输出。")
        print("状态: waiting_for_manual_ingest")
        print()
        print("请保存模型原始输出到:")
        print(f"  {input_dir}")
        print("然后重新运行 ingest 命令。")


def cmd_status(args):
    """显示当前 round 状态"""
    round_id = args.round
    verbose = args.verbose

    print("ai_judge_daily_pool status")
    print(f"round_id: {round_id}")
    print()

    # 检查 manifest
    manifest = _read_json(f"run_manifests/{round_id}.json", default=None)
    manifest_exists = manifest is not None
    print(f"manifest: {'exists' if manifest_exists else 'missing'}")

    # 检查 prompts
    prompts_dir = DATA_DIR / "prompts" / round_id
    prompt_count = 0
    if prompts_dir.exists():
        prompt_count = len(list(prompts_dir.glob("*.md")))
    prompts_expected = len(_load_model_accounts())
    print(f"prompts: {prompt_count}/{prompts_expected}")

    # 检查 raw outputs
    raw_dir = DATA_DIR / "model_outputs" / "raw" / round_id
    raw_count = 0
    if raw_dir.exists():
        raw_count = len([p for p in raw_dir.glob("*.txt") if _is_real_model_output(p)])
    raw_expected = prompts_expected
    print(f"raw_outputs: {raw_count}/{raw_expected}")

    # 检查 ingested outputs
    ingested_json_path = DATA_DIR / "model_outputs" / "ingested" / round_id / "index.json"
    ingested_exists = ingested_json_path.exists()
    ingested_count = 0
    if ingested_exists:
        ingested_data = _read_json(f"model_outputs/ingested/{round_id}/index.json", default=None)
        if ingested_data:
            ingested_count = ingested_data.get("outputs_found", 0)
    print(f"ingested_outputs: {ingested_count}/{raw_expected}")

    # 判断状态
    state = "unknown"
    next_action = ""

    if not manifest_exists:
        state = "not_started"
        next_action = f"运行: python3 ops/ai_judge_daily_pool.py run --date <DATE> --round {round_id} --generate-prompts-only"
    elif raw_count == 0:
        state = "waiting_for_manual_ingest"
        next_action = f"将模型原始输出保存到 {raw_dir}，然后运行: python3 ops/ai_judge_daily_pool.py ingest --round {round_id} --input-dir data/pool/model_outputs/raw/{round_id}"
    elif ingested_count > 0:
        state = "ingested_ready_for_pipeline"
        next_action = "Pipeline 已执行或可执行"
    else:
        state = "ready_for_ingest"
        next_action = f"运行: python3 ops/ai_judge_daily_pool.py ingest --round {round_id} --input-dir data/pool/model_outputs/raw/{round_id}"

    print(f"state: {state}")
    print(f"next_action: {next_action}")

    if verbose and manifest:
        print()
        print("=== Manifest 摘要 ===")
        print(json.dumps(manifest, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="P11.0 AI Judge 每日自动运行入口")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # run 子命令
    run_parser = subparsers.add_parser("run", help="执行每日运行")
    run_parser.add_argument("--date", required=True, help="比赛日期 YYYY-MM-DD")
    run_parser.add_argument("--round", required=True, help="轮次 ID, e.g. run-6")
    run_parser.add_argument("--snapshot-label", default=DEFAULT_SNAPSHOT_LABEL, help="赔率快照标签")
    run_parser.add_argument("--odds-provider", default="auto",
                            help="Prompt 用赔率 provider: auto | manual_stub | the_odds_api")
    run_parser.add_argument("--seats", default=None, help="逗号分隔的 seat_id 列表")
    run_parser.add_argument("--dry-run", action="store_true", help="Dry run，不写文件")
    run_parser.add_argument("--generate-prompts-only", action="store_true", help="只生成 prompt")
    run_parser.add_argument("--skip-browser", action="store_true", default=True, help="跳过浏览器自动化")
    run_parser.add_argument("--no-skip-browser", action="store_false", dest="skip_browser", help="不跳过浏览器")
    run_parser.add_argument("--verbose", action="store_true", help="详细输出")

    # ingest 子命令
    ingest_parser = subparsers.add_parser("ingest", help="Ingest 原始模型输出")
    ingest_parser.add_argument("--round", required=True, help="轮次 ID")
    ingest_parser.add_argument("--input-dir", required=True, help="原始输出目录")
    ingest_parser.add_argument("--snapshot-label", default=DEFAULT_SNAPSHOT_LABEL, help="赔率快照标签")
    ingest_parser.add_argument("--verbose", action="store_true", help="详细输出")

    # status 子命令
    status_parser = subparsers.add_parser("status", help="显示运行状态")
    status_parser.add_argument("--round", required=True, help="轮次 ID")
    status_parser.add_argument("--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "run":
        cmd_run(args)
    elif args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
