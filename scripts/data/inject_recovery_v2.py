"""Extended recovery trajectories (v2): real ToolEnv-verified recovery from empty search and guessed-ID errors.

Adds two failure -> recovery patterns observed in Public Test (63.13) on top of TRAIN and synthetic trajectories:
  1. empty_to_list: a mangled / overly specific / date-in-query search returns empty -> model calls search with query=""
     to list all items, picks the right entity, and completes the remaining trajectory.
  2. guessed_id_to_list: a detail/write call with a guessed bogus code/ID fails (ok=false or done=false) -> model calls
     the app's list/holdings read tool first to obtain the real code/ID, then completes the task.

Failed attempts carry "train": false so train_agent_sft.py applies zero loss to the mistake and trains only on recovery.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "src"))
from lifemate.toolenv import new_env  # noqa: E402

LIST_ALL_SEARCH_TOOLS = {
    "contacts__search",
    "news__search",
    "maps__search_place",
    "podcast_radio__search",
    "library__search",
    "gift_mart__search_products",
    "bakery_shop__search_menu",
    "workshop_pass__search_events",
    "salon__search_salons",
    "clinic__search_doctors",
    "restaurant_booking__search_restaurants",
    "hotel_booking__search_hotels",
}

BOGUS_CODES = {"code": "ZXY", "symbol": "ZXY"}


def hits(result: object) -> list[str]:
    if isinstance(result, dict):
        for v in result.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                if "id" in v[0]:
                    return [x["id"] for x in v]
                if "code" in v[0]:
                    return [x["code"] for x in v]
    return []


def _is_failed(result: object) -> bool:
    if not isinstance(result, dict):
        return False
    return result.get("ok") is False or result.get("done") is False


def _call_name(msg: dict) -> str:
    return msg["tool_calls"][0]["function"]["name"]


def _call_args(msg: dict) -> dict:
    return msg["tool_calls"][0]["function"]["arguments"]


def _mangle_query(q: str, rng: random.Random) -> str:
    q = q.strip()
    if not q:
        return rng.choice(["thứ ba tuần sau", "chương trình đặc biệt", "sản phẩm mới nhất"])
    swaps = [("hài", "hai"), ("dời", "rời"), ("sếp", "xếp"), ("trà", "chà"), ("sữa", "xữa"), ("bánh", "mánh"), ("phở", "phỡ")]
    ql = q.lower()
    for a, b in swaps:
        if a in ql:
            return re.sub(a, b, q, count=1, flags=re.I)
    words = q.split()
    if len(words) >= 2:
        return f"{q} đặc biệt hôm nay"
    return f"{q} 2026"


def replay(data_root: Path, split: str, sample_id: str, calls: list[tuple[str, dict]]) -> list:
    env = new_env(data_root, split, sample_id)
    return [env.call(n.replace("__", ".", 1), a) for n, a in calls]


def build_empty_to_list(row: dict, data_root: Path, split: str, rng: random.Random) -> dict | None:
    msgs = row["messages"]
    idx = next(
        (
            i
            for i, m in enumerate(msgs)
            if m["role"] == "assistant"
            and m.get("tool_calls")
            and _call_name(m) in LIST_ALL_SEARCH_TOOLS
            and isinstance(_call_args(m).get("query"), str)
        ),
        None,
    )
    if idx is None:
        return None
    fn = _call_name(msgs[idx])
    orig_args = _call_args(msgs[idx])
    q = orig_args["query"]
    if not q and row.get("split_tag") != "synth_v2":
        return None

    target = set(hits(json.loads(msgs[idx + 1]["content"])))
    if not target:
        return None

    wrong_q = _mangle_query(q, rng)
    wrong_args = {**orig_args, "query": wrong_q}
    recover_args = {k: v for k, v in orig_args.items() if k != "query"}
    recover_args["query"] = ""

    before = [(_call_name(m), _call_args(m)) for m in msgs[:idx] if m["role"] == "assistant" and m.get("tool_calls")]
    r_wrong = replay(data_root, split, row["sample_id"], before + [(fn, wrong_args)])
    if hits(r_wrong[-1]):
        return None

    after_msgs = msgs[idx + 2:]
    after = [(_call_name(m), _call_args(m)) for m in after_msgs if m["role"] == "assistant" and m.get("tool_calls")]
    res = replay(data_root, split, row["sample_id"], before + [(fn, wrong_args), (fn, recover_args)] + after)
    if not target & set(hits(res[len(before) + 1])):
        return None
    orig_after = [json.loads(m["content"]) for m in after_msgs if m["role"] == "tool"]
    if res[len(before) + 2:] != orig_after:
        return None

    new_msgs = (
        msgs[:idx]
        + [
            {"role": "assistant", "content": "", "train": False, "tool_calls": [{"type": "function", "function": {"name": fn, "arguments": wrong_args}}]},
            {"role": "tool", "name": fn, "content": json.dumps(res[len(before)], ensure_ascii=False)},
            {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": fn, "arguments": recover_args}}]},
            {"role": "tool", "name": fn, "content": json.dumps(res[len(before) + 1], ensure_ascii=False)},
        ]
        + after_msgs
    )
    return {**row, "messages": new_msgs, "recovery_v2": {"kind": "empty_to_list", "tool": fn, "wrong": wrong_args, "recover": recover_args}}


def build_guessed_id_to_list(row: dict, data_root: Path, split: str) -> dict | None:
    msgs = row["messages"]
    # Pattern: assistant calls list_*/get_holdings/my_*/order_status, then immediately calls same-app read/write with id/code
    for i in range(len(msgs) - 3):
        m_list = msgs[i]
        m_next = msgs[i + 2]
        if m_list["role"] != "assistant" or not m_list.get("tool_calls"):
            continue
        if m_next["role"] != "assistant" or not m_next.get("tool_calls"):
            continue
        fn_list = _call_name(m_list)
        fn_next = _call_name(m_next)
        app_list = fn_list.split("__", 1)[0]
        app_next = fn_next.split("__", 1)[0]
        if app_list != app_next or app_list == "sys":
            continue
        if not any(k in fn_list for k in ("list_", "get_holdings", "order_status", "my_")):
            continue
        next_args = _call_args(m_next)
        id_key = next((k for k in ("code", "symbol", "pet_id", "goal_id", "order_id", "pass_id", "booking_id", "appointment_id") if isinstance(next_args.get(k), str)), None)
        if not id_key:
            continue

        bogus_val = BOGUS_CODES.get(id_key, "id_999")
        wrong_args = {**next_args, id_key: bogus_val}
        before = [(_call_name(m), _call_args(m)) for m in msgs[:i] if m["role"] == "assistant" and m.get("tool_calls")]
        res_wrong = replay(data_root, split, row["sample_id"], before + [(fn_next, wrong_args)])
        if not _is_failed(res_wrong[-1]):
            continue

        rest_msgs = msgs[i:]
        rest = [(_call_name(m), _call_args(m)) for m in rest_msgs if m["role"] == "assistant" and m.get("tool_calls")]
        res_full = replay(data_root, split, row["sample_id"], before + [(fn_next, wrong_args)] + rest)
        orig_rest = [json.loads(m["content"]) for m in rest_msgs if m["role"] == "tool"]
        if res_full[len(before) + 1:] != orig_rest:
            continue

        new_msgs = (
            msgs[:i]
            + [
                {"role": "assistant", "content": "", "train": False, "tool_calls": [{"type": "function", "function": {"name": fn_next, "arguments": wrong_args}}]},
                {"role": "tool", "name": fn_next, "content": json.dumps(res_full[len(before)], ensure_ascii=False)},
            ]
            + rest_msgs
        )
        return {**row, "messages": new_msgs, "recovery_v2": {"kind": "guessed_id_to_list", "wrong_tool": fn_next, "list_tool": fn_list}}
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=PROJECT / "data/train+public_test")
    ap.add_argument("--split", default="train")
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--max-empty", type=int, default=120)
    ap.add_argument("--max-id", type=int, default=80)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    rng = random.Random(a.seed)
    stats, out = Counter(), []
    empty_cnt = id_cnt = 0
    for line in a.input.open(encoding="utf-8"):
        row = json.loads(line)
        if empty_cnt < a.max_empty:
            r1 = build_empty_to_list(row, a.data_root, a.split, rng)
            if r1 is not None:
                out.append(r1)
                stats["empty_to_list"] += 1
                empty_cnt += 1
        if id_cnt < a.max_id:
            r2 = build_guessed_id_to_list(row, a.data_root, a.split)
            if r2 is not None:
                out.append(r2)
                stats["guessed_id_to_list"] += 1
                id_cnt += 1

    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps(dict(stats), ensure_ascii=False), f"total={len(out)}")


if __name__ == "__main__":
    main()
