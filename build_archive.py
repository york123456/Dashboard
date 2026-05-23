
import requests

import os
import sys

file_path = "./log/Email.list"
# 檢查檔案是否存在，如果沒有的話就創建
if not os.path.exists(file_path):
    open(file_path, 'w').close()
    print("檔案已建立！")
else:
    print("檔案已經存在。")


file_path = "./log/EmailOperate.log"

# 檢查檔案是否存在，如果沒有的話就創建
if not os.path.exists(file_path):
    open(file_path, 'w').close()
    print("檔案已建立！")
else:
    print("檔案已經存在。")



# 使用 os.environ.get 安全讀取環境變數
api_key = os.environ.get("emailwhitelist")

if not api_key:
    print("錯誤：找不到環境變數 emailwhitelist", file=sys.stderr)
    sys.exit(1)


# 在此處安全地使用您的 api_key
print("成功載入 emailwhitelist")

emailwhitelist= api_key



# 使用 os.environ.get 安全讀取環境變數
api_key = os.environ.get("API_TOKEN")

if not api_key:
    print("錯誤：找不到環境變數 API_TOKEN", file=sys.stderr)
    sys.exit(1)


# 在此處安全地使用您的 api_key
print("成功載入 API_TOKEN")


API_TOKEN = api_key


# 使用 os.environ.get 安全讀取環境變數
api_key = os.environ.get("SANDBOX_ID")

if not api_key:
    print("錯誤：找不到環境變數 SANDBOX_ID", file=sys.stderr)
    sys.exit(1)


# 在此處安全地使用您的 api_key
print("成功載入 SANDBOX_ID")



SANDBOX_ID = api_key


BASE = "https://mailtrap.io/api"

headers = {"Api-Token": API_TOKEN}

# 1) 先列出符合條件的信
#params = {"search": "test"}   # 可用 subject / to_email / to_name

#params = {"search": ""}   # 可用 subject / to_email / to_name

params={}

messages = requests.get(
    f"{BASE}/sandboxes/{SANDBOX_ID}/messages",
    headers=headers,
    params=params,
).json()

#print(messages)

import json


# 2) 取前幾封，進一步抓單封內容
for msg in messages[::]:
    detail = requests.get(
        f"{BASE}/sandboxes/{SANDBOX_ID}/messages/{msg['id']}",
        headers=headers,
    ).json()

    

    # 直接挑選需要的欄位組成新的字典，並轉為 JSON 字串
    result = {
        "id": detail["id"],
        "sent_at": detail["sent_at"],
        "subject": detail["subject"],
        "from_name": detail["from_name"],
        "from_email": detail["from_email"]
    }

    emailinfo = json.dumps(result, ensure_ascii=False)


    with open('./log/Email.list', 'r', encoding='utf-8') as f:
      result = f.readlines()
    Emaillist = " ".join(map(str, result))

    if detail["from_email"] in emailwhitelist and emailinfo not in Emaillist and "Confirm".casefold() not in emailinfo.casefold() and "訂閱".casefold() not in emailinfo.casefold() and "登録確定".casefold() not in emailinfo.casefold() :


      # 使用 'a' 模式開啟檔案，若檔案不存在則會自動建立
      with open("./log/Email.list", "a", encoding="utf-8") as file:
          file.write(emailinfo + "\n")  # 寫入文字並加上換行符號
 

      html_content = requests.get(f"{BASE.strip("api")}/{detail["html_source_path"]}")

      response = html_content

      
      with open(f'./storage/{detail["id"]}.html', 'wb') as file:
              file.write(response.content)
      print("檔案下載成功！")

      print('=================')


with open('./log/Email.list', 'r', encoding='utf-8') as f:
      result = f.readlines()


#print(result)



# 使用列表推導式：遍歷 result 中的每個字串，轉成字典後提取 "id"
id_list = [json.loads(line)["id"] for line in result if line.strip()]

#print(id_list)




