#!/usr/bin/env python3
"""
私を構成する9つのゲーム
Usage: python my9games.py
       → http://localhost:8080 を開く
"""
import json
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8080

# ---- IGDB 認証情報 ----
# https://dev.twitch.tv/console でアプリを作成して取得（無料）
IGDB_CLIENT_ID = ""
IGDB_CLIENT_SECRET = ""


# ---- Steam API ----

def steam_search(term):
    if not term.strip():
        return []
    url = (
        "https://store.steampowered.com/api/storesearch/?"
        + urllib.parse.urlencode({"term": term, "l": "japanese", "cc": "JP"})
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        return [
            {
                "id": g["id"],
                "name": g["name"],
                "thumb": g.get("tiny_image", ""),
                "cover": f"/api/cover?id={g['id']}",
            }
            for g in data.get("items", [])[:12]
        ]
    except Exception as e:
        return {"error": str(e)}


def fetch_cover(appid):
    """Steam CDN からカバー画像を取得。portrait → header の順で試す"""
    if not str(appid).isdigit():
        return None, "text/plain"
    for suffix in ["library_600x900.jpg", "header.jpg"]:
        url = f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/{suffix}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                ct = r.headers.get("Content-Type", "image/jpeg")
                return r.read(), ct
        except Exception:
            continue
    return None, "text/plain"


# ---- IGDB API ----

_igdb_token = {"token": None, "expires": 0.0}


def get_igdb_token():
    global _igdb_token
    if _igdb_token["token"] and time.time() < _igdb_token["expires"] - 60:
        return _igdb_token["token"]
    data = urllib.parse.urlencode({
        "client_id": IGDB_CLIENT_ID,
        "client_secret": IGDB_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }).encode()
    req = urllib.request.Request(
        "https://id.twitch.tv/oauth2/token",
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        result = json.loads(r.read())
    _igdb_token = {
        "token": result["access_token"],
        "expires": time.time() + result["expires_in"],
    }
    return _igdb_token["token"]


def igdb_search(term):
    if not term.strip():
        return []
    if not IGDB_CLIENT_ID or not IGDB_CLIENT_SECRET:
        return {"error": "IGDB_CLIENT_ID / IGDB_CLIENT_SECRET が未設定です。my9games.py の先頭に記入してください。"}
    token = get_igdb_token()
    escaped = term.replace('"', '\\"')
    body = f'fields name,cover.url; search "{escaped}"; limit 12;'.encode()
    req = urllib.request.Request(
        "https://api.igdb.com/v4/games",
        data=body,
        headers={
            "Client-ID": IGDB_CLIENT_ID,
            "Authorization": f"Bearer {token}",
            "Content-Type": "text/plain",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        games = json.loads(r.read())
    results = []
    for g in games:
        thumb = ""
        cover = ""
        if g.get("cover", {}).get("url"):
            raw = "https:" + g["cover"]["url"]
            thumb = raw.replace("/t_thumb/", "/t_cover_big/")
            cover = "/api/igdb_cover?url=" + urllib.parse.quote(thumb, safe="")
        results.append({"id": g["id"], "name": g["name"], "thumb": thumb, "cover": cover})
    return results


def fetch_igdb_image(url):
    if not url.startswith("https://images.igdb.com/"):
        return None, "text/plain"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            ct = r.headers.get("Content-Type", "image/jpeg")
            return r.read(), ct
    except Exception:
        return None, "text/plain"


# ---- HTTP Server ----

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path in ("/", "/index.html"):
            body = HTML.encode("utf-8")
            self._send(200, "text/html; charset=utf-8", body)

        elif parsed.path == "/api/search":
            q = params.get("q", [""])[0]
            result = steam_search(q)
            self._send(200, "application/json", json.dumps(result).encode())

        elif parsed.path == "/api/cover":
            appid = params.get("id", [""])[0]
            data, ct = fetch_cover(appid)
            if data:
                self._send(200, ct, data)
            else:
                self._send(404, "text/plain", b"Not found")

        elif parsed.path == "/api/igdb_search":
            q = params.get("q", [""])[0]
            try:
                result = igdb_search(q)
            except Exception as e:
                result = {"error": str(e)}
            self._send(200, "application/json", json.dumps(result).encode())

        elif parsed.path == "/api/igdb_cover":
            url = params.get("url", [""])[0]
            data, ct = fetch_igdb_image(url)
            if data:
                self._send(200, ct, data)
            else:
                self._send(404, "text/plain", b"Not found")

        else:
            self._send(404, "text/plain", b"Not found")

    def _send(self, code, ct, body):
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


# ---- HTML ----

HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <title>私を構成する9つのゲーム</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Helvetica Neue', Arial, 'Hiragino Kaku Gothic ProN', sans-serif;
      background: #0f172a;
      color: #e2e8f0;
      min-height: 100vh;
      padding: 24px 16px;
    }
    h1 {
      text-align: center;
      font-size: 1.1rem;
      color: #94a3b8;
      margin-bottom: 20px;
      letter-spacing: 0.08em;
    }

    .settings {
      display: flex;
      gap: 10px;
      align-items: center;
      background: #1e293b;
      padding: 12px 16px;
      border-radius: 8px;
      margin: 0 auto 20px;
      max-width: 920px;
    }
    .settings label { font-size: 0.78rem; color: #94a3b8; }
    .settings input {
      background: #334155;
      border: 1px solid #475569;
      border-radius: 5px;
      color: #f1f5f9;
      padding: 5px 10px;
      font-size: 0.82rem;
      outline: none;
      width: 160px;
    }
    .settings input:focus { border-color: #818cf8; }

    button {
      cursor: pointer;
      font-family: inherit;
      font-size: 0.78rem;
      border-radius: 5px;
      border: 1px solid #475569;
      background: #334155;
      color: #cbd5e1;
      padding: 5px 10px;
      transition: background 0.12s;
    }
    button:hover { background: #475569; }

    #capture {
      max-width: 920px;
      margin: 0 auto 20px;
      background: #0f172a;
      padding: 20px;
      border-radius: 12px;
    }
    #captureHeader {
      text-align: center;
      font-size: 0.95rem;
      color: #94a3b8;
      margin-bottom: 14px;
    }
    #captureHeader strong { color: #f1f5f9; }

    .grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
    }

    .slot {
      background: #1e293b;
      border-radius: 6px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    .slot-cover {
      position: relative;
      width: 100%;
      padding-top: 150%;
      background: #334155;
      cursor: pointer;
      overflow: hidden;
    }
    .slot-cover img {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
      transition: opacity 0.15s;
    }
    .slot-cover:hover img { opacity: 0.8; }
    .slot-cover-hint {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.7rem;
      color: #f1f5f9;
      background: rgba(0,0,0,0.45);
      opacity: 0;
      transition: opacity 0.15s;
    }
    .slot-cover:hover .slot-cover-hint { opacity: 1; }

    .slot-empty {
      position: absolute;
      inset: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      color: #64748b;
      gap: 4px;
      transition: background 0.12s;
    }
    .slot-empty:hover { background: #334155; }
    .slot-empty .plus { font-size: 1.8rem; line-height: 1; }
    .slot-empty .label { font-size: 0.65rem; }

    .slot-body {
      padding: 6px 8px;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .slot-title {
      font-size: 0.72rem;
      font-weight: bold;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      color: #f1f5f9;
    }
    textarea.slot-comment {
      width: 100%;
      background: transparent;
      border: none;
      border-bottom: 1px solid #334155;
      color: #94a3b8;
      font-family: inherit;
      font-size: 0.68rem;
      resize: none;
      outline: none;
      height: 34px;
      line-height: 1.45;
    }
    textarea.slot-comment::placeholder { color: #475569; }
    textarea.slot-comment.spoiler {
      color: transparent;
      text-shadow: 0 0 7px #94a3b8;
    }

    .slot-actions {
      display: flex;
      gap: 4px;
      padding: 4px 8px 7px;
    }
    .slot-actions button { font-size: 0.62rem; padding: 2px 6px; }
    .btn-spoiler.on { background: #4c1d95; border-color: #7c3aed; color: #c4b5fd; }

    #exportArea {
      text-align: center;
      max-width: 920px;
      margin: 0 auto 32px;
    }
    #btnExport {
      padding: 10px 28px;
      background: #4f46e5;
      border: none;
      color: white;
      font-size: 0.9rem;
      border-radius: 8px;
    }
    #btnExport:hover { background: #6366f1; }
    .export-note { font-size: 0.7rem; color: #64748b; margin-top: 6px; }

    #modal {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.78);
      z-index: 300;
      align-items: center;
      justify-content: center;
    }
    #modal.open { display: flex; }

    #modalBox {
      background: #1e293b;
      border-radius: 10px;
      padding: 20px;
      width: min(480px, 92vw);
      max-height: 80vh;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    /* タブ */
    .modal-tabs {
      display: flex;
      gap: 6px;
    }
    .tab-btn {
      flex: 1;
      padding: 6px 4px;
      font-size: 0.8rem;
      border-radius: 5px;
      border: 1px solid #475569;
      background: #334155;
      color: #94a3b8;
      cursor: pointer;
      transition: background 0.12s;
    }
    .tab-btn:hover { background: #475569; }
    .tab-btn.active {
      background: #4f46e5;
      border-color: #4f46e5;
      color: #fff;
    }

    #searchInput {
      width: 100%;
      padding: 8px 12px;
      background: #334155;
      border: 1px solid #475569;
      color: #f1f5f9;
      border-radius: 6px;
      font-size: 0.88rem;
      outline: none;
      font-family: inherit;
    }
    #searchInput:focus { border-color: #818cf8; }

    #searchResults { overflow-y: auto; flex: 1; min-height: 80px; }

    .result-item {
      display: flex;
      gap: 10px;
      align-items: center;
      padding: 8px;
      border-radius: 6px;
      cursor: pointer;
      transition: background 0.12s;
    }
    .result-item:hover { background: #334155; }
    .result-thumb {
      width: 46px;
      height: 60px;
      object-fit: cover;
      border-radius: 3px;
      background: #334155;
      flex-shrink: 0;
    }
    .result-name { font-size: 0.82rem; }

    .status { font-size: 0.78rem; color: #64748b; padding: 8px; }
    .status.err { color: #f87171; }
    #modalFoot { display: flex; justify-content: flex-end; }

    /* 手動入力パネル */
    #manualPanel { flex-direction: column; gap: 10px; }
    #manualTitle {
      width: 100%;
      padding: 8px 12px;
      background: #334155;
      border: 1px solid #475569;
      color: #f1f5f9;
      border-radius: 6px;
      font-size: 0.88rem;
      outline: none;
      font-family: inherit;
    }
    #manualTitle:focus { border-color: #818cf8; }
    .file-row { display: flex; align-items: center; gap: 10px; }
    #manualFile { flex: 1; font-size: 0.78rem; color: #94a3b8; }
    #manualPreview {
      width: 52px; height: 70px;
      object-fit: cover;
      border-radius: 4px;
      background: #334155;
      display: none;
    }
    #manualPreview.visible { display: block; }
    #btnManualAdd {
      align-self: flex-end;
      padding: 6px 18px;
      background: #4f46e5;
      border: none;
      color: white;
      border-radius: 5px;
    }
    #btnManualAdd:hover { background: #6366f1; }
  </style>
</head>
<body>

<h1>私を構成する9つのゲーム</h1>

<div class="settings">
  <label>名前：<input type="text" id="nameInput" placeholder="あなたの名前" /></label>
  <button id="btnSave">保存</button>
</div>

<div id="capture">
  <div id="captureHeader"><strong id="displayName">あなた</strong> の9つのゲーム</div>
  <div class="grid" id="grid"></div>
</div>

<div id="exportArea">
  <button id="btnExport">📷 画像を保存</button>
  <p class="export-note">ボタン類は画像に含まれません。ネタバレ隠し中のコメントはぼかして出力されます。</p>
</div>

<div id="modal">
  <div id="modalBox">
    <div class="modal-tabs">
      <button class="tab-btn active" id="tabSteam">Steam</button>
      <button class="tab-btn" id="tabIgdb">IGDB</button>
      <button class="tab-btn" id="tabManual">手動入力</button>
    </div>
    <input type="text" id="searchInput" placeholder="タイトルを入力..." autocomplete="off" />
    <div id="searchResults"><p class="status">タイトルを入力してください</p></div>
    <div id="manualPanel" style="display:none">
      <input type="text" id="manualTitle" placeholder="ゲームタイトル" autocomplete="off" />
      <div class="file-row">
        <input type="file" id="manualFile" accept="image/*" />
        <img id="manualPreview" alt="" />
      </div>
      <button id="btnManualAdd">追加</button>
    </div>
    <div id="modalFoot"><button id="btnClose">閉じる</button></div>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"
        crossorigin="anonymous"></script>
<script>
const STORE = 'my9games_v2';

const state = {
  name: '',
  games: Array(9).fill(null),
  comments: Array(9).fill(''),
  spoilers: Array(9).fill(false),
};

function load() {
  try {
    const s = localStorage.getItem(STORE);
    if (s) Object.assign(state, JSON.parse(s));
  } catch {}
}

function save() {
  localStorage.setItem(STORE, JSON.stringify(state));
}

function renderAll() {
  document.getElementById('nameInput').value = state.name;
  document.getElementById('displayName').textContent = state.name || 'あなた';
  renderGrid();
}

function renderGrid() {
  const grid = document.getElementById('grid');
  grid.innerHTML = '';
  for (let i = 0; i < 9; i++) renderSlot(grid, i);
}

function renderSlot(grid, i) {
  const g = state.games[i];
  const slot = document.createElement('div');
  slot.className = 'slot';

  const coverWrap = document.createElement('div');
  coverWrap.className = 'slot-cover';
  if (g) {
    const img = document.createElement('img');
    img.src = g.cover;
    img.alt = g.name;
    coverWrap.appendChild(img);
    const hint = document.createElement('div');
    hint.className = 'slot-cover-hint';
    hint.textContent = '変更';
    coverWrap.appendChild(hint);
    coverWrap.onclick = () => openModal(i);
  } else {
    const empty = document.createElement('div');
    empty.className = 'slot-empty';
    empty.innerHTML = '<div class="plus">＋</div><div class="label">ゲームを選ぶ</div>';
    empty.onclick = () => openModal(i);
    coverWrap.appendChild(empty);
  }
  slot.appendChild(coverWrap);

  if (g) {
    const body = document.createElement('div');
    body.className = 'slot-body';

    const title = document.createElement('div');
    title.className = 'slot-title';
    title.textContent = g.name;
    body.appendChild(title);

    const ta = document.createElement('textarea');
    ta.className = 'slot-comment' + (state.spoilers[i] ? ' spoiler' : '');
    ta.placeholder = 'コメント...';
    ta.value = state.comments[i];
    ta.addEventListener('input', e => { state.comments[i] = e.target.value; save(); });
    body.appendChild(ta);
    slot.appendChild(body);

    const actions = document.createElement('div');
    actions.className = 'slot-actions';

    const btnSp = document.createElement('button');
    btnSp.className = 'btn-spoiler' + (state.spoilers[i] ? ' on' : '');
    btnSp.textContent = state.spoilers[i] ? '⚠ ネタバレ中' : 'ネタバレ隠す';
    btnSp.onclick = () => { state.spoilers[i] = !state.spoilers[i]; save(); renderGrid(); };
    actions.appendChild(btnSp);

    const btnDel = document.createElement('button');
    btnDel.textContent = '✕';
    btnDel.onclick = () => {
      state.games[i] = null;
      state.comments[i] = '';
      state.spoilers[i] = false;
      save(); renderGrid();
    };
    actions.appendChild(btnDel);

    slot.appendChild(actions);
  }

  grid.appendChild(slot);
}

// ---- Search modal ----

let activeSlot = -1;
let searchTimer = null;
let searchSource = 'steam';

function setTab(source) {
  searchSource = source;
  document.getElementById('tabSteam').classList.toggle('active', source === 'steam');
  document.getElementById('tabIgdb').classList.toggle('active', source === 'igdb');
  document.getElementById('tabManual').classList.toggle('active', source === 'manual');
  const isManual = source === 'manual';
  document.getElementById('searchInput').style.display = isManual ? 'none' : '';
  document.getElementById('searchResults').style.display = isManual ? 'none' : '';
  document.getElementById('manualPanel').style.display = isManual ? 'flex' : 'none';
  if (!isManual) {
    const q = document.getElementById('searchInput').value;
    if (q.trim()) doSearch(q);
    else document.getElementById('searchResults').innerHTML = '<p class="status">タイトルを入力してください</p>';
  }
}

function openModal(i) {
  activeSlot = i;
  document.getElementById('modal').classList.add('open');
  const si = document.getElementById('searchInput');
  si.value = '';
  document.getElementById('searchResults').innerHTML = '<p class="status">タイトルを入力してください</p>';
  document.getElementById('manualTitle').value = '';
  document.getElementById('manualFile').value = '';
  const prev = document.getElementById('manualPreview');
  prev.src = ''; prev.classList.remove('visible');
  if (searchSource === 'manual') document.getElementById('manualTitle').focus();
  else si.focus();
}

function closeModal() {
  document.getElementById('modal').classList.remove('open');
  activeSlot = -1;
}

async function doSearch(q) {
  if (!q.trim()) {
    document.getElementById('searchResults').innerHTML = '<p class="status">タイトルを入力してください</p>';
    return;
  }
  document.getElementById('searchResults').innerHTML = '<p class="status">検索中…</p>';
  const endpoint = searchSource === 'igdb' ? '/api/igdb_search' : '/api/search';
  try {
    const res = await fetch(endpoint + '?' + new URLSearchParams({ q }));
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const items = await res.json();
    if (items.error) throw new Error(items.error);

    const box = document.getElementById('searchResults');
    if (!items.length) {
      box.innerHTML = '<p class="status">見つかりませんでした</p>';
      return;
    }
    box.innerHTML = '';
    for (const g of items) {
      const item = document.createElement('div');
      item.className = 'result-item';
      const thumbSrc = g.thumb || (searchSource === 'steam' ? `/api/cover?id=${g.id}` : '');
      item.innerHTML = `
        <img class="result-thumb" src="${esc(thumbSrc)}" onerror="this.style.opacity=0.2" alt="" />
        <div class="result-name">${esc(g.name)}</div>
      `;
      item.onclick = () => pickGame(g);
      box.appendChild(item);
    }
  } catch (e) {
    document.getElementById('searchResults').innerHTML =
      '<p class="status err">エラー: ' + esc(e.message) + '</p>';
  }
}

function pickGame(g) {
  if (activeSlot < 0) return;
  const cover = g.cover || (searchSource === 'steam' ? '/api/cover?id=' + g.id : '');
  state.games[activeSlot] = { id: g.id, name: g.name, cover };
  save();
  renderGrid();
  closeModal();
}

// ---- Export ----

async function exportImage() {
  const target = document.getElementById('capture');
  const toHide = [...target.querySelectorAll('.slot-actions')];
  toHide.forEach(el => { el.dataset.d = el.style.display; el.style.display = 'none'; });
  try {
    const canvas = await html2canvas(target, { backgroundColor: '#0f172a', scale: 2, logging: false });
    const a = document.createElement('a');
    a.download = 'my9games.png';
    a.href = canvas.toDataURL('image/png');
    a.click();
  } catch (e) {
    alert('画像出力に失敗しました: ' + e.message);
  } finally {
    toHide.forEach(el => { el.style.display = el.dataset.d ?? ''; });
  }
}

function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ---- Events ----

document.getElementById('tabSteam').addEventListener('click', () => setTab('steam'));
document.getElementById('tabIgdb').addEventListener('click', () => setTab('igdb'));
document.getElementById('tabManual').addEventListener('click', () => setTab('manual'));
document.getElementById('manualFile').addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = ev => {
    const prev = document.getElementById('manualPreview');
    prev.src = ev.target.result;
    prev.classList.add('visible');
  };
  reader.readAsDataURL(file);
});
document.getElementById('btnManualAdd').addEventListener('click', () => {
  if (activeSlot < 0) return;
  const name = document.getElementById('manualTitle').value.trim();
  if (!name) { alert('タイトルを入力してください'); return; }
  const prev = document.getElementById('manualPreview');
  const cover = prev.classList.contains('visible') ? prev.src : '';
  state.games[activeSlot] = { id: 'manual_' + Date.now(), name, cover };
  save(); renderGrid(); closeModal();
});
document.getElementById('searchInput').addEventListener('input', e => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => doSearch(e.target.value), 350);
});
document.getElementById('btnClose').addEventListener('click', closeModal);
document.getElementById('modal').addEventListener('click', e => {
  if (e.target === document.getElementById('modal')) closeModal();
});
document.getElementById('btnExport').addEventListener('click', exportImage);
document.getElementById('btnSave').addEventListener('click', () => {
  state.name = document.getElementById('nameInput').value.trim();
  document.getElementById('displayName').textContent = state.name || 'あなた';
  save();
});
document.getElementById('nameInput').addEventListener('input', e => {
  document.getElementById('displayName').textContent = e.target.value.trim() || 'あなた';
});

load();
renderAll();
</script>
</body>
</html>"""


if __name__ == "__main__":
    server = HTTPServer(("localhost", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"起動中: {url}")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n停止しました")
