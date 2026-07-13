FROM node:20-alpine
WORKDIR /app
COPY index.html config.mjs server.mjs ./
ENV PORTAL_HOST=0.0.0.0 PORTAL_PORT=8080
EXPOSE 8080
CMD ["node", "server.mjs"]
