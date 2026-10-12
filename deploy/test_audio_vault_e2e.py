import json
import urllib.request

B = "http://127.0.0.1:4200"


def call(method, path, body=None):
    req = urllib.request.Request(
        B + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"} if body is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> {e.code} {e.read().decode()[:400]}") from None


REC = "voice_lab_vd17_1791428120530"
row = call("POST", "/api/vault/add", {
    "kind": "lab", "src": REC, "role": "NARRATOR",
    "tags": {"emotion": "cold", "intensity": 0.4, "bond": "敬畏", "scene": ["旁白铺陈", "悬疑铺垫"],
             "timbre": ["低沉", "厚实"], "rating": 4, "note": "安装器端到端自检"}})
print("ADD", row["id"], row["derived"], row["tags"].get("pace"), row["tag_prompt"])
sid = row["id"]
vec_row = call("GET", f"/api/vault/list?role=NARRATOR&limit=5")
print("LIST", vec_row["total"], [r["id"] for r in vec_row["rows"]])
print("FILTER-EMO", call("GET", "/api/vault/list?emotion=cold&min_rating=3")["total"],
      "PACE", call("GET", "/api/vault/list?pace_min=0.5&pace_max=1.0")["total"],
      "MISS", call("GET", "/api/vault/list?q=zzzznotexist")["total"])
pick = call("GET", "/api/vault/pick?role=NARRATOR&scene=%E6%82%AC%E7%96%91%E9%93%BA%E5%9E%AB&limit=2")
print("PICK", pick["total"], len(pick["layout"]), pick["candidates"][0]["vector"][:6])
upd = call("POST", "/api/vault/update", {"id": sid, "tags": {"emotion": "anger", "rating": 5}})
print("UPDATE", upd["tags"], upd["derived"]["cps"], "len(tags)=", len(upd["tags"]))
bad = None
try:
    call("POST", "/api/vault/update", {"id": sid, "tags": {"emotion": "furious"}})
except Exception as e:
    bad = str(e)
print("REJECT-BAD-TAG", bad)
print("DELETE", call("DELETE", f"/api/vault/{sid}?purge=false"))

chp = call("POST", "/api/vault/add", {"kind": "chunk", "src": "8", "tags": {"scene": ["旁白铺陈"], "rating": 2}})
print("ADD-CHUNK", chp["id"], chp["kind"], chp["derived"], chp["role"], repr((chp["text"] or "")[:16]))
print("DELETE-CHUNK", call("DELETE", f"/api/vault/{chp['id']}?purge=false"))

hist = call("GET", "/api/voice_lab/history?limit=3&offset=0")
print("HIST", hist["total"], len(hist["records"]), hist["limit"], hist["offset"])
print("HIST-P2", [r["id"][:20] for r in call("GET", "/api/voice_lab/history?limit=3&offset=3")["records"]])
print("HIST-FILTER", call("GET", "/api/voice_lab/history?speaker=NARRATOR")["total"])

# 现造一条只用于改/删自检的记录（顺带验证 generate 的清单写入走 _lab_write）
gen = call("POST", "/api/voice_lab/generate", {
    "model": "cv06", "method": "custom", "voice": "Ryan", "instruct": "calm", "seed": 3,
    "sample_text": "仓库自检：这是一句用来做端到端验证的台词。", "speaker": ""})
print("GENERATE", gen["id"], gen["engine"], gen["seed"], gen["duration_s"])
TEST_REC = gen["id"]
hit = call("POST", "/api/voice_lab/record/update",
           {"id": TEST_REC, "tags": {"emotion": "calm", "rating": 3, "note": "端到端自检"}})
print("REC-UPDATE", hit["tags"])
again = call("POST", "/api/voice_lab/record/update", {"id": TEST_REC, "tags": {"emotion": "calm"}})
print("REPLACE-SEMANTICS", again["tags"], "rating cleared:", "rating" not in again["tags"])
txt = call("POST", "/api/voice_lab/record/update", {"id": TEST_REC, "text": "自检改过的文本"})
print("TEXT-UPDATE", txt["sample_text"])
print("REC-DELETE", call("POST", "/api/voice_lab/record/delete", {"id": TEST_REC, "purge": True}))
left = call("GET", "/api/voice_lab/history?limit=100")
print("AFTER-DELETE", left["total"], TEST_REC in [r["id"] for r in left["records"]])

