# Theseus Test Package

이 폴더는 Theseus VSCode Extension을 테스트용으로 설치하고, 함께 포함된
`theseus-runner.exe`로 로컬에서 실행하기 위한 배포 패키지입니다.

## Theseus 소개

Theseus는 프로젝트 코드와 실행 환경을 이해하고, 질문 답변, 코드 조사, 계획
수립, 커스텀 툴 생성, 승인 기반 실행을 돕는 AI agent runtime입니다.

이 테스트 패키지는 핵심 Python source tree를 직접 전달하지 않고, packaged
runner binary를 Extension에 연결합니다. 설치가 끝나면 IDE 사이드바에서
Theseus를 실행할 수 있습니다.

## 폴더 구성

```text
Theseus-TestPackage/
  README.md
  Install-Theseus-TestPackage.cmd
  scripts/
    install-test-package.ps1
  theseus-vscode-0.0.1.vsix
  theseus-runner/
    theseus-runner.exe
    _internal/
```

## 빠른 실행

1. `Install-Theseus-TestPackage.cmd`를 더블클릭합니다.
2. workspace/project path를 입력합니다. 그냥 Enter를 누르면 이 패키지 폴더가
   workspace로 열립니다.
3. IDE가 열리면 Theseus 사이드바를 엽니다.
4. Command Palette 또는 Theseus 사이드바에서 `Theseus: Start Agent`를
   실행합니다.

설치기는 다음 작업을 자동으로 처리합니다.

- VSIX 설치
- `theseus.runtimeMode=bundled-runner` 설정
- `theseus.runnerPath`를 이 폴더의 `theseus-runner.exe`로 설정
- `theseus.workspacePath` 설정
- 선택한 workspace를 IDE로 열기

## 명령으로 실행

자동 감지가 맞지 않으면 명령 프롬프트에서 설치 대상을 명시할 수 있습니다.

```cmd
Install-Theseus-TestPackage.cmd -Ide vscode
Install-Theseus-TestPackage.cmd -Ide antigravity
```

workspace를 미리 지정하려면 다음처럼 실행합니다.

```cmd
Install-Theseus-TestPackage.cmd -WorkspacePath C:\path\to\your\project
```

IDE CLI를 자동으로 찾지 못하면 `-Code`로 직접 지정합니다.

```cmd
Install-Theseus-TestPackage.cmd -Ide antigravity -Code "C:\path\to\antigravity.cmd"
```

## 실행 전 확인

- Windows 환경을 기준으로 합니다.
- VS Code 또는 Antigravity CLI가 PATH에 있어야 합니다. 자동 감지가 실패하면
  `-Code`를 사용합니다.
- LLM provider API key가 필요한 기능은 사용자 환경의 IDE 설정, 시스템 환경
  변수, 또는 runner가 읽을 수 있는 `.env` 설정이 필요합니다.
- 이 패키지는 테스트 배포용입니다. binary 역공학 방지, 서명, 라이선스,
  SBOM 정리는 별도 배포 단계에서 확인해야 합니다.
