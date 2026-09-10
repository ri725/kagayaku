#!/usr/bin/env python3
"""
LINE Messaging APIでユーザーにリッチメニューを紐付けるスクリプト。

使い方:
  1) 1ユーザー解放
     python unlock_richmenu.py --user-id Uxxxxxxxx

  2) 複数ユーザー解放（CSV）
     python unlock_richmenu.py --csv-path responses.csv --column-name line_user_id

必要な環境変数:
  LINE_CHANNEL_ACCESS_TOKEN
  LINE_UNLOCK_RICHMENU_ID
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.request


API_BASE = "https://api.line.me/v2/bot/user"


def validate_user_id(user_id: str) -> bool:
    return isinstance(user_id, str) and user_id.startswith("U") and len(user_id) > 10


def link_richmenu(user_id: str, richmenu_id: str, access_token: str) -> tuple[bool, str]:
    url = f"{API_BASE}/{user_id}/richmenu/{richmenu_id}"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Authorization", f"Bearer {access_token}")

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            code = response.getcode()
            if 200 <= code < 300:
                return True, f"OK ({code})"
            return False, f"Unexpected status: {code}"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        return False, f"HTTPError {e.code}: {body}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def read_user_ids_from_csv(csv_path: str, column_name: str) -> list[str]:
    user_ids: list[str] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or column_name not in reader.fieldnames:
            raise ValueError(
                f"列 '{column_name}' が見つかりません。利用可能列: {reader.fieldnames}"
            )

        for row in reader:
            raw = (row.get(column_name) or "").strip()
            if raw:
                user_ids.append(raw)

    # 重複除去（順序維持）
    seen = set()
    unique_ids = []
    for uid in user_ids:
        if uid not in seen:
            seen.add(uid)
            unique_ids.append(uid)
    return unique_ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LINEリッチメニュー解放スクリプト")
    parser.add_argument("--user-id", help="単体解放するユーザーID (U...)")
    parser.add_argument("--csv-path", help="Googleフォーム回答CSVパス")
    parser.add_argument(
        "--column-name",
        default="line_user_id",
        help="CSV内のユーザーID列名 (default: line_user_id)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    richmenu_id = os.getenv("LINE_UNLOCK_RICHMENU_ID", "").strip()

    if not access_token or not richmenu_id:
        print(
            "環境変数不足: LINE_CHANNEL_ACCESS_TOKEN と LINE_UNLOCK_RICHMENU_ID を設定してください。",
            file=sys.stderr,
        )
        return 1

    targets: list[str] = []

    if args.user_id:
        targets = [args.user_id.strip()]
    elif args.csv_path:
        try:
            targets = read_user_ids_from_csv(args.csv_path, args.column_name)
        except Exception as e:  # noqa: BLE001
            print(f"CSV読み込み失敗: {e}", file=sys.stderr)
            return 1
    else:
        print("--user-id か --csv-path のどちらかを指定してください。", file=sys.stderr)
        return 1

    if not targets:
        print("対象ユーザーIDが0件です。")
        return 0

    success = 0
    failed = 0

    for user_id in targets:
        if not validate_user_id(user_id):
            failed += 1
            print(f"[NG] {user_id} : userId形式が不正です")
            continue

        ok, message = link_richmenu(user_id, richmenu_id, access_token)
        if ok:
            success += 1
            print(f"[OK] {user_id} : {message}")
        else:
            failed += 1
            print(f"[NG] {user_id} : {message}")

    print(json.dumps({"success": success, "failed": failed}, ensure_ascii=False))
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
