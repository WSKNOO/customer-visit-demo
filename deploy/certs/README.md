Place the private-network TLS files here only on the server:

- `server.crt`: server certificate including any required intermediate chain
- `server.key`: unencrypted private key readable only by the deployment account

Do not commit either file. Prefer a certificate issued by the organization's internal CA. Import that CA into managed client devices so browser microphone access is available without certificate warnings. For temporary offline testing only, an administrator may create a SAN certificate for the server DNS name/IP and distribute its CA through the approved device-management process.
