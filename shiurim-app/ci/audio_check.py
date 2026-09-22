import concurrent.futures, json, re, sys, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

DATA = "shiurim-app/shared/recordings.json"
with open(DATA, encoding="utf-8") as f:
    recordings = json.load(f)

def looks_audio(head: bytes, content_type: str) -> bool:
    b = head[:64]
    ct = (content_type or "").lower()
    if ct.startswith("audio/"):
        return True
    if b.startswith(b"ID3") or b.startswith(b"OggS") or b.startswith(b"RIFF"):
        return True
    if len(b) >= 12 and b[4:8] == b"ftyp":
        return True
    # MPEG audio frame sync (MP3 without ID3)
    if len(b) >= 2 and b[0] == 0xFF and (b[1] & 0xE0) == 0xE0:
        return True
    return False

def check(r):
    req = Request(r["url"], headers={
        "Range": "bytes=0-8191",
        "User-Agent": "Mozilla/5.0 ShiurimAudioCheck/1.0"
    })
    try:
        with urlopen(req, timeout=25) as resp:
            status = getattr(resp, "status", 200)
            ct = resp.headers.get("Content-Type", "")
            final_url = resp.geturl()
            head = resp.read(8192)
            ok = status in (200, 206) and looks_audio(head, ct)
            return {
                "ok": ok, "id": r["id"], "title": r["title"],
                "status": status, "content_type": ct,
                "bytes": len(head), "final_url": final_url
            }
    except Exception as e:
        return {"ok": False, "id": r["id"], "title": r["title"], "error": repr(e)}

start = time.time()
results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
    for i, result in enumerate(ex.map(check, recordings), 1):
        results.append(result)
        if i % 50 == 0:
            print(f"checked {i}/{len(recordings)}", flush=True)

bad = [r for r in results if not r["ok"]]
good = len(results) - len(bad)
print(f"RESULT: {good}/{len(results)} audio links passed in {time.time()-start:.1f}s")
if bad:
    print("FAILED LINKS:")
    for r in bad:
        print(json.dumps(r, ensure_ascii=False))
    sys.exit(1)
