#!/usr/bin/env python3
"""
企業様向けリッチメニュー（企業.jpg 前提 + タブ切替）を作成するスクリプト。

構成:
- 上段タブ: 薬剤師 / 企業様
- 中段2ボタン: 公式ホームページ / お問い合わせ
- 下段ロゴ帯: 非タップ

使い方:
python create_company_richmenu.py \
  --image-path "企業.jpg" \
  --homepage-url "https://kagayakuyakuzaisi.co.jp" \
  --inquiry-message "お問い合わせ" \
  --company-alias "company_tab" \
  --pharmacist-alias "pharmacist_tab"
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
    payload = {"richMenuAliasId": alias_id, "richMenuId": richmenu_id}
    try:
        request_json(ALIAS_API_BASE, "POST", access_token, payload)
    except RuntimeError as e:
        msg = str(e)
        if "HTTP 409" not in msg and "conflict richmenu alias id" not in msg:
            raise
        request_json(
            f"{ALIAS_API_BASE}/{alias_id}",
            "POST",
            access_token,
            {"richMenuId": richmenu_id},
        )


def build_company_payload(
    homepage_url: str,
    inquiry_message: str,
    company_alias: str,
    pharmacist_alias: str | None,
) -> dict:
    pharmacist_tab_action = (
        {"type": "richmenuswitch", "richMenuAliasId": pharmacist_alias, "data": "tab=pharmacist"}
        if pharmacist_alias
        else {"type": "message", "text": "薬剤師向けメニューは準備中です"}
    )

    # 企業.jpg（2500x1686換算）
    # 上段タブ / 中段2ボタン / 下段ロゴ帯は非タップ
    return {
        "size": {"width": 2500, "height": 1686},
        "selected": False,
        "name": "company_tab_menu",
        "chatBarText": "メニュー",
        "areas": [
            {
                "bounds": {"x": 0, "y": 0, "width": 1250, "height": 200},
                "action": pharmacist_tab_action,
            },
            {
                "bounds": {"x": 1250, "y": 0, "width": 1250, "height": 200},
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": company_alias,
                    "data": "tab=company",
                },
            },
            {
                "bounds": {"x": 160, "y": 240, "width": 1040, "height": 940},
                "action": {"type": "uri", "uri": homepage_url},
            },
            {
                "bounds": {"x": 1300, "y": 240, "width": 1040, "height": 940},
                "action": {"type": "message", "text": inquiry_message},
            },
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="企業様向けリッチメニュー作成")
    parser.add_argument("--image-path", default="企業.jpg", help="リッチメニュー画像パス")
    parser.add_argument(
        "--homepage-url",
        default="https://kagayakuyakuzaisi.co.jp",
        help="公式ホームページURL",
    )
    parser.add_argument(
        "--inquiry-message",
        default="お問い合わせ",
        help="お問い合わせボタンで送信するメッセージ",
    )
    parser.add_argument(
        "--company-alias",
        default="company_tab",
        help="企業様タブのrichMenuAliasId (default: company_tab)",
    )
    parser.add_argument(
        "--pharmacist-alias",
        default="pharmacist_tab",
        help="薬剤師タブのrichMenuAliasId (default: pharmacist_tab)",
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

    payload = build_company_payload(
        homepage_url=args.homepage_url,
        inquiry_message=args.inquiry_message,
        company_alias=args.company_alias,
        pharmacist_alias=args.pharmacist_alias,
    )

    try:
        create_result = request_json(API_BASE, "POST", access_token, payload)
        richmenu_id = create_result.get("richMenuId")
        if not richmenu_id:
            print(f"richMenuId が取得できません: {create_result}", file=sys.stderr)
            return 1

        upload_richmenu_image(richmenu_id, args.image_path, access_token)
        create_richmenu_alias(args.company_alias, richmenu_id, access_token)

        if args.set_default:
            set_default_richmenu(richmenu_id, access_token)

        print(
            json.dumps(
                {
                    "richMenuId": richmenu_id,
                    "defaultSet": args.set_default,
                    "companyAliasId": args.company_alias,
                    "pharmacistAliasId": args.pharmacist_alias,
                    "homepageUrl": args.homepage_url,
                    "inquiryMessage": args.inquiry_message,
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
