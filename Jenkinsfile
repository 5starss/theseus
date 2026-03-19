pipeline {
    agent any

    environment {
        COMPOSE_DIR = "docker-compose-prod"
        COMPOSE_FILE = "docker-compose-server.yml"
        // 빌드 검증을 위한 서비스 목록
        SERVICES = "api-gateway core-api-server matcher-server market-server ai-server"
    }

    stages {
        stage('Checkout') {
            steps {
                echo '🚚 [CI] Checking out source code...'
                checkout scm
            }
        }

        stage('Validate & Prep') {
            steps {
                echo '🔍 [CI] Validating structure and preparing builds...'
                script {
                    def serviceList = env.SERVICES.split(' ')
                    serviceList.each { service ->
                        sh """
                        echo "--- Checking ${service} ---"
                        if [ -f "backend/${service}/gradlew" ]; then
                            echo "☕ Java(Gradle) detected. Pre-building JAR for ${service}..."
                            cd backend/${service} && chmod +x ./gradlew && ./gradlew clean build -x test
                        elif [ -f "backend/${service}/requirements.txt" ]; then
                            echo "🐍 Python(AI) detected. Docker will handle pip install."
                        elif [ -f "backend/${service}/go.mod" ]; then
                            echo "🐹 Go(Market) detected. Docker will handle go build."
                        fi
                        """
                    }
                }
            }
        }

        stage('Smart Deploy (dev only)') {
            when { branch 'dev' }
            steps {
                echo '🚀 [CD] Deploying updated services with docker-compose...'
                withCredentials([file(credentialsId: 'env-file', variable: 'SECURE_ENV')]) {
                    // 쌍따옴표(""")를 써서 젠킨스 변수와 쉘 변수를 모두 안전하게 처리
                    sh """
                    echo "📦 Copying secure .env file..."
                    cp ${SECURE_ENV} ${COMPOSE_DIR}/.env

                    cd ${COMPOSE_DIR}

                    echo "🐳 Running docker-compose up -d --build..."
                    # --build 옵션이 있으면 Dockerfile의 내용(Python, Go 빌드 포함)이 실행됩니다.
                    docker-compose -f ${COMPOSE_FILE} up -d --build

                    echo "📦 Deployment Status:"
                    docker-compose -f ${COMPOSE_FILE} ps
                    """
                }
            }
        }
    }
    post {
        success { echo '✅ [SUCCESS] CI/CD Pipeline completed!' }
        failure { echo '❌ [FAILURE] Pipeline failed. Check console output.' }
        always {
            echo '🧹 [Cleanup] Post-build operations...'
            sh "docker image prune -f || true"
        }
    }
}