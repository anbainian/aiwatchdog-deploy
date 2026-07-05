#!/bin/bash
# AIWatchdog 一键部署脚本
set -e
echo "=== AIWatchdog \u90e8\u7f72\u811a\u672c ==="
mkdir -p /opt/aiWatchdog /opt/aiWatchdog/snapshots /opt/aiWatchdog/video_warning

# \u5b89\u88c5\u4f9d\u8d56
pip3 install opencv-python fastapi uvicorn httpx websockets pymysql 2>/dev/null

# \u521b\u5efa\u544a\u8b66\u670d\u52a1
cat > /etc/systemd/system/aiwatchdog.service << SVCEOF
[Unit]
Description=AIWatchdog Alarm Server
After=network.target
[Service]
ExecStart=/usr/bin/python3 /opt/aiWatchdog/alarm_server.py
WorkingDirectory=/opt/aiWatchdog
Restart=always
User=root
[Install]
WantedBy=multi-user.target
SVCEOF

# \u521b\u5efaIP\u76d1\u63a7\u670d\u52a1
cat > /etc/systemd/system/ipmonitor.service << IPEOF
[Unit]
Description=IP Monitor
After=network.target
[Service]
ExecStart=/usr/bin/python3 /opt/aiWatchdog/ip_monitor.py
WorkingDirectory=/opt/aiWatchdog
Restart=always
User=root
[Install]
WantedBy=multi-user.target
IPEOF

systemctl daemon-reload
echo "=== \u5b8c\u6210 ==="
echo "\u542f\u52a8: systemctl start aiwatchdog"
echo "\u5f00\u673a\u81ea\u542f: systemctl enable aiwatchdog"
