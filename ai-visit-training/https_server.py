#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTPS 启动脚本 - 为语音对练系统提供 HTTPS 支持
使用自签名证书，解决浏览器麦克风权限问题
"""
import os, sys, subprocess, time

PUBLIC_HOST = os.getenv('PUBLIC_HOST', 'localhost').strip() or 'localhost'

# 生成自签名证书
CERT_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_KEY = os.path.join(CERT_DIR, 'server.key')
CERT_CRT = os.path.join(CERT_DIR, 'server.crt')

if not (os.path.exists(CERT_KEY) and os.path.exists(CERT_CRT)):
    print("[SSL] Generating self-signed certificate...")
    ret = subprocess.run([
        'openssl', 'req', '-x509', '-nodes', '-days', '3650',
        '-newkey', 'rsa:2048',
        '-keyout', CERT_KEY,
        '-out', CERT_CRT,
        '-subj', f'/CN={PUBLIC_HOST}/O=VoicePractice/C=CN'
    ], capture_output=True, text=True)
    if ret.returncode == 0:
        print("[SSL] Certificate generated successfully!")
    else:
        print(f"[SSL] Failed to generate cert: {ret.stderr}")
        # 尝试用 python 生成
        try:
            import ssl
            print("[SSL] Trying Python SSL generation...")
            from OpenSSL import crypto
            k = crypto.PKey()
            k.generate_key(crypto.TYPE_RSA, 2048)
            c = crypto.X509()
            c.get_subject().CN = PUBLIC_HOST
            c.set_issuer(c.get_subject())
            c.set_serial_number(1000)
            gmt_before = b'20240101000000Z'
            gmt_after = b'20350101000000Z'
            c.set_notBefore(gmt_before)
            c.set_notAfter(gmt_after)
            c.set_pubkey(k)
            c.sign(k, 'sha256')
            with open(CERT_CRT, 'wb') as f:
                f.dump_certificate(crypto.FILETYPE_PEM, c)
            with open(CERT_KEY, 'wb') as f:
                f.dump_privatekey(crypto.FILETYPE_PEM, k)
            print("[SSL] Certificate generated via pyOpenSSL!")
        except Exception as e2:
            print(f"[SSL] All methods failed: {e2}")
            sys.exit(1)

print("=" * 55)
print("  Voice Practice - HTTPS Server")
print("=" * 55)
print(f"  HTTPS URL: https://{PUBLIC_HOST}:443")
print(f"  HTTP URL:  http://{PUBLIC_HOST}:5000  -> redirect to 443")
print("")
print("  NOTE: Browser will show certificate warning.")
print(f"  Click 'Advanced' -> 'Proceed to {PUBLIC_HOST} (unsafe)'")
print("=" * 55)

# 用 ssl 模块启动 Flask
from app import app
import ssl

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(CERT_CRT, CERT_KEY)

# HTTP 重定向到 HTTPS（在后台线程）
def http_redirect():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', 5000))
    s.listen(5)
    while True:
        conn, addr = s.accept()
        data = conn.recv(1024)
        host_header = ''
        for line in data.split(b'\r\n'):
            if line.startswith(b'Host:'):
                host_header = line.decode().split(':')[1].strip()
                break
        redirect = (
            b"HTTP/1.1 301 Moved Permanently\r\n"
            + f"Location: https://{PUBLIC_HOST}:443\r\n".encode()
            + b"Content-Length: 0\r\n"
            + b"\r\n"
        )
        conn.sendall(redirect)
        conn.close()

import threading
t = threading.Thread(target=http_redirect, daemon=True)
t.start()

# 启动 HTTPS 服务
app.run(host='0.0.0.0', port=443, ssl_context=(CERT_CRT, CERT_KEY), debug=False)
