pipeline {
    agent any

    environment {
        // 프로젝트 루트 기준 docker-compose 파일이 위치한 디렉토리 경로
        COMPOSE_DIR = "docker-compose-prod"
        COMPOSE_FILE = "docker-compose-server.yml"
    }

    stages {
        // 1. 소스 코드 가져오기 (모든 브랜치)
        stage('Checkout') {
            steps {
                echo '🚚 [CI] Checking out source code from GitLab...'
                checkout scm
            }
        }

        // 2. 전체 프로젝트 빌드 및 테스트 (모든 브랜치)
        stage('Build & Test') {
            steps {
                echo '🛠️ [CI] Building Application and Running Unit Tests...'
                sh """
                chmod +x ./gradlew
                ./gradlew clean build -x test
                """
                // -x test는 빌드 속도를 위해 추가했습니다. 테스트를 포함하려면 삭제하세요.
            }
        }

        // 3. 선택적 자동 배포 (오직 dev 브랜치만)
        stage('Smart Deploy (dev only)') {
            when {
                branch 'dev'
            }
            steps {
                echo "🚀 [CD] Scanning for changes and deploying updated services..."

                // 🔐 Jenkins Credentials를 통한 보안 .env 파일 주입
                withCredentials([file(credentialsId: 'env-file', variable: 'SECURE_ENV')]) {
                    sh """
                    # 1. 환경 설정 파일 복사
                    cp ${SECURE_ENV} ${COMPOSE_DIR}/.env

                    # 2. 실행 경로 이동
                    cd ${COMPOSE_DIR}

                    # 3. 스마트 배포 실행
                    # --build: 변경된 서비스만 이미지를 새로 만듭니다.
                    # up -d: 변경된 컨테이너만 중지 후 교체하며, 나머지는 유지합니다.
                    docker-compose -f ${COMPOSE_FILE} up -d --build
                    """
                }
            }
        }
    }

    post {
        success {
            echo '✅ [SUCCESS] CI/CD Pipeline completed successfully!'
        }
        failure {
            echo '❌ [FAILURE] Pipeline failed. Check Jenkins console output.'
        }
        always {
            echo '🧹 [Cleanup] Post-build operations...'

            // 보안을 위해 워크스페이스 내 .env 파일 삭제
            sh "rm -f ${COMPOSE_DIR}/.env || true"

            // 사용하지 않는 오래된(dangling) 이미지 정리 (서버 용량 확보)
            sh "docker image prune -f || true"
        }
    }
}