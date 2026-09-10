#!/usr/bin/env python3
"""
薬剤師向けリッチメニュー（薬剤師.jpg 前提 + タブ切替）を作成するスクリプト。

構成:
- 上段タブ: 薬剤師 / 企業様
- 中段3ボタン: 求人情報 / 使い方 / お問い合わせ
- 下段ロゴ帯: 非タップ

使い方:
python create_pharmacist_richmenu.py \
  --image-path "薬剤師.jpg" \
  --jobs-message "求人情報" \
  --usage-message "使い方" \
  --inquiry-message "お問い合わせ" \
  --pharmacist-alias "pharmacist_tab" \
  --company-alias "company_tab" \
  --set-default
"""

from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request

try:
    from PIL import Image
except ImportError:
    vendor = os.path.join(os.path.dirname(__file__), ".vendor")
    if vendor not in sys.path:
        sys.path.insert(0, vendor)
    from PIL import Image


API_BASE = "https://api.line.me/v2/bot/richmenu"
DATA_API_BASE = "https://api-data.line.me/v2/bot/richmenu"
ALIAS_API_BASE = "https://api.line.me/v2/bot/richmenu/alias"
TARGET_SIZE = (2500, 1686)


def request_json(
    url: str,
    method: str,
    access_token: str,
    payload: dict | None = None,
) -> dict:
    data = None
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json")

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    try:
        with urllib.request.urlopen(req, data=data, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {e.code} {url}: {body}") from e


def prepare_image_bytes(image_path: str) -> tuple[bytes, str]:
    content_type, _ = mimetypes.guess_type(image_path)
    if content_type not in {"image/jpeg", "image/png"}:
        raise ValueError("画像は JPEG か PNG を指定してください。")

    with Image.open(image_path) as img:
        rgb = img.convert("RGB")
        if rgb.size != TARGET_SIZE:
            rgb = rgb.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=92, optimize=True)
        return buf.getvalue(), "image/jpeg"


def upload_richmenu_image(richmenu_id: str, image_path: str, access_token: str) -> None:
    image_data, content_type = prepare_image_bytes(image_path)
    url = f"{DATA_API_BASE}/{richmenu_id}/content"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", content_type)

    try:
        with urllib.request.urlopen(req, data=image_data, timeout=30):
            return
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"画像アップロード失敗 HTTP {e.code}: {body}") from e


def set_default_richmenu(richmenu_id: str, access_token: str) -> None:
    url = f"https://api.line.me/v2/bot/user/all/richmenu/{richmenu_id}"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Length", "0")

    try:
        with urllib.request.urlopen(req, data=b"", timeout=30):
            return
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"デフォルト設定失敗 HTTP {e.code}: {body}") from e


def create_richmenu_alias(alias_id: str, richmenu_id: str, access_token: str) -> None:
    payload = {
        "richMenuAliasId": alias_id,
        "richMenuId": richmenu_id,
    }
    try:
        request_json(ALIAS_API_BASE, "POST", access_token, payload)
    except RuntimeError as e:
        # alias 既存時は更新APIへ（LINEは 409 ではなく 400 conflict を返すことがある）
        msg = str(e)
        if "HTTP 409" not in msg and "conflict richmenu alias id" not in msg:
            raise
        request_json(
            f"{ALIAS_API_BASE}/{alias_id}",
            "POST",
            access_token,
            {"richMenuId": richmenu_id},
        )


def build_pharmacist_payload(
    jobs_message: str,
    usage_message: str,
    inquiry_message: str,
    pharmacist_alias: str,
    company_alias: str | None = None,
) -> dict:
    company_action = (
        {"type": "richmenuswitch", "richMenuAliasId": company_alias, "data": "tab=company"}
        if company_alias
        else {"type": "message", "text": "企業様向けメニューは準備中です"}
    )

    # 薬剤師.jpg（2500x1686換算）
    # 上段タブ / 中段3ボタン / 下段ロゴ帯は非タップ
    return {
        "size": {"width": 2500, "height": 1686},
        "selected": False,
        "name": "pharmacist_tab_menu",
        "chatBarText": "メニュー",
        "areas": [
            {
                "bounds": {"x": 0, "y": 0, "width": 1250, "height": 200},
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": pharmacist_alias,
                    "data": "tab=pharmacist",
                },
            },
            {
                "bounds": {"x": 1250, "y": 0, "width": 1250, "height": 200},
                "action": company_action,
            },
            {
                "bounds": {"x": 0, "y": 200, "width": 833, "height": 1080},
                "action": {"type": "message", "text": jobs_message},
            },
            {
                "bounds": {"x": 833, "y": 200, "width": 834, "height": 1080},
                "action": {"type": "message", "text": usage_message},
            },
            {
                "bounds": {"x": 1667, "y": 200, "width": 833, "height": 1080},
                "action": {"type": "message", "text": inquiry_message},
            },
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="薬剤師向けリッチメニュー作成")
    parser.add_argument("--image-path", default="薬剤師.jpg", help="リッチメニュー画像パス")
    parser.add_argument(
        "--jobs-message",
        default="求人情報",
        help="求人情報ボタンで送信するメッセージ",
    )
    parser.add_argument(
        "--usage-message",
        default="使い方",
        help="使い方ボタンで送信するメッセージ",
    )
    parser.add_argument(
        "--inquiry-message",
        default="お問い合わせ",
        help="お問い合わせボタンで送信するメッセージ",
    )
    parser.add_argument(
        "--pharmacist-alias",
        default="pharmacist_tab",
        help="薬剤師タブのrichMenuAliasId (default: pharmacist_tab)",
    )
    parser.add_argument(
        "--company-alias",
        help="企業様タブのrichMenuAliasId（未指定時は準備中メッセージ）",
    )
    parser.add_argument(
        "--set-default",
        action="store_true",
        help="作成したメニューをデフォルトに設定する",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()

    if not access_token:
        print("環境変数 LINE_CHANNEL_ACCESS_TOKEN を設定してください。", file=sys.stderr)
        return 1

    if not os.path.exists(args.image_path):
        print(f"画像が見つかりません: {args.image_path}", file=sys.stderr)
        return 1

    payload = build_pharmacist_payload(
        jobs_message=args.jobs_message,
        usage_message=args.usage_message,
        inquiry_message=args.inquiry_message,
        pharmacist_alias=args.pharmacist_alias,
        company_alias=args.company_alias,
    )

    try:
        create_result = request_json(API_BASE, "POST", access_token, payload)
        richmenu_id = create_result.get("richMenuId")
        if not richmenu_id:
            print(f"richMenuId が取得できません: {create_result}", file=sys.stderr)
            return 1

        upload_richmenu_image(richmenu_id, args.image_path, access_token)
        create_richmenu_alias(args.pharmacist_alias, richmenu_id, access_token)

        if args.set_default:
            set_default_richmenu(richmenu_id, access_token)

        print(
            json.dumps(
                {
                    "richMenuId": richmenu_id,
                    "defaultSet": args.set_default,
                    "pharmacistAliasId": args.pharmacist_alias,
                    "companyAliasId": args.company_alias,
                },
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"失敗: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
