"""扫描内网摄像头并自动添加到WVP管理平台"""
import socket, concurrent.futures, httpx, json, time, os, re

WVP_LOGIN = "http://localhost:18080/api/user/login"
WVP_PROXY_ADD = "http://localhost:18080/api/proxy/add"
WVP_PROXY_START = "http://localhost:18080/api/proxy/start"

def wvp_login():
    r = httpx.get(WVP_LOGIN, params={"username":"admin","password":"21232f297a57a5a743894a0e4a801fc3"}, timeout=10)
    return r.json()["data"]["accessToken"]

def scan_port(ip, port):
    try:
        s = socket.socket()
        s.settimeout(1)
        if s.connect_ex((ip, port)) == 0:
            s.close()
            return (ip, port)
        s.close()
    except:
        pass
    return None

def scan_network(subnets=["192.168.1.0/24","192.168.0.0/24","172.16.0.0/24","10.0.0.0/24"]):
    """扫描内网，发现开放的RTSP端口(554)和HTTP端口(80/8080)"""
    print("开始扫描内网...")
    ips = []
    for subnet in subnets:
        base = ".".join(subnet.split(".")[:3])
        ips += [f"{base}.{i}" for i in range(1, 255)]
    
    found = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=300) as ex:
        futures = {ex.submit(scan_port, ip, p): (ip, p) for ip in ips for p in [554, 80, 8080]}
        for f in concurrent.futures.as_completed(futures):
            r = f.result()
            if r:
                ip, port = r
                if ip not in found:
                    found[ip] = []
                if port not in found[ip]:
                    found[ip].append(port)
    
    devices = []
    for ip, ports in found.items():
        device = {"ip": ip, "ports": ports, "rtsp": f"rtsp://{ip}:554/" if 554 in ports else ""}
        devices.append(device)
        print(f"  {ip} 端口:{ports}")
    
    return devices

def test_rtsp(rtsp_url):
    """测试RTSP流是否可用"""
    try:
        s = socket.socket()
        s.settimeout(2)
        ip = rtsp_url.split("://")[1].split(":")[0]
        port = int(rtsp_url.split(":")[-1].split("/")[0])
        r = s.connect_ex((ip, port))
        s.close()
        return r == 0
    except:
        return False

def add_to_wvp(token, name, rtsp_url):
    """添加到WVP流代理"""
    headers = {"access-token": token}
    
    # 添加代理
    data = {
        "name": name,
        "streamId": "cam_" + re.sub(r'[^a-zA-Z0-9]', '_', name.lower()),
        "url": rtsp_url,
        "enableHls": True,
        "enableFlv": True,
        "enableRtsp": True,
        "enableAudio": False,
        "enableRemoveNoneReader": False,
        "mediaServerId": "zlmediakit-local"
    }
    
    r = httpx.post(WVP_PROXY_ADD, json=data, headers=headers, timeout=10)
    result = r.json()
    if result.get("code") == 0:
        print(f"  ✅ 已添加: {name} -> {rtsp_url}")
        # 启动代理
        stream_id = data["streamId"]
        r2 = httpx.get(f"{WVP_PROXY_START}?streamId={stream_id}", headers=headers, timeout=10)
        print(f"     播放地址: http://121.29.248.85:9092/rtp/{stream_id}.live.flv")
        return True
    else:
        print(f"  ❌ 添加失败: {result.get('msg','')}")
        return False

def main():
    print("=== 内网摄像头扫描+自动添加到WVP ===\n")
    
    # 登录WVP
    print("登录WVP...")
    token = wvp_login()
    print("登录成功\n")
    
    # 扫描
    devices = scan_network()
    
    if not devices:
        print("\n未发现任何设备")
        return
    
    # 过滤出有RTSP的设备
    rtsp_devices = [d for d in devices if d["rtsp"]]
    http_devices = [d for d in devices if 80 in d["ports"] and d not in rtsp_devices]
    
    print(f"\n发现 {len(devices)} 个设备")
    print(f"  RTSP摄像头: {len(rtsp_devices)}")
    print(f"  HTTP设备: {len(http_devices)}")
    
    # 自动添加RTSP设备到WVP
    if rtsp_devices:
        print("\n=== 自动添加到WVP ===")
        for i, dev in enumerate(rtsp_devices):
            name = f"摄像头_{dev['ip'].replace('.','_')}"
            add_to_wvp(token, name, dev["rtsp"])
    
    print("\n=== 完成 ===")
    print(f"请刷新WVP管理页面查看: http://121.29.248.85:28080")

if __name__ == "__main__":
    main()
