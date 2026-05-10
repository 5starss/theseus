# ─────────────────────────────────────────────────────────────
# 1. Build Stage
# Node 환경에서 패키지를 설치하고 React+Vite 앱을 정적 파일로 빌드합니다.
# ─────────────────────────────────────────────────────────────
FROM node:24-alpine AS build

WORKDIR /app

# 캐시 효율을 위해 package.json과 package-lock.json 복사
COPY package.json package-lock.json ./
# 의존성 설치 (버전 고정을 위해 npm ci 사용 권장)
RUN npm ci

# 소스 코드 전체 복사 후, Vite 빌드 실행
COPY . .
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build


# ─────────────────────────────────────────────────────────────
# 2. Production Stage
# 가벼운 Nginx 이미지를 사용하여 빌드된 정적 리소스를 제공합니다.
# ─────────────────────────────────────────────────────────────
FROM nginx:alpine

# 프로젝트 루트에서 생성한 사용자 정의 nginx.conf 복사 (SPA 라우팅 지원)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Build Stage의 최종 결과물(dist)을 Nginx 웹 서버의 루트 폴더로 가져옴
COPY --from=build /app/dist /usr/share/nginx/html

# 외부에서 접근 가능한 80포트 개방 지정
EXPOSE 80

# Nginx 포그라운드 실행
CMD ["nginx", "-g", "daemon off;"]