#==========================


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_archive.py — 訂閱情報典藏室產生器（編輯室版型）
=========================================================
讀取 ./log/Email.list 與 ./storage/*.html，
產生一份策展式、智庫氣質的靜態 index.html。

用法：
    python build_archive.py

版型特色：
    報頭式 masthead、紙張紋理、雙軸側欄篩選（研究領域 × 情報來源）、
    搜尋與排序、右側抽屜式閱讀面板（iframe 沙箱載入原信）。
    每封信會依關鍵字自動歸入「研究領域」，規則可在下方自由增修。
"""

import os
import re
import json
import html as _html
from datetime import datetime, timezone
from html.parser import HTMLParser

# ──────────────────────────────────────────────────────────────
#  可調整設定
# ──────────────────────────────────────────────────────────────
SITE_NAME    = "情報典藏室"
KICKER       = "SUBSCRIBED INTELLIGENCE ARCHIVE"      # 報頭上方英文小標
RULE_LABEL   = "卷宗自動彙編"                          # 標題下分隔線文字
SUBTITLE     = "訂閱信件的策展式典藏 — 以智庫視角重新閱讀每一封來信"

LOG_FILE     = "./log/Email.list"
STORAGE_DIR  = "./storage"
OUTPUT_FILE  = "./index.html"

# True  : 將每封信完整內嵌進單一 index.html（離線可用、最穩定）
# False : 改以 iframe 連結 ./storage/{id}.html（檔案較小，建議搭配本機 HTTP server）
EMBED_HTML   = True

CHARS_PER_MIN = 350      # 估算閱讀時間（中文約值）
SNIPPET_LEN   = 120      # 摘要字數

# 置頂：填入要釘選在最上方的信件 id（字串或數字皆可）
PINNED_IDS = set()       # 例如 {"1001", 1003}

# 研究領域分類規則：由上而下比對主旨＋內文，命中第一個即採用。
# 中文關鍵字用「子字串」比對；英文／數字關鍵字用「全字」比對（避免 ai 誤中 Taiwan）。
TOPIC_RULES = [
    ("地緣戰略", ["台海", "臺海", "地緣", "嚇阻", "deterrence", "deterrent", "灰色地帶",
                 "gray zone", "印太", "indo-pacific", "南海", "軍演", "balikatan",
                 "解放軍", "威懾", "半導體", "semiconductor", "crink",
                 "strategic", "geopolit", "sea power", "land power"]),
    ("民主治理", ["民主", "democr", "善治", "治理失靈", "選舉", "election", "政黨",
                 "政治光譜", "spectrum", "威權", "autocra", "polity", "公民社會",
                 "制度", "institution", "韌性", "resilience", "governance"]),
    ("前沿科技", ["人工智慧", "alignment", "對齊", "演算法", "algorithm", "大模型",
                 "llm", "機器學習", "frontier", "量子", "quantum", "futurolog", "ai"]),
    ("城市與社會", ["城市", "urban", "高齡", "aging", "人口", "住房", "housing",
                   "組織", "organization", "社會學", "sociolog",
                   "維也納", "vienna", "新加坡", "singapore", "medell"]),
]
DEFAULT_TOPIC = "綜合情報"

# 指定來源直接對應主題（優先於關鍵字）。鍵可填 from_name 或 email 網域。
SOURCE_TOPIC = {
    # "Strategic Brief": "地緣戰略",
    # "polity.io": "民主治理",
}


# ──────────────────────────────────────────────────────────────
#  HTML 純文字擷取
# ──────────────────────────────────────────────────────────────
class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "head", "title", "noscript"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def html_to_text(markup: str) -> str:
    p = _TextExtractor()
    try:
        p.feed(markup)
    except Exception:
        pass
    return re.sub(r"\s+", " ", " ".join(p.parts)).strip()


# ──────────────────────────────────────────────────────────────
#  主題分類
# ──────────────────────────────────────────────────────────────
_CJK = re.compile(r"[\u4e00-\u9fff]")


def _match_topic(text: str):
    """在單一文字段落中找出第一個命中的主題，找不到回傳 None。"""
    if not text:
        return None
    hay = text.lower()
    for topic, kws in TOPIC_RULES:
        for kw in kws:
            if _CJK.search(kw):
                if kw in text:
                    return topic
            elif re.search(r"\b" + re.escape(kw.lower()) + r"\b", hay):
                return topic
    return None


def classify_topic(subject: str, body: str, source: str, domain: str) -> str:
    # 1) 來源覆寫優先
    if source and source in SOURCE_TOPIC:
        return SOURCE_TOPIC[source]
    if domain and domain in SOURCE_TOPIC:
        return SOURCE_TOPIC[domain]
    # 2) 主旨是最強訊號，先以主旨判定；3) 主旨無命中才退回內文
    return _match_topic(subject) or _match_topic(body) or DEFAULT_TOPIC


# ──────────────────────────────────────────────────────────────
#  時間
# ──────────────────────────────────────────────────────────────
def parse_sent_at(raw):
    """回傳 (epoch, 'YYYY.MM.DD', ISO 字串)。"""
    if not raw:
        return 0.0, "—", ""
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp(), f"{dt.year}.{dt.month:02d}.{dt.day:02d}", dt.isoformat()
    except Exception:
        return 0.0, str(raw), ""


# ──────────────────────────────────────────────────────────────
#  資料讀取
# ──────────────────────────────────────────────────────────────
def load_entries():
    if not os.path.exists(LOG_FILE):
        raise SystemExit(f"找不到 {LOG_FILE}，請先執行抓信程式。")

    pinned = {str(x) for x in PINNED_IDS}
    seen, entries = set(), []

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            eid = rec.get("id")
            if eid is None or eid in seen:
                continue
            seen.add(eid)

            epoch, date_label, date_iso = parse_sent_at(rec.get("sent_at"))

            path = os.path.join(STORAGE_DIR, f"{eid}.html")
            raw_html, text = "", ""
            if os.path.exists(path):
                with open(path, "rb") as hf:
                    raw_html = hf.read().decode("utf-8", errors="replace")
                text = html_to_text(raw_html)

            chars = len(text)
            subject = (rec.get("subject") or "（無主旨）").strip()
            from_name = (rec.get("from_name") or "").strip()
            from_email = (rec.get("from_email") or "").strip()
            domain = from_email.split("@")[-1] if "@" in from_email else ""
            source = from_name or domain or "未知來源"
            excerpt = (text[:SNIPPET_LEN] + " …") if chars > SNIPPET_LEN else text

            entry = {
                "id": eid,
                "subject": subject,
                "from_name": from_name,
                "from_email": from_email,
                "source": source,
                "topic": classify_topic(subject, text, source, domain),
                "date_iso": date_iso,
                "date_label": date_label,
                "date_sort": epoch,
                "excerpt": excerpt,
                "minutes": max(1, round(chars / CHARS_PER_MIN)) if chars else 1,
                "has_body": bool(raw_html),
                "rel_path": f"{STORAGE_DIR}/{eid}.html",
                "pinned": str(eid) in pinned,
                "html": raw_html if EMBED_HTML else "",
            }
            entries.append(entry)

    entries.sort(key=lambda e: e["date_sort"], reverse=True)
    return entries


def build_stats(entries):
    sources = {e["source"] for e in entries}
    topics = {e["topic"] for e in entries}
    dated = [e for e in entries if e["date_sort"]]
    if dated:
        lo = min(dated, key=lambda e: e["date_sort"])["date_label"]
        hi = max(dated, key=lambda e: e["date_sort"])["date_label"]
        rng = lo if lo == hi else f"{lo} – {hi}"
    else:
        rng = "—"
    return len(entries), len(sources), len(topics), rng


# ──────────────────────────────────────────────────────────────
#  頁面樣板（編輯室版型）
# ──────────────────────────────────────────────────────────────
TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__PAGE_TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300..600;1,6..72,400&family=Noto+Serif+TC:wght@400;500;700;900&family=Noto+Sans+TC:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
  :root {
    --paper:      #f4efe4;
    --paper-2:    #ece5d6;
    --card:       #fffdf8;
    --ink:        #20242c;
    --ink-soft:   #585c64;
    --ink-faint:  #8c8b82;
    --accent:     #8a2b2b;   /* 酒紅 */
    --accent-2:   #9c7a3c;   /* 黃銅 */
    --line:       rgba(32,36,44,.14);
    --line-soft:  rgba(32,36,44,.07);
    --shadow:     0 1px 2px rgba(32,36,44,.05), 0 14px 40px rgba(32,36,44,.07);
    --serif:      "Noto Serif TC", "Newsreader", Georgia, "Songti TC", serif;
    --display:    "Newsreader", "Noto Serif TC", Georgia, serif;
    --sans:       "Noto Sans TC", -apple-system, "Segoe UI", system-ui, sans-serif;
  }
  * { box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  body {
    margin: 0;
    background:
      radial-gradient(circle at 18% -10%, rgba(156,122,60,.10), transparent 55%),
      radial-gradient(circle at 100% 0%, rgba(138,43,43,.06), transparent 45%),
      var(--paper);
    color: var(--ink);
    font-family: var(--sans);
    font-weight: 400;
    -webkit-font-smoothing: antialiased;
    line-height: 1.6;
  }
  /* 細微紙張紋理 */
  body::before {
    content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
    opacity: .035; mix-blend-mode: multiply;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  }
  .wrap { position: relative; z-index: 1; max-width: 1180px; margin: 0 auto; padding: 0 28px; }

  /* ── 報頭 ─────────────────────────── */
  header.masthead { text-align: center; padding: 56px 0 30px; }
  .kicker {
    font-family: var(--sans); font-weight: 500; font-size: 11.5px;
    letter-spacing: .42em; text-transform: uppercase; color: var(--accent);
    margin: 0 0 18px;
  }
  .masthead h1 {
    font-family: var(--display); font-weight: 600; font-size: clamp(40px, 7vw, 78px);
    line-height: .98; letter-spacing: -.015em; margin: 0;
    color: var(--ink);
  }
  .masthead h1 .tc { font-family: var(--serif); font-weight: 900; }
  .rule {
    display: flex; align-items: center; gap: 16px;
    max-width: 560px; margin: 22px auto 16px; color: var(--ink-faint);
  }
  .rule::before, .rule::after { content: ""; flex: 1; height: 1px; background: var(--line); }
  .rule span { font-size: 11px; letter-spacing: .3em; text-transform: uppercase; }
  .masthead p.sub {
    font-family: var(--serif); font-style: italic; color: var(--ink-soft);
    font-size: clamp(15px, 2vw, 18px); max-width: 620px; margin: 0 auto;
  }

  /* ── 統計列 ───────────────────────── */
  .stats {
    display: flex; flex-wrap: wrap; justify-content: center; gap: 0;
    border-top: 1px solid var(--ink); border-bottom: 1px solid var(--ink);
    margin: 30px 0 0; padding: 14px 0;
  }
  .stat { padding: 4px 30px; text-align: center; border-right: 1px solid var(--line); }
  .stat:last-child { border-right: none; }
  .stat .num { font-family: var(--display); font-size: 26px; font-weight: 600; line-height: 1; }
  .stat .lab { font-size: 10.5px; letter-spacing: .22em; text-transform: uppercase; color: var(--ink-faint); margin-top: 6px; }

  /* ── 控制列 ───────────────────────── */
  .controls {
    display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
    margin: 26px 0 8px;
  }
  .search { position: relative; flex: 1; min-width: 220px; }
  .search input {
    width: 100%; padding: 12px 14px 12px 40px; font-family: var(--sans); font-size: 15px;
    background: var(--card); border: 1px solid var(--line); border-radius: 2px; color: var(--ink);
    transition: border-color .2s, box-shadow .2s;
  }
  .search input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(138,43,43,.10); }
  .search svg { position: absolute; left: 14px; top: 50%; transform: translateY(-50%); color: var(--ink-faint); }
  select {
    padding: 12px 14px; font-family: var(--sans); font-size: 14px; color: var(--ink);
    background: var(--card); border: 1px solid var(--line); border-radius: 2px; cursor: pointer;
  }
  select:focus { outline: none; border-color: var(--accent); }

  /* ── 主版面 ───────────────────────── */
  .layout { display: grid; grid-template-columns: 232px 1fr; gap: 44px; padding: 18px 0 80px; align-items: start; }
  aside { position: sticky; top: 22px; }
  aside h3 {
    font-family: var(--sans); font-size: 11px; letter-spacing: .26em; text-transform: uppercase;
    color: var(--ink-faint); margin: 0 0 12px; padding-bottom: 10px; border-bottom: 1px solid var(--line);
  }
  aside h3:not(:first-child) { margin-top: 30px; }
  .filter {
    display: flex; justify-content: space-between; align-items: baseline; gap: 8px;
    width: 100%; padding: 7px 10px; margin: 1px 0; border: none; border-radius: 2px;
    background: transparent; cursor: pointer; text-align: left; color: var(--ink-soft);
    font-family: var(--sans); font-size: 14px; transition: background .15s, color .15s;
  }
  .filter:hover { background: var(--paper-2); color: var(--ink); }
  .filter.active { background: var(--ink); color: var(--paper); }
  .filter .n { font-family: var(--display); font-size: 13px; opacity: .7; }

  /* ── 條目列表 ─────────────────────── */
  .feed { min-height: 50vh; }
  article.entry {
    position: relative; padding: 26px 0; border-bottom: 1px solid var(--line);
    cursor: pointer; opacity: 0; transform: translateY(10px);
    animation: rise .6s cubic-bezier(.2,.7,.3,1) forwards;
  }
  @keyframes rise { to { opacity: 1; transform: none; } }
  article.entry:first-child { padding-top: 4px; }
  .entry .topline { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
  .tag {
    font-size: 10.5px; letter-spacing: .16em; text-transform: uppercase; font-weight: 500;
    color: var(--accent); padding: 3px 9px; border: 1px solid rgba(138,43,43,.30); border-radius: 2px;
  }
  .pin { font-size: 10.5px; letter-spacing: .14em; color: var(--accent-2); font-weight: 700; }
  .entry h2 {
    font-family: var(--serif); font-weight: 700; font-size: clamp(20px, 2.6vw, 26px);
    line-height: 1.25; margin: 0 0 10px; color: var(--ink); letter-spacing: -.01em;
    transition: color .2s;
  }
  .entry:hover h2 { color: var(--accent); }
  .entry .meta {
    display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px;
    font-size: 13px; color: var(--ink-faint); margin-bottom: 12px;
  }
  .entry .meta .src { color: var(--ink-soft); font-weight: 500; }
  .entry .meta .dot { width: 3px; height: 3px; border-radius: 50%; background: var(--ink-faint); }
  .entry p.excerpt {
    font-family: var(--serif); font-size: 15.5px; line-height: 1.7; color: var(--ink-soft);
    margin: 0; max-width: 64ch;
  }
  .entry .more {
    display: inline-flex; align-items: center; gap: 6px; margin-top: 12px;
    font-size: 13px; letter-spacing: .04em; color: var(--accent); font-weight: 500;
  }
  .entry .more::after { content: "→"; transition: transform .2s; }
  .entry:hover .more::after { transform: translateX(4px); }
  .nobody { font-style: italic; color: var(--ink-faint); }
  .empty { text-align: center; padding: 80px 20px; color: var(--ink-faint); font-family: var(--serif); font-style: italic; }

  /* ── 閱讀面板 ─────────────────────── */
  .reader-bg {
    position: fixed; inset: 0; z-index: 40; background: rgba(20,18,14,.46);
    backdrop-filter: blur(3px); opacity: 0; visibility: hidden; transition: opacity .3s;
  }
  .reader-bg.open { opacity: 1; visibility: visible; }
  .reader {
    position: fixed; top: 0; right: 0; bottom: 0; z-index: 41; width: min(820px, 94vw);
    background: var(--card); box-shadow: -20px 0 60px rgba(0,0,0,.22);
    transform: translateX(102%); transition: transform .42s cubic-bezier(.22,.8,.28,1);
    display: flex; flex-direction: column;
  }
  .reader.open { transform: none; }
  .reader header { padding: 26px 34px 20px; border-bottom: 1px solid var(--line); }
  .reader .r-tag { font-size: 10.5px; letter-spacing: .18em; text-transform: uppercase; color: var(--accent); }
  .reader h2 { font-family: var(--serif); font-weight: 700; font-size: 24px; line-height: 1.3; margin: 10px 0 12px; }
  .reader .r-meta { font-size: 13px; color: var(--ink-faint); display: flex; flex-wrap: wrap; gap: 6px 14px; }
  .reader .body { flex: 1; overflow: hidden; background: #fff; }
  .reader iframe { width: 100%; height: 100%; border: none; background: #fff; }
  .reader .fallback { padding: 40px; font-family: var(--serif); color: var(--ink-soft); }
  .close {
    position: absolute; top: 22px; right: 26px; width: 38px; height: 38px; border-radius: 50%;
    border: 1px solid var(--line); background: var(--paper); cursor: pointer; color: var(--ink);
    font-size: 20px; line-height: 1; transition: background .2s, transform .2s;
  }
  .close:hover { background: var(--ink); color: var(--paper); transform: rotate(90deg); }

  footer { text-align: center; padding: 36px 0 60px; color: var(--ink-faint); font-size: 12px; letter-spacing: .1em; }
  footer .em { color: var(--accent-2); }

  @media (max-width: 760px) {
    .layout { grid-template-columns: 1fr; gap: 20px; }
    aside { position: static; }
    aside .deskwrap { display: flex; flex-wrap: wrap; gap: 6px; }
    aside h3 { width: 100%; }
    .filter { width: auto; }
    .stat { padding: 4px 18px; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    <p class="kicker">__KICKER__</p>
    <h1><span class="tc">__SITE_NAME__</span></h1>
    <div class="rule"><span>__RULE_LABEL__</span></div>
    <p class="sub">__SUBTITLE__</p>
    <div class="stats">
      <div class="stat"><div class="num">__STAT_COUNT__</div><div class="lab">典藏條目</div></div>
      <div class="stat"><div class="num">__STAT_SOURCES__</div><div class="lab">情報來源</div></div>
      <div class="stat"><div class="num">__STAT_TOPICS__</div><div class="lab">研究領域</div></div>
      <div class="stat"><div class="num" style="font-size:15px;letter-spacing:.02em">__STAT_RANGE__</div><div class="lab">收錄期間</div></div>
    </div>
  </header>

  <div class="controls">
    <div class="search">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
      <input id="q" type="search" placeholder="搜尋主旨、來源、內文摘要…" autocomplete="off">
    </div>
    <select id="sort">
      <option value="new">最新優先</option>
      <option value="old">最早優先</option>
      <option value="az">主旨 A→Z</option>
    </select>
  </div>

  <div class="layout">
    <aside>
      <h3>研究領域</h3>
      <div class="deskwrap" id="topicFilters"></div>
      <h3>情報來源</h3>
      <div class="deskwrap" id="sourceFilters"></div>
    </aside>
    <main class="feed" id="feed"></main>
  </div>

  <footer>
    本卷宗於 <span class="em">__BUILD_TIME__</span> 由 <span class="em">build_archive.py</span> 自動彙編 ·
    共 __STAT_COUNT__ 件典藏
  </footer>
</div>

<!-- 閱讀面板 -->
<div class="reader-bg" id="readerBg"></div>
<div class="reader" id="reader" role="dialog" aria-modal="true">
  <button class="close" id="closeReader" aria-label="關閉">×</button>
  <header>
    <span class="r-tag" id="rTag"></span>
    <h2 id="rTitle"></h2>
    <div class="r-meta" id="rMeta"></div>
  </header>
  <div class="body" id="rBody"></div>
</div>

<script>
const DATA = __DATA_JSON__;
const EMBED = __EMBED_FLAG__;
let state = { q: "", topic: null, source: null, sort: "new" };

const $ = (s) => document.querySelector(s);
const feed = $("#feed");

// 建立側邊篩選
function buildFilters() {
  const topics = {}, sources = {};
  DATA.forEach(e => {
    topics[e.topic] = (topics[e.topic]||0)+1;
    sources[e.source] = (sources[e.source]||0)+1;
  });
  renderFilterGroup("#topicFilters", topics, "topic");
  renderFilterGroup("#sourceFilters", sources, "source");
}
function renderFilterGroup(sel, counts, key) {
  const box = $(sel);
  const all = document.createElement("button");
  all.className = "filter active"; all.dataset.key = key; all.dataset.val = "";
  all.innerHTML = `<span>全部</span><span class="n">${Object.values(counts).reduce((a,b)=>a+b,0)}</span>`;
  box.appendChild(all);
  Object.entries(counts).sort((a,b)=>b[1]-a[1]).forEach(([name, n]) => {
    const b = document.createElement("button");
    b.className = "filter"; b.dataset.key = key; b.dataset.val = name;
    b.innerHTML = `<span>${escapeHtml(name)}</span><span class="n">${n}</span>`;
    box.appendChild(b);
  });
  box.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".filter"); if (!btn) return;
    state[key] = btn.dataset.val || null;
    box.querySelectorAll(".filter").forEach(x => x.classList.remove("active"));
    btn.classList.add("active");
    render();
  });
}

function escapeHtml(s) {
  return (s||"").replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;" }[c]));
}

function filtered() {
  let out = DATA.filter(e => {
    if (state.topic && e.topic !== state.topic) return false;
    if (state.source && e.source !== state.source) return false;
    if (state.q) {
      const hay = (e.subject + " " + e.source + " " + e.from_email + " " + e.excerpt).toLowerCase();
      if (!hay.includes(state.q.toLowerCase())) return false;
    }
    return true;
  });
  const s = state.sort;
  out.sort((a,b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    if (s === "new") return b.date_sort - a.date_sort;
    if (s === "old") return a.date_sort - b.date_sort;
    if (s === "az")  return a.subject.localeCompare(b.subject, "zh-Hant");
    return 0;
  });
  return out;
}

function render() {
  const items = filtered();
  feed.innerHTML = "";
  if (!items.length) {
    feed.innerHTML = `<div class="empty">沒有符合條件的卷宗。<br>試著放寬搜尋或切換篩選。</div>`;
    return;
  }
  items.forEach((e, i) => {
    const art = document.createElement("article");
    art.className = "entry";
    art.style.animationDelay = Math.min(i * 0.04, 0.4) + "s";
    art.innerHTML = `
      <div class="topline">
        <span class="tag">${escapeHtml(e.topic)}</span>
        ${e.pinned ? '<span class="pin">★ 置頂</span>' : ''}
      </div>
      <h2>${escapeHtml(e.subject)}</h2>
      <div class="meta">
        <span class="src">${escapeHtml(e.source)}</span>
        <span class="dot"></span><span>${escapeHtml(e.date_label)}</span>
        <span class="dot"></span><span>約 ${e.minutes} 分鐘</span>
        ${e.has_body ? '' : '<span class="dot"></span><span class="nobody">僅存目</span>'}
      </div>
      <p class="excerpt">${escapeHtml(e.excerpt || "（此封信件沒有可預覽的內文）")}</p>
      ${e.has_body ? '<span class="more">閱讀全文</span>' : ''}`;
    art.addEventListener("click", () => openReader(e));
    feed.appendChild(art);
  });
}

// 閱讀面板
const readerBg = $("#readerBg"), reader = $("#reader");
function openReader(e) {
  $("#rTag").textContent = e.topic;
  $("#rTitle").textContent = e.subject;
  $("#rMeta").innerHTML =
    `<span>${escapeHtml(e.source)}</span>` +
    (e.from_email ? `<span>${escapeHtml(e.from_email)}</span>` : "") +
    `<span>${escapeHtml(e.date_label)}</span>`;
  const body = $("#rBody");
  if (!e.has_body) {
    body.innerHTML = `<div class="fallback">這封信件目前只有索引資料，沒有保存完整內文。</div>`;
  } else if (EMBED) {
    const f = document.createElement("iframe");
    f.setAttribute("sandbox", "allow-popups allow-popups-to-escape-sandbox");
    f.srcdoc = e.html;
    body.innerHTML = ""; body.appendChild(f);
  } else {
    const f = document.createElement("iframe");
    f.setAttribute("sandbox", "allow-popups allow-popups-to-escape-sandbox");
    f.src = e.rel_path;
    body.innerHTML = ""; body.appendChild(f);
  }
  readerBg.classList.add("open");
  reader.classList.add("open");
  document.body.style.overflow = "hidden";
}
function closeReader() {
  readerBg.classList.remove("open");
  reader.classList.remove("open");
  document.body.style.overflow = "";
  setTimeout(() => { $("#rBody").innerHTML = ""; }, 420);
}
readerBg.addEventListener("click", closeReader);
$("#closeReader").addEventListener("click", closeReader);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeReader(); });

