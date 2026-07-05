"""内网摄像头扫描工具 - 扫描IP段，发现ONVIF/RTSP设备"""
import socket, threading, queue, subprocess, os, json, httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
import ipaddress

# 内网网段（根据实际情况修改）
SUBNETS = ["192.168.1.0/24", "192.168.0.0/24", "172.16.0.0/24", "10.0.0.0/24"]
SCAN_PORTS = [80, 554, 8080, 8090, 37777, 34567, 8999]  # 常见摄像头端口
TIMEOUT = 2
THREADS = 100

found_devices = []
lock = threading.Lock()

def check_port(ip, port):
    """检测端口是否开放"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(TIMEOUT)
        r = s.connect_ex((ip, port))
        s.close()
        return r == 0
    except:
        return False

def check_rtsp(ip):
    """检测RTSP流"""
    try:
        with httpx.Client(timeout=3) as c:
            r = c.request("OPTIONS", f"rtsp://{ip}:554/", headers={"User-Agent": "VLC/3.0"})
            if r.status_code < 400:
                return True
    except:
        pass
    return False

def check_onvif(ip, port=80):
    """检测ONVIF设备"""
    try:
        body = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
  xmlns:wsdd="http://schemas.xmlsoap.org/ws/2005/04/discovery"
  xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
  <soap:Header/>
  <soap:Body>
    <wsdd:Probe>
      <wsdd:Types>dn:NetworkVideoTransmitter</wsdd:Types>
    </wsdd:Probe>
  </soap:Body>
</soap:Envelope>"""
        with httpx.Client(timeout=3) as c:
            r = c.post(f"http://{ip}:{port}/onvif/device_service",
                       data=body,
                       headers={"Content-Type": "application/soap+xml"})
            return "http://www.onvif.org/" in r.text
    except:
        return False

def check_http_camera(ip, port=80):
    """检测HTTP摄像头页面"""
    try:
        with httpx.Client(timeout=2, verify=False) as c:
            r = c.get(f"http://{ip}:{port}", headers={"User-Agent": "Mozilla/5.0"})
            body = r.text.lower()
            # 常见摄像头特征
            keywords = ["hikvision", "大华", "dahua", "摄像头", "ipc", "nvr",
                       "dvr", "web service", "login", "onvif", "camera",
                       "snapshot", "h264", "h265", "rtsp", "liveview"]
            score = sum(1 for kw in keywords if kw in body)
            if score >= 2:
                return True, r.text[:200]
    except:
        pass
    return False, ""

def scan_ip(ip):
    """扫描单个IP的所有端口"""
    results = []
    for port in SCAN_PORTS:
        if check_port(ip, port):
            results.append(port)
    return results

def probe_device(ip, open_ports):
    """探测开放端口的设备类型"""
    device = {"ip": ip, "ports": open_ports, "type": [], "rtsp": "", "name": ""}
    
    if 554 in open_ports:
        device["type"].append("RTSP")
        device["rtsp"] = f"rtsp://{ip}:554/"
    
    for port in open_ports:
        if port == 80 or port == 8080:
            ok, info = check_http_camera(ip, port)
            if ok:
                device["type"].append(f"HTTP摄像头({port})")
                device["name"] = info[:80]
    
    for port in open_ports:
        if port in [80, 8080]:
            if check_onvif(ip, port):
                device["type"].append(f"ONVIF({port})")
    
    if device["type"]:
        with lock:
            found_devices.append(device)
        print(f"  ✅ {ip:15} 端口:{str(open_ports):15} 类型:{'/'.join(device['type'])}")
        if device["rtsp"]:
            print(f"     RTSP: {device['rtsp']}")

def scan_network():
    """扫描网络"""
    # 获取本机IP和网段
    print("=== 内网摄像头扫描 ===")
    print(f"扫描线程: {THREADS} 超时: {TIMEOUT}s")
    print(f"扫描端口: {SCAN_PORTS}")
    print()
    
    all_ips = []
    for subnet_str in SUBNETS:
        try:
            subnet = ipaddress.ip_network(subnet_str, strict=False)
            for ip in subnet.hosts():
                all_ips.append(str(ip))
        except:
            pass
    
    print(f"共 {len(all_ips)} 个IP地址需要扫描")
    print()
    
    # 第一阶段：端口扫描
    print("=== 第1阶段：端口扫描 ===")
    ip_ports = {}
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        future_to_ip = {executor.submit(scan_ip, ip): ip for ip in all_ips}
        for i, future in enumerate(as_completed(future_to_ip)):
            ip = future_to_ip[future]
            ports = future.result()
            if ports:
                ip_ports[ip] = ports
            if i % 50 == 0:
                print(f"  进度: {i}/{len(all_ips)} 已发现 {len(ip_ports)} 个设备")
    
    print(f"  扫描完成，发现 {len(ip_ports)} 个设备")
    print()
    
    # 第二阶段：设备类型探测
    print("=== 第2阶段：设备探测 ===")
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(probe_device, ip, ports): ip for ip, ports in ip_ports.items()}
        for future in as_completed(futures):
            pass
    
    print()
    print(f"=== 扫描完成 ===")
    print(f"共发现 {len(found_devices)} 个摄像头/视频设备")
    
    # 保存结果
    output = {"scan_time": __import__('datetime').datetime.now().isoformat(),
              "total_ips": len(all_ips),
              "total_devices": len(found_devices),
              "devices": found_devices}
    
    with open("/opt/aiWatchdog/camera_scan.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"结果已保存到 /opt/aiWatchdog/camera_scan.json")
    print()
    
    # 打印RTSP列表
    rtsp_list = [d for d in found_devices if d.get("rtsp")]
    if rtsp_list:
        print("=== RTSP流列表 ===")
        for d in rtsp_list:
            print(f"  {d['rtsp']}")

if __name__ == "__main__":
    scan_network()
