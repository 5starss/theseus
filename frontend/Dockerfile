# 1단계: 빌드 환경
FROM node:24-alpine AS builder
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# 2단계: 실행 환경 (Nginx)
FROM nginx:1.27-alpine

# --- 타임존 설정 추가 (한국 시간) ---
RUN apk add --no-cache tzdata && \
    cp /usr/share/zoneinfo/Asia/Seoul /etc/localtime && \
    echo "Asia/Seoul" > /etc/timezone
# --------------------------------

# 빌드된 정적 파일 복사
COPY --from=builder /app/dist /usr/share/nginx/html

# 커스텀 Nginx 설정 파일 복사
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
