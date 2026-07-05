"""IP变更监控 - 检测外网IP变化并推送到钉钉"""
import httpx, time, os, socket

IP_FILE = "/opt/aiWatchdog/last_ip.txt"
DINGTALK_URL = "https://oapi.dingtalk.com/robot/send?access_token=4f47828fb7233dc781ab3bc13ac200bdf71bcbd91aa396fcfad305e9bfef46b5"

def get_public_ip():
    try:
        r = httpx.get("http://ip.3322.net", timeout=10)
        return r.text.strip()
    except:
        try:
            r = httpx.get("http://myip.ipip.net", timeout=10)
            return r.text.strip()
        except:
            return None

def send_dingtalk(new_ip, old_ip):
    hostname = socket.gethostname()
    msg = "电梯系统 [" + hostname + "] IP地址已变更\n旧IP: " + old_ip + "\n新IP: " + new_ip
    try:
        httpx.post(DINGTALK_URL, json={"msgtype":"text","text":{"content":msg}}, timeout=5)
        print("已发送IP变更通知: " + old_ip + " -> " + new_ip)
    except Exception as e:
        print("发送失败: " + str(e))

last_ip = None
if os.path.exists(IP_FILE):
    with open(IP_FILE) as f:
        last_ip = f.read().strip()
    print("上次记录IP: " + str(last_ip))

print("IP监控已启动，每10分钟检测一次")
while True:
    ip = get_public_ip()
    if ip:
        if last_ip and ip != last_ip:
            send_dingtalk(ip, last_ip)
        last_ip = ip
        with open(IP_FILE, "w") as f:
            f.write(ip)
        print("当前IP: " + ip)
    else:
        print("获取IP失败")
    time.sleep(600)
