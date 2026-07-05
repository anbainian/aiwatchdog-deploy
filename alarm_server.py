import os, pymysql, uvicorn, httpx, json, time, secrets
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, Response

app = FastAPI(title="AI告警")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

TOKEN_FILE = "/opt/aiWatchdog/tokens.json"
DB = {"host":"127.0.0.1","port":3306,"user":"root","password":"1234567890","database":"wvp"}

def load_tokens():
    if os.path.exists(TOKEN_FILE):
        try: return json.load(open(TOKEN_FILE))
        except: return {}
    return {}

def save_tokens(tokens):
    json.dump(tokens, open(TOKEN_FILE, "w"))

def get_ch(token):
    tokens = load_tokens()
    if token not in tokens or tokens[token]["expires"] < time.time():
        return None
    return tokens[token]["ch"]

@app.get("/api/alarms")
async def get_alarms(page:int=1,count:int=50):
    conn = pymysql.connect(**DB)
    try:
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute("SELECT * FROM wvp_device_alarm ORDER BY id DESC LIMIT %s OFFSET %s", (count, (page-1)*count))
        alarms = cur.fetchall()
        cur.execute("SELECT COUNT(*) t FROM wvp_device_alarm")
        total = cur.fetchone()["t"]
        return {"code":0, "data":{"total":total, "list":alarms}}
    finally:
        conn.close()

@app.get("/api/photo/{alarm_id}")
async def photo(alarm_id:int):
    p = "/opt/aiWatchdog/snapshots/" + str(alarm_id) + ".jpg"
    if os.path.exists(p): return FileResponse(p, media_type="image/jpeg")
    return {"code":404}

@app.get("/api/token/{ch}")
async def gen_token(ch: str):
    token = secrets.token_hex(16)
    tokens = load_tokens()
    tokens[token] = {"ch": ch, "expires": time.time() + 900}
    save_tokens(tokens)
    return {"token": token, "expires": 900}

async def proxy_stream(url):
    async with httpx.AsyncClient(timeout=None) as c:
        async with c.stream("GET", url) as resp:
            async for chunk in resp.aiter_bytes():
                yield chunk

@app.get("/hls/{token}.m3u8")
async def hls_playlist(token: str):
    ch = get_ch(token)
    if not ch:
        return HTMLResponse("expired", status_code=403)
    try:
        r = httpx.get("http://127.0.0.1:9092/rtp/" + ch + "/hls.m3u8", timeout=10)
        lines = []
        for line in r.text.split("\n"):
            if line.strip().endswith(".ts"):
                parts = line.strip().split("/")
                lines.append("/hls/" + token + "/seg/" + parts[-1])
            else:
                lines.append(line)
        return Response("\n".join(lines), media_type="application/vnd.apple.mpegurl")
    except:
        return HTMLResponse("stream error", status_code=503)

@app.get("/hls/{token}/seg/{seg_name}")
async def hls_segment(token: str, seg_name: str):
    ch = get_ch(token)
    if not ch:
        return HTMLResponse("expired", status_code=403)
    try:
        r = httpx.get("http://127.0.0.1:9092/rtp/" + ch + "/hls.m3u8", timeout=5)
        for line in r.text.split("\n"):
            if line.strip().endswith("/" + seg_name):
                url = "http://127.0.0.1:9092/rtp/" + ch + "/" + line.strip()
                return StreamingResponse(proxy_stream(url), media_type="video/MP2T")
    except:
        pass
    return HTMLResponse("segment not found", status_code=404)

@app.get("/watch/{token}")
async def watch(token: str):
    ch = get_ch(token)
    if not ch:
        return HTMLResponse("<h2 style='text-align:center;margin-top:100px;color:#666'>链接已过期</h2>")
    h = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>视频</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest/dist/hls.min.js"></script>
