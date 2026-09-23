#!/usr/bin/env python3
"""
LINE Webhook（薬剤師メニュー応答 + フォーム回答後通知）。

機能:
- 「求人情報」→ ダミー求人3件
- 「使い方」→ サポートの流れ（相談〜入職後フォロー）
- 「お問い合わせ」→ クイックリプライ（担当者連絡先 / その他）
- 「その他」→ 担当者連絡待ちメッセージ
- POST /form-complete → フォーム回答後に「ご利用いただけます」をpush

必要な環境変数:
- LINE_CHANNEL_ACCESS_TOKEN
- LINE_CHANNEL_SECRET
- FORM_NOTIFY_SECRET（任意。 /form-complete 保護用）
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
from urllib.error import HTTPError


REPLY_ENDPOINT = "https://api.line.me/v2/bot/message/reply"
PUSH_ENDPOINT = "https://api.line.me/v2/bot/message/push"
OFFICIAL_URL = "https://kagayakuyakuzaisi.co.jp"
FORM_LIFF_URL = os.getenv("FORM_LIFF_URL", "https://liff.line.me/2010024465-3JecMAQb")

FORM_COMPLETE_MESSAGE = (
    "ご回答ありがとうございます。\n"
    "これよりリッチメニューをご利用いただけます。\n\n"
    "求人情報・使い方・お問い合わせからお進みください。"
)


def build_company_inquiry_menu_message() -> dict:
    return {
        "type": "text",
        "text": "お問い合わせ内容をお選びください。",
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "フリーランス薬剤師の募集",
                        "text": "フリーランス薬剤師の募集",
                    },
                },
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "転職の仲介",
                        "text": "転職の仲介",
                    },
                },
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "その他のお問い合わせ",
                        "text": "その他のお問い合わせ",
                    },
                },
            ]
        },
    }


def build_pharmacist_inquiry_menu_message() -> dict:
    return {
        "type": "text",
        "text": "ご希望の内容をお選びください。",
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
                        "label": "その他のお問い合わせ",
                        "text": "その他のお問い合わせ",
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


def build_recruit_inquiry_message() -> dict:
    return {
        "type": "text",
        "text": (
            "フリーランス薬剤師の募集について承りました。\n"
            "希望エリア・時給・稼働開始時期をこのままご返信ください。"
        ),
    }


def build_mediation_inquiry_message() -> dict:
    return {
        "type": "text",
        "text": (
            "転職の仲介について承りました。\n"
            "募集背景・採用時期・雇用条件をこのままご返信ください。"
        ),
    }


def build_form_guide_message() -> dict:
    return {
        "type": "text",
        "text": (
            "薬剤師向けサービスをご希望の方は、初回登録フォームのご回答をお願いします。\n"
            f"{FORM_LIFF_URL}"
        ),
    }


def build_follow_welcome_message() -> dict:
    return {
        "type": "text",
        "text": (
            "友だち追加ありがとうございます。\n\n"
            "薬剤師向けサービスをご希望の方は、初回登録フォームのご回答をお願いします。\n"
            f"{FORM_LIFF_URL}"
        ),
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


def push_message(access_token: str, user_id: str, messages: list[dict]) -> None:
    payload = {
        "to": user_id,
        "messages": messages,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = request.Request(PUSH_ENDPOINT, method="POST", data=data)
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json")

    with request.urlopen(req, timeout=20):
        return


def build_form_complete_message() -> dict:
    return {"type": "text", "text": FORM_COMPLETE_MESSAGE}


def is_valid_user_id(user_id: str) -> bool:
    return isinstance(user_id, str) and user_id.startswith("U") and len(user_id) > 10


def resolve_messages(user_text: str) -> list[dict] | None:
    if user_text in {"企業お問い合わせメニュー", "企業問い合わせしたい"}:
        return [build_company_inquiry_menu_message()]
    if user_text in {"薬剤師お問い合わせメニュー", "お問い合わせ"}:
        return [build_pharmacist_inquiry_menu_message()]
    if user_text in {"フリーランス薬剤師の募集"}:
        return [build_recruit_inquiry_message()]
    if user_text in {"転職の仲介"}:
        return [build_mediation_inquiry_message()]
    if user_text in {"その他", "その他のお問い合わせ"}:
        return [build_inquiry_wait_message()]
    if user_text in {"求人情報", "求人情報を見たい"}:
        return [build_dummy_jobs_message()]
    if user_text in {"担当者連絡先", "担当者に相談したい"}:
        return [build_staff_contacts_message()]
    if user_text in {"使い方", "使い方を知りたい"}:
        return [build_usage_guide_message()]
    if user_text in {"薬剤師メニューを利用したい", "薬剤師サービスを利用したい"}:
        return [build_form_guide_message()]
    return None


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/form-complete":
            self._handle_form_complete()
            return
        if self.path != "/webhook":
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return
        self._handle_webhook()

    def _handle_form_complete(self) -> None:
        access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
        if not access_token:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "missing token"})
            return

        expected_secret = os.getenv("FORM_NOTIFY_SECRET", "").strip()
        if expected_secret:
            got = self.headers.get("X-Form-Notify-Secret", "").strip()
            if not hmac.compare_digest(got, expected_secret):
                self._send_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "forbidden"})
                return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid json"})
            return

        user_id = str(payload.get("userId") or payload.get("line_user_id") or "").strip()
        if not is_valid_user_id(user_id):
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid userId"})
            return

        try:
            push_message(access_token, user_id, [build_form_complete_message()])
        except HTTPError as e:
            detail = e.read().decode("utf-8", errors="ignore")
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {"ok": False, "error": f"line push failed: {e.code}", "detail": detail},
            )
            return
        except Exception as e:  # noqa: BLE001
            self._send_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(e)})
            return

        self._send_json(HTTPStatus.OK, {"ok": True})

    def _handle_webhook(self) -> None:
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
            if event.get("type") == "follow":
                reply_token = event.get("replyToken")
                if not reply_token:
                    continue
                try:
                    reply_message(access_token, reply_token, [build_follow_welcome_message()])
                except Exception:
                    pass
                continue

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
