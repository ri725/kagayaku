/**
 * Googleフォーム回答後に LINE へ「ご利用いただけます」を通知する Apps Script。
 *
 * 設定手順:
 * 1) 対象Googleフォームを開く → 右上︙ → スクリプトエディタ
 * 2) このコードを貼り付けて保存
 * 3) 左の「時計アイコン（トリガー）」→ 追加
 *    - 関数: onFormSubmit
 *    - イベント: フォーム送信時
 * 4) NOTIFY_URL / ITEM_TITLE_LINE_USER_ID を環境に合わせて変更
 * 5) （推奨）Railway に FORM_NOTIFY_SECRET を追加し、下の SECRET と同じ値にする
 */

var NOTIFY_URL = "https://web-production-fef3c.up.railway.app/form-complete";
var SECRET = ""; // Railway の FORM_NOTIFY_SECRET と同じ値。未設定なら空のままでも可
var ITEM_TITLE_LINE_USER_ID = "line_user_id"; // フォーム項目名

function onFormSubmit(e) {
  var userId = extractLineUserId_(e);
  if (!userId) {
    console.error("line_user_id が取得できませんでした");
    return;
  }

  var headers = {
    "Content-Type": "application/json",
  };
  if (SECRET) {
    headers["X-Form-Notify-Secret"] = SECRET;
  }

  var res = UrlFetchApp.fetch(NOTIFY_URL, {
    method: "post",
    contentType: "application/json",
    headers: headers,
    payload: JSON.stringify({ userId: userId }),
    muteHttpExceptions: true,
  });

  console.log(res.getResponseCode() + " " + res.getContentText());
}

function extractLineUserId_(e) {
  if (!e || !e.namedValues) {
    return "";
  }
  var values = e.namedValues[ITEM_TITLE_LINE_USER_ID];
  if (!values || !values.length) {
    // 項目名が少し違う場合のフォールバック
    var keys = Object.keys(e.namedValues);
    for (var i = 0; i < keys.length; i++) {
      if (String(keys[i]).toLowerCase().indexOf("line_user_id") >= 0) {
        values = e.namedValues[keys[i]];
        break;
      }
    }
  }
  if (!values || !values.length) {
    return "";
  }
  return String(values[0] || "").trim();
}
