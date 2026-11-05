# Alive Games

Kumpulan game dua pemain **AI vs manusia**, dibuat khusus supaya AI (Alive)
bisa bermain cepat lewat API langsung — tanpa browser, tanpa klik-klik papan
di situs orang lain.

- **Manusia** bermain dari halaman web (papan catur di browser HP).
- **AI** bermain lewat API HTTP (`curl`/kode), langkah divalidasi server.

## Game yang tersedia

- ♟️ **Catur** — aturan lengkap (validasi [python-chess](https://python-chess.readthedocs.io/)):
  rokade, en passant, promosi, skakmat, stalemate, remis materi tidak cukup.

Game lain (tic-tac-toe, dll.) menyusul — server ini memang dibuat untuk
ditambah game baru.

## Cara jalan

```bash
pip install -r requirements.txt
GAME_TOKEN=tokenrahasia uvicorn app:app --port 8000
```

Lalu:

- Halaman manusia: `http://localhost:8000/?g=<game_id>`
- AI membuat game baru dan menggerakkan bidaknya lewat API.

## API

| Aksi | Endpoint |
|---|---|
| Cek server | `GET /api/health` |
| Buat game (AI, header `X-Token`) | `POST /api/games` body `{"ai_color":"white"}` |
| Lihat keadaan game | `GET /api/games/{id}` |
| Langkah AI (header `X-Token`) | `POST /api/games/{id}/move/ai` body `{"move":"e4"}` |
| Langkah manusia | `POST /api/games/{id}/move/human` body `{"move":"e2e4"}` |

Langkah boleh ditulis SAN (`e4`, `Nf3`, `O-O`) atau UCI (`e2e4`).
Promosi pion dari halaman web otomatis jadi menteri.

Keadaan game disimpan di `data/games.json` (diabaikan git) supaya tidak
hilang saat server restart selama instance yang sama masih hidup.

## Deploy (Koyeb)

1. Buat app dari repo ini (Dockerfile sudah disediakan).
2. Set env var `GAME_TOKEN` = token rahasia (jangan commit token ke repo!).
3. Deploy — selesai. AI tinggal memanggil API-nya.

## Catatan

Token hanya pengaman sederhana untuk endpoint AI. Endpoint manusia memakai
`game_id` acak yang tidak bisa ditebak — bagikan link game hanya ke pemainnya.
