# Git Convention

## MR Title Convention

형식:

```text
JIRA 번호 [label]: 작업 내용
```

예시:

```text
S14P11A503-123 [feat]: 회원가입 API 구현
S14P11A503-123 [fix]: 홈 화면 네브바 수정
```

## Branch Convention

형식:

```text
stock/<type>/<JIRA 번호>/<branch-name>
```

예시:

```text
stock/feat/S14P21A308-123/initial-user-info
stock/fix/S14P31A308-358/jenkins-gitlab-connection
```

## Commit Convention

형식:

```text
JIRA 번호 [label]: 작업 내용
```

예시:

```text
S14P11A503-123 [chore]: 스프링 부트 프로젝트 초기 세팅
```

커밋 유형:

| 타입 | 의미 |
| --- | --- |
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서 수정 |
| `refactor` | 코드 리팩토링 |
| `test` | 테스트 코드 추가 및 리팩토링 |
| `chore` | 패키지 매니저 수정, 설정 변경, 기타 작업 |

추가로 백엔드와 프론트엔드 작업 구분이 필요하면 작업 내용에 명시합니다.

## MR Template Guide

```md
## 어떤 이유로 MR를 하셨나요?

* [ ] feature 병합
* [ ] 버그 수정
* [ ] 코드 개선
* [ ] 기타

## 세부 내용

* 세부 내용1
* 세부 내용2
```

## Issue Management

GitLab에서 이슈 관리는 따로 하지 않고, Jira 스토리 설명란에 관련 내용을 작성합니다.
