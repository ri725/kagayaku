#!/usr/bin/env python3
"""
LINE Webhook（薬剤師メニュー応答）。

機能:
- 「求人情報」→ ダミー求人3件
- 「使い方」→ サポートの流れ（相談〜入職後フォロー）
- 「お問い合わせ」→ クイックリプライ（担当者連絡先 / その他）
- 「その他」→ 担当者連絡待ちメッセージ

必要な環境変数:
- LINE_CHANNEL_ACCESS_TOKEN
- LINE_CHANNEL_SECRET
- PORT (任意, default: 8080)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import request


REPLY_ENDPOINT = "https://api.line.me/v2/bot/message/reply"
OFFICIAL_URL = "https://kagayakuyakuzaisi.co.jp"


def build_inquiry_menu_message() -> dict:
    return {
        "type": "text",
        "text": "お問い合わせ内容をお選びください。",
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "担当者連絡先",
                        "text": "担当者連絡先",
                    },
                },
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "その他",
                        "text": "その他",
                    },
                },
            ]
        },
    }


def build_inquiry_wait_message() -> dict:
    return {
        "type": "text",
        "text": "担当者から連絡がきます。しばらくお待ちください。",
    }


def build_dummy_jobs_message() -> dict:
    return {
        "type": "flex",
        "altText": "募集中の求人（ダミー）3件",
        "contents": {
            "type": "carousel",
            "contents": [
                _job_bubble(
                    area="福岡市中央区",
                    wage="時給 3,500円",
                    note="日勤メイン / 処方箋枚数安定",
                ),
                _job_bubble(
                    area="福岡市博多区",
                    wage="時給 3,800円",
                    note="週3日〜可 / 高時給案件",
                ),
                _job_bubble(
                    area="福岡市南区",
                    wage="時給 4,000円",
                    note="管理薬剤師候補 / 定着支援あり",
                ),
            ],
        },
    }


def _job_bubble(area: str, wage: str, note: str) -> dict:
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": "求人情報（ダミー）",
                    "size": "xs",
                    "color": "#888888",
                },
                {
                    "type": "text",
                    "text": area,
                    "weight": "bold",
                    "size": "lg",
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": wage,
                    "size": "md",
                    "color": "#1F4E79",
                    "weight": "bold",
                },
                {
                    "type": "text",
                    "text": note,
                    "size": "sm",
                    "color": "#555555",
                    "wrap": True,
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#1F4E79",
                    "action": {
                        "type": "uri",
                        "label": "もっと詳しく",
                        "uri": OFFICIAL_URL,
                    },
                }
            ],
        },
    }


def build_staff_contacts_message() -> dict:
    return {
        "type": "text",
        "text": (
            "担当者連絡先です。\n\n"
            "【カガヤク薬剤師】\n"
            "TEL: 070-8570-4556（受付 9:00-18:00）\n"
            "Mail: jinji@kagayakuyakuzaisi.co.jp\n"
            f"HP: {OFFICIAL_URL}\n\n"
            "ご用件をこのままご返信いただいても大丈夫です。"
        ),
    }


def build_usage_guide_message() -> dict:
    return {
        "type": "text",
        "text": (
            "サポートの流れ\n"
            "ご相談から転職決定まで、すべて無料でサポートします。\n\n"
            "01 無料キャリア相談\n"
            "まずはお気軽にご相談ください。現在の状況・希望・悩みをヒアリングします。"
            "オンライン・対面どちらも対応可能です。\n\n"
            "02 求人提案・マッチング\n"
            "ご希望に合った求人を厳選してご提案。非公開求人を含む、"
            "九州エリアの豊富な案件からマッチングします。\n\n"
            "03 応募・面接サポート\n"
            "履歴書・職務経歴書の添削から面接対策までしっかりサポート。"
            "薬剤師業界の面接傾向も熟知しています。\n\n"
            "04 条件交渉・内定\n"
            "給与・勤務条件の交渉も代行します。"
            "あなたの代わりに、最善の条件を引き出します。\n\n"
            "05 入職後フォロー\n"
            "転職後も継続してフォロー。"
            "「転職してよかった」と感じていただけるまで伴走します。\n\n"
            "ご相談はメニューの「お問い合わせ」からどうぞ。"
        ),
    }


def verify_signature(body: bytes, signature: str, channel_secret: str) -> bool:
    mac = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def reply_message(access_token: str, reply_token: str, messages: list[dict]) -> None:
    payload = {
        "replyToken": reply_token,
        "messages": messages,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = request.Request(REPLY_ENDPOINT, method="POST", data=data)
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json")

    with request.urlopen(req, timeout=20):
        return


def resolve_messages(user_text: str) -> list[dict] | None:
    if user_text in {"お問い合わせ", "企業お問い合わせメニュー", "問い合わせしたい"}:
        return [build_inquiry_menu_message()]
    if user_text in {"その他"}:
        return [build_inquiry_wait_message()]
    if user_text in {"求人情報", "求人情報を見たい"}:
        return [build_dummy_jobs_message()]
    if user_text in {"担当者連絡先", "担当者に相談したい"}:
        return [build_staff_contacts_message()]
    if user_text in {"使い方", "使い方を知りたい"}:
        return [build_usage_guide_message()]
    return None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/webhook":
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return

        access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
        channel_secret = os.getenv("LINE_CHANNEL_SECRET", "").strip()
        if not access_token or not channel_secret:
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.end_headers()
            self.wfile.write(b"Missing LINE env vars")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        signature = self.headers.get("x-line-signature", "")

        if not verify_signature(body, signature, channel_secret):
            self.send_response(HTTPStatus.FORBIDDEN)
            self.end_headers()
            self.wfile.write(b"Invalid signature")
            return

        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.end_headers()
            return

        events = payload.get("events", [])
        for event in events:
            if event.get("type") != "message":
                continue
            message = event.get("message", {})
            if message.get("type") != "text":
                continue

            user_text = str(message.get("text", "")).strip()
            reply_token = event.get("replyToken")
            if not reply_token:
                continue

            messages = resolve_messages(user_text)
            if not messages:
                continue

            try:
                reply_message(access_token, reply_token, messages)
            except Exception:
                # LINE側の再送を避けるため 200 応答は返す
                pass

        self.send_response(HTTPStatus.OK)
        self.end_headers()


def main() -> None:
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Webhook server started on :{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
