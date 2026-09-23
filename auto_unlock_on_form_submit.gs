/**
 * Googleフォーム回答後に、回答者へ薬剤師リッチメニューを自動解放する。
 *
 * 前提:
 * - フォーム回答に line_user_id が含まれる（LIFFで U... を自動入力）
 *
 * スクリプトプロパティに以下を設定する:
 * - LINE_CHANNEL_ACCESS_TOKEN
 * - LINE_UNLOCK_RICHMENU_ID
 * - LINE_USER_ID_COLUMN (任意, default: line_user_id)
 *
 * トリガー:
 * - installable trigger: onFormSubmit
 *   - フォーム側GASなら: From form -> On form submit
 *   - スプレッドシート側GASなら: From spreadsheet -> On form submit
 */

const LINE_API_BASE = "https://api.line.me/v2/bot/user";
const USER_ID_ALIASES = ["line_user_id", "lineuserid", "line user id", "lineユーザーid", "lineユーザー id"];

function onFormSubmit(e) {
  if (!e) {
    console.log("No event payload.");
    return;
  }

  const props = PropertiesService.getScriptProperties();
  const accessToken = (props.getProperty("LINE_CHANNEL_ACCESS_TOKEN") || "").trim();
  const richMenuId = (props.getProperty("LINE_UNLOCK_RICHMENU_ID") || "").trim();
  const userIdColumn = (props.getProperty("LINE_USER_ID_COLUMN") || "line_user_id").trim();

  if (!accessToken || !richMenuId) {
    throw new Error("Script properties missing: LINE_CHANNEL_ACCESS_TOKEN / LINE_UNLOCK_RICHMENU_ID");
  }

  const userId = extractUserIdFromEvent(e, userIdColumn);
  if (!isValidUserId(userId)) {
    console.log("Invalid or missing userId: " + userId);
    return;
  }

  const result = linkRichMenu(userId, richMenuId, accessToken);
  console.log(JSON.stringify(result));
}

function extractUserIdFromEvent(e, userIdColumn) {
  // 1) スプレッドシートトリガー: e.namedValues
  if (e.namedValues && typeof e.namedValues === "object") {
    return extractUserIdFromNamedValues(e.namedValues, userIdColumn);
  }

  // 2) フォームトリガー: e.response
  if (e.response && typeof e.response.getItemResponses === "function") {
    return extractUserIdFromFormResponse(e.response, userIdColumn);
  }

  console.log("Unsupported event payload keys: " + Object.keys(e).join(", "));
  return "";
}

function extractUserIdFromNamedValues(namedValues, userIdColumn) {
  const columns = Object.keys(namedValues);
  const matchedKey = findMatchedKey(columns, userIdColumn);
  if (!matchedKey) {
    console.log("Column not found: " + userIdColumn + " / available: " + columns.join(", ") + " / fallback scan");
    return findUserIdInUnknownValues(namedValues);
  }

  const values = namedValues[matchedKey] || [];
  const first = values.length > 0 ? String(values[0]).trim() : "";
  if (isValidUserId(first)) return first;

  // 列が見つかっても値が空の場合は全体スキャン
  return findUserIdInUnknownValues(namedValues);
}

function extractUserIdFromFormResponse(response, userIdColumn) {
  const targetNormalized = normalizeKey(userIdColumn);
  const itemResponses = response.getItemResponses();

  for (let i = 0; i < itemResponses.length; i++) {
    const item = itemResponses[i].getItem();
    const title = String(item.getTitle() || "").trim();
    const normalizedTitle = normalizeKey(title);
    if (normalizedTitle === targetNormalized || USER_ID_ALIASES.indexOf(normalizedTitle) !== -1) {
      const value = String(itemResponses[i].getResponse() || "").trim();
      if (isValidUserId(value)) return value;
    }
  }

  // タイトル一致しない場合でも、回答全体からU...を探す
  for (let i = 0; i < itemResponses.length; i++) {
    const value = String(itemResponses[i].getResponse() || "").trim();
    if (isValidUserId(value)) return value;
  }

  console.log("Form item/value not found for userIdColumn: " + userIdColumn);
  return "";
}

function isValidUserId(userId) {
  return typeof userId === "string" && userId.startsWith("U") && userId.length > 10;
}

function normalizeKey(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[ _\-　]/g, "");
}

function findMatchedKey(columns, userIdColumn) {
  const target = normalizeKey(userIdColumn);
  for (let i = 0; i < columns.length; i++) {
    const normalized = normalizeKey(columns[i]);
    if (normalized === target || USER_ID_ALIASES.indexOf(normalized) !== -1) {
      return columns[i];
    }
  }
  return null;
}

function findUserIdInUnknownValues(namedValues) {
  const keys = Object.keys(namedValues || {});
  for (let i = 0; i < keys.length; i++) {
    const values = namedValues[keys[i]] || [];
    for (let j = 0; j < values.length; j++) {
      const value = String(values[j] || "").trim();
      if (isValidUserId(value)) {
        return value;
      }
    }
  }
  return "";
}

function linkRichMenu(userId, richMenuId, accessToken) {
  const url = LINE_API_BASE + "/" + encodeURIComponent(userId) + "/richmenu/" + encodeURIComponent(richMenuId);
  const response = UrlFetchApp.fetch(url, {
    method: "post",
    headers: {
      Authorization: "Bearer " + accessToken,
    },
    muteHttpExceptions: true,
  });

  const status = response.getResponseCode();
  const body = response.getContentText();

  if (status < 200 || status >= 300) {
    throw new Error("LINE API error: " + status + " " + body);
  }

  return {
    ok: true,
    userId: userId,
    status: status,
  };
}

// 設定確認用（手動実行）
function validateSetup() {
  const props = PropertiesService.getScriptProperties();
  const accessToken = (props.getProperty("LINE_CHANNEL_ACCESS_TOKEN") || "").trim();
  const richMenuId = (props.getProperty("LINE_UNLOCK_RICHMENU_ID") || "").trim();
  const userIdColumn = (props.getProperty("LINE_USER_ID_COLUMN") || "line_user_id").trim();

  console.log(
    JSON.stringify(
      {
        hasAccessToken: !!accessToken,
        accessTokenPrefix: accessToken ? accessToken.slice(0, 12) + "..." : "",
        richMenuId: richMenuId,
        userIdColumn: userIdColumn,
      },
      null,
      2
    )
  );
}
