# 📘 테세우스 (Theseus)

💡 **“자연어를 실행으로 바꾸는 AI Agent 개발 지원 시스템”**

테세우스는 사용자의 자연어 지시를 기반으로
프로젝트에 맞는 실행 계획을 수립하고,
필요한 Tool을 생성 및 실행하며,
분석과 검증을 통해 작업을 자동화하는 AI Agent 플랫폼입니다.

단순 코드 생성을 넘어
**실제 실행 가능한 작업 단위로 변환하고, 반복 작업을 줄이며 개발 생산성을 향상시키는 것**을 목표로 합니다.

---

# 🚀 주요 기능

## 🧠 자연어 기반 작업 해석

사용자의 요청을 단순 실행하지 않고
프로젝트 문맥을 기반으로 **실행 가능한 작업 단위로 변환**

* Instruction Parsing
* Context-aware Task Understanding

---

## ⚙️ 실행 계획 수립 (Planning)

작업 수행을 위한 **선행 작업 분석 및 실행 순서 자동 구성**

* 작업 의존성 분석 (A → B → C 구조)
* 실행 가능한 Workflow 생성

---

## 🔍 실행 계획 검증 (Review)

생성된 계획을 검증하고, 잘못된 흐름을 수정

* 실행 순서 검증
* 사용자 피드백 기반 수정
* 검증된 실행 계획 확보

---

## 🛠️ 프로젝트 전용 Tool 생성

복잡한 작업을 **재사용 가능한 Tool로 변환**

* 반복 작업 자동화
* CLI / API / Script 형태 Tool 생성
* 실행 가능 여부 검증

---

## 🔐 권한 기반 Tool 제어

사용자 권한에 따라 Tool 사용을 제한하고,
이중 검증 구조로 안전성 확보

* Soft Control (AI 단계 제한)
* Hard Control (Backend 검증)

---

## 📊 분석 기반 개선 지원

실행 결과를 분석하여 개선 방향을 제안

* 로그 기반 문제 탐지
* 성능 개선 Tool 생성
* 자동화된 개선 루프

---

# 🏗️ 시스템 아키텍처

```
User
↓
AI Agent (Planning / Review)
↓
Tool Orchestration
↓
Execution Layer
↓
| Backend Services | System Environment |
```

---

# ⚙️ 기술 스택

## 🖥️ Frontend

- React, TypeScript, Vite
- Zustand (상태 관리)
- React Query (서버 상태 관리)
- Tailwind CSS (UI 스타일링)

---

## 🖥️ Backend

* Java, Spring Boot
* FastAPI (AI Server)

---

## 🤖 AI / Agent

* LLM 기반 Agent (Planning / Review 구조)
* Tool Orchestration Framework

---

## 📡 데이터 & 시스템

* MySQL / Redis
* 로그 기반 분석 시스템

---

## 🌐 Infra

* Docker / Docker Compose
* Nginx
* Jenkins (CI/CD)
* AWS EC2

---

## 🔒 보안

* 권한 기반 Tool 접근 제어
* 폐쇄망(On-Premise) 환경 대응
* 로컬 LLM 적용 가능

---

# 🔄 실행 흐름 (핵심)

```
자연어 요청
↓
Planning (계획 수립)
↓
Review (검증 및 수정)
↓
Tool 생성 및 실행
↓
분석 및 개선
```

---

# 📦 프로젝트 구조 (예시)

```
backend/
  ├── api-gateway
  ├── agent-server
  ├── tool-engine
  └── execution-service

infra/
nginx/
frontend/
```

---

# 🎯 서비스 목표

* 자연어 기반 개발 자동화
* 반복 작업 제거 및 생산성 향상
* 비전공자도 활용 가능한 개발 환경 제공
* 폐쇄망 환경에서도 동작 가능한 AI Agent 구현

---

# 🧪 검증 전략

기존 프로젝트(싸피증권)를 기반으로
실제 서비스 환경에서 Tool 생성 및 성능 개선 검증

* 서버 병목 감지 및 개선 Tool
* 지연 시간 분석 및 최적화 Tool
* 실시간 운영 환경 적용 테스트

---

# 🔥 차별점

* 단순 코드 생성이 아닌 실행 가능한 Tool 생성
* Planning + Review 기반 검증된 실행 구조
* 권한 기반 이중 검증으로 안전성 확보
* 폐쇄망에서도 동작 가능한 AI Agent

---

# 🏁 한 줄 소개

💡 **“한 번 만들면, 다음부터는 한 줄로 실행하는 AI Agent 시스템”**