<style>*{margin:0;padding:0;background:#000}video{width:100%;height:95vh}</style>
</head>
<body>
<video id="v" controls autoplay muted playsinline style="width:100%;height:95vh"></video>
<script>
var url = "/hls/""" + token + """.m3u8";
if (Hls.isSupported()) {
  var hls = new Hls();
  hls.loadSource(url);
  hls.attachMedia(document.getElementById("v"));
} else {
  document.getElementById("v").src = url;
}
</script>
</body></html>"""
    return HTMLResponse(h)

PAGE = """<!DOCTYPE html><html><body><h2>AI告警</h2><ul id="x"></ul>
<script>
fetch('/api/alarms?page=1&count=50').then(r=>r.json()).then(function(d){
var h='';var list=d.data.list;
for(var i=0;i<list.length;i++){var a=list[i];h+='<li>'+a.id+' - '+a.alarm_description+' ['+a.alarm_time+']</li>';}
document.getElementById('x').innerHTML=h||'<li>暂无</li>'});
</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return PAGE

import socket, concurrent.futures
from fastapi.responses import HTMLResponse as HTMLResp

@app.get("/api/scan")
async def api_scan():
    def check(ip, port):
        try:
            s = socket.socket()
            s.settimeout(1)
            if s.connect_ex((ip, port)) == 0:
                s.close(); return (ip, port)
            s.close()
        except: pass
        return None
    devices = {}
    ips = []
    for subnet in ["192.168.1","192.168.0","172.16.10","10.0.0"]:
        ips += [f"{subnet}.{i}" for i in range(1,255)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=300) as ex:
        futs = {ex.submit(check, ip, p): (ip,p) for ip in ips for p in [554,80,8080]}
        for f in concurrent.futures.as_completed(futs):
            r = f.result()
            if r:
                ip, port = r
                if ip not in devices: devices[ip] = []
                if port not in devices[ip]: devices[ip].append(port)
    result = []
    for ip, ports in devices.items():
        item = {"ip": ip, "ports": ports}
        if 554 in ports: item["rtsp"] = f"rtsp://{ip}:554/"
        result.append(item)
    return {"code": 0, "data": result}

@app.get("/api/scan_add")
async def api_scan_add(ip: str, rtsp: str = ""):
    try:
        r = httpx.get("http://localhost:18080/api/user/login", params={"username":"admin","password":"21232f297a57a5a743894a0e4a801fc3"})
        token = r.json()["data"]["accessToken"]
        name = "cam_" + ip.replace(".", "_")
        data = {"name": name, "streamId": name, "url": rtsp or f"rtsp://{ip}:554/",
                "enableHls": True, "enableFlv": True, "enableRtsp": False,
                "enableRemoveNoneReader": False, "mediaServerId": "zlmediakit-local"}
        r2 = httpx.post("http://localhost:18080/api/proxy/add", json=data, headers={"access-token": token})
        return r2.json()
    except Exception as e:
        return {"code": -1, "msg": str(e)}

SCAN_HTML = '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>扫描摄像头</title><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:sans-serif;background:#f0f2f5;padding:20px}h1{font-size:18px;margin-bottom:12px}button{padding:8px 20px;font-size:14px;border:none;border-radius:6px;cursor:pointer}.btn-scan{background:#409EFF;color:#fff}.btn-add{background:#67C23A;color:#fff;font-size:12px;padding:4px 10px}table{width:100%;border-collapse:collapse;background:#fff;border-radius:6px;overflow:hidden;margin-top:12px}th{background:#409EFF;color:#fff;padding:8px 10px;text-align:left;font-size:12px}td{padding:8px 10px;border-bottom:1px solid #eee;font-size:12px}.st{color:#909399;font-size:12px;margin:8px 0}</style></head><body><h1>&#128225; \u5185\u7f51\u6444\u50cf\u5934\u626b\u63cf</h1><button class="btn-scan" id="s" onclick="scan()">&#128269; \u5f00\u59cb\u626b\u63cf</button><span class="st" id="st">\u51c6\u5907\u5c31\u7eea</span><div id="r"></div><script>function scan(){var b=document.getElementById("s");b.disabled=true;b.textContent="\u626b\u63cf\u4e2d...";document.getElementById("st").textContent="\u6b63\u5728\u626b\u63cf...";fetch("/api/scan").then(function(r){return r.json()}).then(function(d){var list=d.data;var h="<table><thead><tr><th>IP</th><th>\u7aef\u53e3</th><th>\u7c7b\u578b</th><th>\u64cd\u4f5c</th></tr></thead><tbody>";if(list.length==0){h+="<tr><td colspan=4 style=text-align:center;color:#ccc;padding:30px>\u672a\u53d1\u73b0\u6444\u50cf\u5934</td></tr>"}else{for(var i=0;i<list.length;i++){var dev=list[i];var type=dev.ports.indexOf(554)>=0?"RTSP\u6444\u50cf\u5934":"HTTP\u8bbe\u5907";var btn="";if(dev.rtsp){btn="<button class=btn-add onclick=add(\\""+dev.ip+"\\")>+ \u6dfb\u52a0\u5230WVP</button>"}h+="<tr><td>"+dev.ip+"</td><td>"+dev.ports.join(", ")+"</td><td>"+type+"</td><td>"+btn+"</td></tr>"}}h+="</tbody></table>";document.getElementById("r").innerHTML=h;document.getElementById("st").textContent="\u626b\u63cf\u5b8c\u6210\uff0c\u53d1\u73b0 "+list.length+" \u4e2a\u8bbe\u5907";b.disabled=false;b.textContent="\u91cd\u65b0\u626b\u63cf"})}function add(ip){fetch("/api/scan_add?ip="+ip).then(function(r){return r.json()}).then(function(d){alert(d.code==0?"\\u2714\\ufe0f \\u5df2\u6dfb\u52a0\u5230WVP\uff01\u5237\u65b0\u9875\u9762\u67e5\u770b":"\\u274c \\u6dfb\u52a0\u5931\u8d25: "+d.msg)})}</script></body></html>'

@app.get("/scan", response_class=HTMLResp)
async def scan_page():
    return SCAN_HTML

if __name__ == "__main__":
    uvicorn.run(app="alarm_server:app", host="0.0.0.0", port=16533)
