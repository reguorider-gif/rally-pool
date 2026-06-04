#!/usr/bin/env python3
from __future__ import annotations
"""
P13.0 Provider Config Checker — 检查赔率供应商 API key 配置状态。

用法:
  python3 ops/check_provider_config.py
  python3 ops/check_provider_config.py --provider the_odds_api
  python3 ops/check_provider_config.py --json

输出:
  data/pool/provider_status/latest.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── 路径 ───────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "pool"
OUT_DIR  = DATA_DIR / "provider_status"
OUT_PATH = OUT_DIR / "latest.json"

# ── Provider 配置 ─────────────────────────────────────────────────────────────
PROVIDERS = {
    "the_odds_api": {
        "env_var":    "THE_ODDS_API_KEY",
        "api_base":   "https://api.the-odds-api.com/v4",
        "key_pattern": "sk_live_",
        "doc_url":    "https://the-odds-api.com/",
    },
}


def mask_key(key: str) -> str | None:
    """对 API key 做完全脱敏处理，不保留真实前后缀。"""
    if not key:
        return None
    return "***REDACTED***"


def check_provider(provider_name: str) -> dict:
    """检查单个 provider 的配置状态。"""
    cfg = PROVIDERS.get(provider_name)
    if not cfg:
        return {
            "provider":     provider_name,
            "configured":   False,
            "status":       "unknown_provider",
            "message":      f"Unknown provider: {provider_name}",
            "secret_masked": None,
        }

    env_var = cfg["env_var"]
    raw_key = os.environ.get(env_var, "")

    result = {
        "provider":      provider_name,
        "env_var":       env_var,
        "configured":    bool(raw_key),
        "status":        "configured" if raw_key else "not_configured",
        "secret_masked": mask_key(raw_key) if raw_key else None,
        "api_base":      cfg.get("api_base"),
        "doc_url":       cfg.get("doc_url"),
    }

    if not raw_key:
        result["message"] = (
            f"{env_var} is not set. "
            f"Please run: export {env_var}=<your_key>"
        )
        result["next_action"] = f"export {env_var}=<your_key>"
    else:
        result["message"] = f"{env_var} is configured (masked)."
        result["next_action"] = "ready_for_smoke_test"

    return result


def run_check(provider_name: str | None = None, to_json: bool = False):
    """主检查逻辑。"""
    targets = [provider_name] if provider_name else list(PROVIDERS.keys())
    providers = []
    blockers  = []
    warnings  = []

    for pname in targets:
        info = check_provider(pname)
        providers.append(info)
        if not info["configured"]:
            warnings.append({
                "code":    "provider_not_configured",
                "provider": pname,
                "message":  f"{info['env_var']} is not set.",
            })

    overall = "ready"
    if blockers:
        overall = "blocked"
    elif warnings:
        overall = "ready_with_warnings"

    result = {
        "version":       "p13.0",
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "overall":        overall,
        "providers":      providers,
        "blockers":       blockers,
        "warnings":       warnings,
    }

    # 终端输出
    print("=== Provider Config Check ===")
    for p in providers:
        status_icon = "✅" if p["configured"] else "⚠️"
        print(f"  {status_icon} {p['provider']}: {p['status']}")
        if p["secret_masked"]:
            print(f"      key: {p['secret_masked']}")
        print(f"      {p['message']}")
        if p.get("next_action"):
            print(f"      next: {p['next_action']}")

    print(f"\n  Overall: {overall}")
    if warnings:
        print(f"  Warnings: {len(warnings)}")
    if blockers:
        print(f"  Blockers: {len(blockers)}")

    # 写 JSON
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n  [write] {OUT_PATH.relative_to(BASE_DIR)}")

    if to_json:
        print("\n" + json.dumps(result, ensure_ascii=False, indent=2))

    return result


def main():
    parser = argparse.ArgumentParser(description="P13.0 Provider Config Checker")
    parser.add_argument("--provider", default=None, help="Provider name (default: all)")
    parser.add_argument("--json",      action="store_true", help="Also print JSON to stdout")
    args = parser.parse_args()

    run_check(provider_name=args.provider, to_json=args.json)


if __name__ == "__main__":
    main()
