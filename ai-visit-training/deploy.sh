#!/bin/bash
# 一键部署到云服务器
# 使用: bash deploy.sh

SERVER="${DEPLOY_HOST:?Set DEPLOY_HOST}"
DEPLOY_USER="${DEPLOY_USER:-root}"
DEPLOY_PORT="${DEPLOY_PORT:-22}"
echo "=== 部署语音对练到 $SERVER ==="

echo "[1/6] 上传项目文件..."
ssh -p "$DEPLOY_PORT" "$DEPLOY_USER@$SERVER" "mkdir -p /opt/voice_practice"
scp -P "$DEPLOY_PORT" -r d:/demo2/app.py d:/demo2/static d:/demo2/doc d:/demo2/requirements.txt "$DEPLOY_USER@$SERVER:/opt/voice_practice/"

echo "[2/6] 安装 Python 依赖..."
ssh -p "$DEPLOY_PORT" "$DEPLOY_USER@$SERVER" "cd /opt/voice_practice && pip3 install flask flask-cors python-dotenv requests python-docx PyPDF2 python-pptx openpyxl -q"

echo "[3/6] 配置 systemd 服务..."
ssh -p "$DEPLOY_PORT" "$DEPLOY_USER@$SERVER" "cat > /etc/systemd/system/voice_practice.service << 'EOF'
[Unit]
Description=Voice Practice AI Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/voice_practice
ExecStart=/usr/bin/python3 /opt/voice_practice/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF"

echo "[4/6] 安装 nginx..."
ssh -p "$DEPLOY_PORT" "$DEPLOY_USER@$SERVER" "apt-get update -qq && apt-get install -y -qq nginx certbot python3-certbot-nginx"

echo "[5/6] 配置 nginx 反向代理..."
ssh -p "$DEPLOY_PORT" "$DEPLOY_USER@$SERVER" "cat > /etc/nginx/sites-available/voice_practice << EOF
server {
    listen 80;
    server_name $SERVER;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }
}
EOF"

ssh -p "$DEPLOY_PORT" "$DEPLOY_USER@$SERVER" "ln -sf /etc/nginx/sites-available/voice_practice /etc/nginx/sites-enabled/ && rm -f /etc/nginx/sites-enabled/default && nginx -t && systemctl reload nginx"

echo "[6/6] 启动服务..."
ssh -p "$DEPLOY_PORT" "$DEPLOY_USER@$SERVER" "systemctl daemon-reload && systemctl enable voice_practice && systemctl restart voice_practice"

echo ""
echo "=== 部署完成！==="
echo "HTTP 访问: http://$SERVER"
echo "检查状态: ssh -p $DEPLOY_PORT $DEPLOY_USER@$SERVER 'systemctl status voice_practice'"
echo "查看日志: ssh -p $DEPLOY_PORT $DEPLOY_USER@$SERVER 'journalctl -u voice_practice -f'"
