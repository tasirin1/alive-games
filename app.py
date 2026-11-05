"""Alive Games — server permainan AI vs manusia.

Satu server kecil untuk kumpulan game dua pemain:
- Manusia bermain dari halaman web (static/index.html).
- AI bermain lewat API HTTP langsung (cepat, tanpa browser).

Game pertama: catur (aturan lengkap divalidasi python-chess).
Struktur dibuat supaya game lain mudah ditambah nanti.

Keamanan sederhana:
- Endpoint AI wajib header  X-Token: <GAME_TOKEN>  (env var).
- Endpoint manusia cukup memakai game_id (UUID acak, tidak bisa ditebak).
- GAME_TOKEN JANGAN PERNAH dicommit ke repo; set sebagai env var di Koyeb.
"""

import json
import os
import threading
import uuid
from pathlib import Path

import chess
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).parent
DATA_FILE = BASE / "data" / "games.json"
TOKEN = os.environ.get("GAME_TOKEN", "")

app = FastAPI(title="Alive Games")

_lock = threading.Lock()
_games: dict[str, dict] = {}


# ---------- penyimpanan sederhana (JSON di disk) ----------

def _load() -> None:
    if DATA_FILE.exists():
        try:
            raw = json.loads(DATA_FILE.read_text())
            for gid, g in raw.items():
                board = chess.Board(g["fen"])
                _games[gid] = {"board": board, "ai_color": g["ai_color"]}
        except Exception:
            pass


def _save() -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        gid: {"fen": g["board"].fen(), "ai_color": g["ai_color"]}
        for gid, g in _games.items()
    }
    DATA_FILE.write_text(json.dumps(raw))


_load()


# ---------- bantuan ----------

def _state(gid: str) -> dict:
    g = _games[gid]
    board: chess.Board = g["board"]
    moves_san = []
    replay = chess.Board()
    for mv in board.move_stack:
        moves_san.append(replay.san(mv))
        replay.push(mv)
    if board.is_checkmate():
        status = "checkmate"
        winner = "black" if board.turn == chess.WHITE else "white"
    elif board.is_stalemate():
        status, winner = "stalemate", None
    elif board.is_insufficient_material():
        status, winner = "draw_insufficient_material", None
    elif board.is_game_over():
        status, winner = "draw", None
    else:
        status, winner = "playing", None
    return {
        "game_id": gid,
        "game": "chess",
        "fen": board.fen(),
        "moves": moves_san,
        "turn": "white" if board.turn == chess.WHITE else "black",
        "ai_color": g["ai_color"],
        "human_color": "black" if g["ai_color"] == "white" else "white",
        "check": board.is_check(),
        "status": status,
        "winner": winner,
        "legal_moves": [board.uci(m) for m in board.legal_moves] if status == "playing" else [],
    }


def _require_token(x_token: str | None) -> None:
    if TOKEN and x_token != TOKEN:
        raise HTTPException(status_code=401, detail="token salah")


def _get_game(gid: str) -> dict:
    if gid not in _games:
        raise HTTPException(status_code=404, detail="game tidak ditemukan")
    return _games[gid]


def _push_move(gid: str, move_text: str, side: str) -> dict:
    g = _get_game(gid)
    board: chess.Board = g["board"]
    if board.is_game_over():
        raise HTTPException(status_code=400, detail="game sudah selesai")
    turn_color = "white" if board.turn == chess.WHITE else "black"
    expected = g["ai_color"] if side == "ai" else (
        "black" if g["ai_color"] == "white" else "white"
    )
    if turn_color != expected:
        raise HTTPException(
            status_code=400,
            detail=f"sekarang giliran {turn_color}, bukan {side} ({expected})",
        )
    move = None
    text = (move_text or "").strip()
    try:
        move = board.parse_san(text)
    except Exception:
        try:
            move = chess.Move.from_uci(text.lower())
            if move not in board.legal_moves:
                move = None
        except Exception:
            move = None
    if move is None:
        raise HTTPException(status_code=400, detail=f"langkah tidak sah: {move_text}")
    board.push(move)
    _save()
    return _state(gid)


# ---------- API ----------

@app.get("/api/health")
def health():
    return {"ok": True, "games": len(_games)}


@app.post("/api/games")
async def create_game(req: Request, x_token: str | None = Header(default=None)):
    """Buat game catur baru. Dipakai AI (wajib token bila GAME_TOKEN diset)."""
    _require_token(x_token)
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    ai_color = (body or {}).get("ai_color", "white")
    if ai_color not in ("white", "black"):
        raise HTTPException(status_code=400, detail="ai_color harus white/black")
    with _lock:
        gid = uuid.uuid4().hex[:12]
        _games[gid] = {"board": chess.Board(), "ai_color": ai_color}
        _save()
        return _state(gid)


@app.get("/api/games/{gid}")
def get_game(gid: str):
    _get_game(gid)
    return _state(gid)


@app.post("/api/games/{gid}/move/ai")
async def move_ai(gid: str, req: Request, x_token: str | None = Header(default=None)):
    """Langkah AI. Body: {"move": "e4"} atau {"move": "e2e4"}."""
    _require_token(x_token)
    body = await req.json()
    with _lock:
        return _push_move(gid, body.get("move", ""), side="ai")


@app.post("/api/games/{gid}/move/human")
async def move_human(gid: str, req: Request):
    """Langkah manusia dari halaman web. Body: {"move": "e2e4"} (UCI) atau SAN."""
    body = await req.json()
    with _lock:
        return _push_move(gid, body.get("move", ""), side="human")


# ---------- halaman web ----------

@app.get("/")
def index():
    return FileResponse(BASE / "static" / "index.html")


app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


@app.exception_handler(HTTPException)
async def http_exc_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