$("#q").addEventListener("input", (e) => { state.q = e.target.value; render(); });
$("#sort").addEventListener("change", (e) => { state.sort = e.target.value; render(); });

buildFilters();
render();
</script>
</body>
</html>
"""


def main():
    entries = load_entries()
    count, n_sources, n_topics, rng = build_stats(entries)

    data_json = json.dumps(entries, ensure_ascii=False)
    data_json = data_json.replace("</", "<\\/")   # 防止信件內含 </script> 提前結束腳本

    page = (TEMPLATE
            .replace("__PAGE_TITLE__", _html.escape(f"{SITE_NAME} · {SUBTITLE}"))
            .replace("__KICKER__", _html.escape(KICKER))
            .replace("__SITE_NAME__", _html.escape(SITE_NAME))
            .replace("__RULE_LABEL__", _html.escape(RULE_LABEL))
            .replace("__SUBTITLE__", _html.escape(SUBTITLE))
            .replace("__STAT_SOURCES__", str(n_sources))
            .replace("__STAT_TOPICS__", str(n_topics))
            .replace("__STAT_RANGE__", _html.escape(rng))
            .replace("__BUILD_TIME__", datetime.now().strftime("%Y.%m.%d %H:%M"))
            .replace("__EMBED_FLAG__", "true" if EMBED_HTML else "false")
            .replace("__STAT_COUNT__", str(count))   # 出現在統計列與頁尾，皆替換
            .replace("__DATA_JSON__", data_json))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(page)

    print(f"✓ 已產生 {OUTPUT_FILE}")
    print(f"  收錄 {count} 封 · 來源 {n_sources} · 領域 {n_topics} · 期間 {rng}")
    dist = {}
    for e in entries:
        dist[e["topic"]] = dist.get(e["topic"], 0) + 1
    print("  領域分布：" + "、".join(f"{k} {v}" for k, v in sorted(dist.items(), key=lambda x: -x[1])))
    if not EMBED_HTML:
        print("  （EMBED_HTML=False：建議於專案目錄執行  python -m http.server  後開啟）")


if __name__ == "__main__":
    main()





