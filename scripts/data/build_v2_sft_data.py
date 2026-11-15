"""Build improved SFT datasets (v2_eval excluding Val-200, and v2_full with all 1,545 TRAIN tasks) into an output folder.

Combines:
  - TRAIN trajectories (E1P, gold + pseudo/asr + noisy variants)
  - Original recovery rows x2 (inject_recovery.py)
  - Extended v2 recovery rows (inject_recovery_v2.py: empty_to_list + guessed_id_to_list)
  - Curated synth_v2 trajectories (cart->checkout vs cart-only, holdings/list before code, empty-query date lookup) + synth_v2 recovery

Every trajectory is replayed and verified through the official ToolEnv.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
DATA_SCRIPTS = PROJECT / "scripts/data"


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _ask_rate(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    asks = sum(
        1
        for r in rows
        if any(
            c.get("function", {}).get("name") == "sys__ask_missing_info"
            for m in r["messages"]
            if m.get("role") == "assistant"
            for c in (m.get("tool_calls") or [])
        )
    )
    return asks / len(rows)


def build_one(
    name: str,
    include_val: bool,
    data_root: Path,
    asr_cache: Path | None,
    synth_root: Path,
    synth_rows: list[dict],
    synth_rec_rows: list[dict],
    out_dir: Path,
    work_dir: Path,
) -> None:
    py = sys.executable
    prep_dir = work_dir / f"prep_{name}"
    if prep_dir.exists():
        shutil.rmtree(prep_dir)

    variants = "gold,asr,noisy" if (asr_cache and asr_cache.exists()) else "gold,pseudo,noisy"
    cmd = [
        py, str(DATA_SCRIPTS / "prepare_agent_sft.py"),
        "--data-root", str(data_root),
        "--orchestration", "E1P",
        "--variants", variants,
        "--output-dir", str(prep_dir),
    ]
    if include_val:
        cmd.append("--include-validation")
    if asr_cache and asr_cache.exists():
        cmd += ["--asr-cache", str(asr_cache)]
    _run(cmd)

    # For recovery generation on TRAIN, run on merged train+dev when include_val=True, else train.jsonl
    base_train = _read_jsonl(prep_dir / "train.jsonl")
    base_dev = _read_jsonl(prep_dir / "dev.jsonl")
    train_pool_path = work_dir / f"pool_{name}.jsonl"
    pool_rows = (base_train + base_dev) if include_val else base_train
    train_pool_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in pool_rows), encoding="utf-8")

    rec1_path = work_dir / f"rec1_{name}.jsonl"
    _run([
        py, str(DATA_SCRIPTS / "inject_recovery.py"),
        "--data-root", str(data_root),
        "--input", str(train_pool_path),
        "--output", str(rec1_path),
    ])
    rec1_rows = _read_jsonl(rec1_path)

    rec2_path = work_dir / f"rec2_{name}.jsonl"
    _run([
        py, str(DATA_SCRIPTS / "inject_recovery_v2.py"),
        "--data-root", str(data_root),
        "--split", "train",
        "--input", str(train_pool_path),
        "--output", str(rec2_path),
        "--max-empty", "140",
        "--max-id", "80",
    ])
    rec2_rows = _read_jsonl(rec2_path)

    combined_train = pool_rows + (rec1_rows * 2) + rec2_rows + synth_rows + synth_rec_rows
    target_dir = out_dir / name
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)
    (target_dir / "train.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in combined_train),
        encoding="utf-8",
    )
    if not include_val and base_dev:
        (target_dir / "dev.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in base_dev),
            encoding="utf-8",
        )
    summary = {
        "split": name,
        "include_validation": include_val,
        "variants": variants,
        "base_rows": len(pool_rows),
        "rec1_x2_rows": len(rec1_rows) * 2,
        "rec2_rows": len(rec2_rows),
        "synth_v2_rows": len(synth_rows),
        "synth_v2_rec_rows": len(synth_rec_rows),
        "total_train_rows": len(combined_train),
        "ask_missing_info_rate": round(_ask_rate(combined_train), 4),
    }
    (target_dir / "manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"BUILT {name}:", json.dumps(summary, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--asr-cache", type=Path, default=None)
    ap.add_argument("--work-dir", type=Path, default=PROJECT / "outputs/v2_build_tmp")
    a = ap.parse_args()

    if a.work_dir.exists():
        shutil.rmtree(a.work_dir)
    a.work_dir.mkdir(parents=True)

    # 1. Build synth_v2 split (isolated to synth_v2.py tasks)
    synth_out = a.work_dir / "synth_out"
    _run([
        sys.executable, str(DATA_SCRIPTS / "build_synth_split.py"),
        "--data-root", str(a.data_root),
        "--out", str(synth_out),
        "--tasks-glob", "synth_v2.py",
        "--seed", "7",
    ])
    synth_sft_dir = a.work_dir / "synth_sft"
    _run([
        sys.executable, str(DATA_SCRIPTS / "prepare_agent_sft.py"),
        "--data-root", str(synth_out),
        "--split", "synth",
        "--include-validation",
        "--orchestration", "E1P",
        "--variants", "gold,pseudo,noisy",
        "--output-dir", str(synth_sft_dir),
    ])
    synth_rows = _read_jsonl(synth_sft_dir / "train.jsonl") + _read_jsonl(synth_sft_dir / "dev.jsonl")
    synth_all_path = a.work_dir / "synth_all.jsonl"
    synth_all_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in synth_rows), encoding="utf-8")

    synth_rec_path = a.work_dir / "synth_rec.jsonl"
    _run([
        sys.executable, str(DATA_SCRIPTS / "inject_recovery_v2.py"),
        "--data-root", str(synth_out),
        "--split", "synth",
        "--input", str(synth_all_path),
        "--output", str(synth_rec_path),
        "--max-empty", "60",
        "--max-id", "40",
    ])
    synth_rec_rows = _read_jsonl(synth_rec_path)

    # 2. Build v2_eval (excludes 200 Val IDs) and v2_full (all 1,545 TRAIN tasks)
    build_one("v2_eval", False, a.data_root, a.asr_cache, synth_out, synth_rows, synth_rec_rows, a.out_dir, a.work_dir)
    build_one("v2_full", True, a.data_root, a.asr_cache, synth_out, synth_rows, synth_rec_rows, a.out_dir, a.work_dir)


if __name__ == "__main__":
    main()
