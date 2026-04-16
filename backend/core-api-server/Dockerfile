# 1단계: 빌드 환경 (JDK 21)
FROM eclipse-temurin:21-jdk-alpine AS builder
WORKDIR /build

# Gradle 설정 파일 복사
COPY gradlew .
COPY gradle gradle
COPY build.gradle settings.gradle ./
COPY src src

# 윈도우에서 작성된 스크립트의 줄바꿈 오류 방지 및 권한 부여 후 빌드
RUN sed -i 's/\r$//' gradlew
RUN chmod +x ./gradlew
RUN ./gradlew bootJar -x test

# 2단계: 실행 환경 (JRE 21 - 가볍게 유지)
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

# 타임존 설정 (한국 시간)
RUN apk add --no-cache tzdata && \
    cp /usr/share/zoneinfo/Asia/Seoul /etc/localtime && \
    echo "Asia/Seoul" > /etc/timezone

# 빌드된 jar 파일 복사
COPY --from=builder /build/build/libs/*SNAPSHOT.jar app.jar

# 컨테이너 실행 시 jar 파일 구동
EXPOSE 8081
ENTRYPOINT ["java", "-jar", "app.jar"]
