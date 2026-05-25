pipeline {
    agent any

    options {
        gitLabConnection('SSAFY-GitLab')
    }

    environment {
        COMPOSE_DIR    = "docker-compose-prod"
        SERVER_COMPOSE = "docker-compose-server.yml"
        WEB_COMPOSE    = "docker-compose-web.yml"
    }

    stages {
        stage('Report GitLab Pending') {
            steps {
                script {
                    updateGitlabCommitStatus name: 'jenkins-ci', state: 'pending'
                }
            }
        }

        stage('Checkout') {
            steps {
                echo '🚚 [CI] Checking out source code...'
                checkout scm
            }
        }

        // ────────────────────────────────────────────────────────────
        // 변경 감지: Git diff 분석 후 서비스별 변경 여부를 환경변수로 설정
        // ────────────────────────────────────────────────────────────
        stage('Detect Changes') {
            steps {
                script {
                    // Shallow Clone 해제 — MR Merge Base 탐색에 필요
                    sh "git fetch --unshallow || true"

                    def changedFiles = ""
                    try {
                        if (env.GIT_PREVIOUS_COMMIT) {
                            // [Case 1: Push Mode] 연속 빌드 — 구간 비교
                            echo "🔍 [Push Mode] Comparing: ${env.GIT_PREVIOUS_COMMIT}...HEAD"
                            changedFiles = sh(script: "git diff --name-only ${env.GIT_PREVIOUS_COMMIT} HEAD", returnStdout: true).trim()

                        } else if (env.gitlabMergeRequestIid || env.CHANGE_ID) {
                            // [Case 2: MR Mode] MR 생성/업데이트 — Target 브랜치와 비교
                            def targetBranch = env.gitlabTargetBranch ?: env.CHANGE_TARGET
                            echo "🔍 [MR Mode] Comparing against origin/${targetBranch}"
                            sh "git fetch origin ${targetBranch} || true"
                            changedFiles = sh(script: "git diff --name-only origin/${targetBranch}...HEAD", returnStdout: true).trim()

                        } else {
                            // [Case 3: First Build] 히스토리 없음 — 직전 커밋과 비교
                            echo "⚠️ First build. Comparing HEAD~1...HEAD"
                            changedFiles = sh(script: "git diff --name-only HEAD~1 HEAD", returnStdout: true).trim()
                        }
                    } catch (Exception e) {
                        echo "⚠️ Diff check failed. Building ALL modules as fallback."
                        changedFiles = "nginx/ frontend/ backend/ai-server/ backend/api-gateway/ backend/core-api-server/ backend/market-server/ backend/matcher-server/"
                    }

                    echo "📝 Changed Files:\n${changedFiles}"

                    // 서비스별 변경 여부를 환경변수로 저장
                    env.CHANGED_API_GATEWAY     = changedFiles.contains('backend/api-gateway/')     ? 'true' : 'false'
                    env.CHANGED_CORE_API_SERVER = changedFiles.contains('backend/core-api-server/') ? 'true' : 'false'
                    env.CHANGED_MATCHER_SERVER  = changedFiles.contains('backend/matcher-server/')  ? 'true' : 'false'
                    env.CHANGED_MARKET_SERVER   = changedFiles.contains('backend/market-server/')   ? 'true' : 'false'
                    env.CHANGED_AI_SERVER       = changedFiles.contains('backend/ai-server/')       ? 'true' : 'false'
                    env.CHANGED_NGINX           = (changedFiles.contains('frontend/') || changedFiles.contains('nginx/')) ? 'true' : 'false'
                }
            }
        }

        // ════════════════════════════════════════════════════════════
        // PREPARE (Build 전 준비: .env + JWT PEM 파일 주입)
        // — 무조건 실행되도록 when 블록 제거
        // — Windows 줄바꿈(\r) 제거 로직 추가
        // ════════════════════════════════════════════════════════════
        stage('Prepare') {
            steps {
                echo '⚙️ [Prepare] Injecting .env and JWT key files before build...'
                withCredentials([
                    file(credentialsId: 'env-file',        variable: 'SECURE_ENV'),
                    file(credentialsId: 'jwt-public-pem',  variable: 'JWT_PUBLIC_PEM'),
                    file(credentialsId: 'jwt-private-pem', variable: 'JWT_PRIVATE_PEM')
                ]) {
                    // 1. .env 복사
                    sh "cp \$SECURE_ENV .env"

                    // 2. Windows식 줄바꿈(CRLF)을 Linux식(LF)으로 변환하여 오류 방지
                    sh "sed -i 's/\\r\$//' .env"

                    // 3. 변환된 .env를 Deploy 단계에서 사용할 위치로 복사
                    sh "cp .env ${COMPOSE_DIR}/.env"

                    // 4. 필요한 서비스에만 JWT 키 복사
                    script {
                        if (env.CHANGED_CORE_API_SERVER == 'true') {
                            sh '''
                                mkdir -p backend/core-api-server/src/main/resources/keys
                                cp $JWT_PUBLIC_PEM  backend/core-api-server/src/main/resources/keys/public_key.pem
                                cp $JWT_PRIVATE_PEM backend/core-api-server/src/main/resources/keys/private_key.pem
                            '''
                        }
                        if (env.CHANGED_API_GATEWAY == 'true') {
                            sh '''
                                mkdir -p backend/api-gateway/src/main/resources/keys
                                cp $JWT_PUBLIC_PEM backend/api-gateway/src/main/resources/keys/public_key.pem
                            '''
                        }
                    }
                }
            }
        }

        // ════════════════════════════════════════════════════════════
        // BUILD (Rule A + Rule B 공통 실행)
        // ════════════════════════════════════════════════════════════
        stage('Build: api-gateway') {
            when { expression { env.CHANGED_API_GATEWAY == 'true' } }
            steps {
                echo '☕ [Build] Building api-gateway...'
                sh '''
                    set -a && . ${WORKSPACE}/.env && set +a
                    cd backend/api-gateway && chmod +x ./gradlew && ./gradlew clean build
                '''
            }
        }

        stage('Build: core-api-server') {
            when { expression { env.CHANGED_CORE_API_SERVER == 'true' } }
            steps {
                echo '☕ [Build] Building core-api-server...'
                sh '''
                    set -a && . ${WORKSPACE}/.env && set +a
                    cd backend/core-api-server && chmod +x ./gradlew && ./gradlew clean build
                '''
            }
        }

        stage('Build: matcher-server') {
            when { expression { env.CHANGED_MATCHER_SERVER == 'true' } }
            steps {
                echo '☕ [Build] Building matcher-server...'
                sh '''
                    set -a && . ${WORKSPACE}/.env && set +a
                    cd backend/matcher-server && chmod +x ./gradlew && ./gradlew clean build
                '''
            }
        }

        stage('Build: market-server') {
            when { expression { env.CHANGED_MARKET_SERVER == 'true' } }
            steps {
                echo '🐹 [Build] market-server — go build is handled by Docker.'
            }
        }

        stage('Build: ai-server') {
            when { expression { env.CHANGED_AI_SERVER == 'true' } }
            steps {
                echo '🐍 [Build] ai-server — pip install is handled by Docker.'
            }
        }

        stage('Build: nginx') {
            when { expression { env.CHANGED_NGINX == 'true' } }
            steps {
                echo '🌐 [Build] nginx/frontend — frontend build is handled by Docker.'
            }
        }

        // ════════════════════════════════════════════════════════════
        // TEST (Rule A + Rule B 공통 실행)
        // ════════════════════════════════════════════════════════════
        stage('Test: api-gateway') {
            when { expression { env.CHANGED_API_GATEWAY == 'true' } }
            steps {
                echo '🧪 [Test] Collecting test results for api-gateway...'
                junit(testResults: 'backend/api-gateway/build/test-results/**/*.xml', allowEmptyResults: true)
            }
        }

        stage('Test: core-api-server') {
            when { expression { env.CHANGED_CORE_API_SERVER == 'true' } }
            steps {
                echo '🧪 [Test] Collecting test results for core-api-server...'
                junit(testResults: 'backend/core-api-server/build/test-results/**/*.xml', allowEmptyResults: true)
            }
        }

        stage('Test: matcher-server') {
            when { expression { env.CHANGED_MATCHER_SERVER == 'true' } }
            steps {
                echo '🧪 [Test] Collecting test results for matcher-server...'
                junit(testResults: 'backend/matcher-server/build/test-results/**/*.xml', allowEmptyResults: true)
            }
        }

        // ════════════════════════════════════════════════════════════
        // DEPLOY
        // ════════════════════════════════════════════════════════════
        stage('Deploy') {
            when {
                allOf {
                    branch 'stock_dev'
                    expression { !env.gitlabMergeRequestIid && !env.CHANGE_ID }
                }
            }
            steps {
                echo '🚀 [CD] Deploying updated services...'
                script {
                    def composeDir    = env.COMPOSE_DIR
                    def serverCompose = env.SERVER_COMPOSE
                    def webCompose    = env.WEB_COMPOSE
                    def deployed      = false

                    sh """
                        set -e
                        echo '=== Docker Environment Debug ==='
                        whoami
                        pwd
                        docker version
                        docker context ls
                        docker network ls
                        ls -al
                        ls -al ${composeDir}
                    """

                    sh """
                        set -e
                        echo '=== Ensure stock-network exists ==='
                        docker network inspect stock-network >/dev/null 2>&1 || docker network create stock-network
                        docker network ls | grep stock-network
                    """

                    sh """
                        set -e
                        echo '=== Compose Config Check: ${serverCompose} ==='
                        cd ${composeDir}
                        docker compose -f ${serverCompose} config | grep -A5 -B5 stock-network || true
                        echo '=== Compose Config Check: ${webCompose} ==='
                        docker compose -f ${webCompose} config | grep -A5 -B5 stock-network || true
                    """

                    if (env.CHANGED_API_GATEWAY == 'true') {
                        echo '  → Deploying api-gateway'
                        sh """
                            set -e
                            echo '=== Deploy api-gateway ==='
                            cd ${composeDir}
                            docker compose -f ${serverCompose} up -d --no-deps --build api-gateway
                        """
                        deployed = true
                    }
                    if (env.CHANGED_CORE_API_SERVER == 'true') {
                        echo '  → Deploying core-api-server'
                        sh """
                            set -e
                            echo '=== Deploy core-api-server ==='
                            cd ${composeDir}
                            docker compose -f ${serverCompose} up -d --no-deps --build core-api-server
                        """
                        deployed = true
                    }
                    if (env.CHANGED_MATCHER_SERVER == 'true') {
                        echo '  → Deploying matcher-server'
                        sh """
                            set -e
                            echo '=== Deploy matcher-server ==='
                            cd ${composeDir}
                            docker compose -f ${serverCompose} up -d --no-deps --build matcher-server
                        """
                        deployed = true
                    }
                    if (env.CHANGED_MARKET_SERVER == 'true') {
                        echo '  → Deploying market-server'
                        sh """
                            set -e
                            echo '=== Deploy market-server ==='
                            cd ${composeDir}
                            docker compose -f ${serverCompose} up -d --no-deps --build market-server
                        """
                        deployed = true
                    }
                    if (env.CHANGED_AI_SERVER == 'true') {
                        echo '  → Deploying ai-server'
                        sh """
                            set -e
                            echo '=== Deploy ai-server ==='
                            cd ${composeDir}
                            docker compose -f ${serverCompose} up -d --no-deps --build ai-server
                        """
                        deployed = true
                    }
                    if (env.CHANGED_NGINX == 'true') {
                        echo '  → Deploying nginx'
                        sh """
                            set -e
                            echo '=== Deploy nginx ==='
                            cd ${composeDir}
                            docker compose -f ${webCompose} up -d --no-deps --build nginx
                        """
                        deployed = true
                    }

                    if (deployed) {
                        echo '📦 Deployment Status:'
                        sh "cd ${composeDir} && docker compose -f ${serverCompose} ps || true"
                        sh "cd ${composeDir} && docker compose -f ${webCompose} ps || true"
                    } else {
                        echo '⏭️ No services changed. Skipping deployment.'
                    }
                }
            }
        }
    }

    post {
        always {
            echo '🧹 [Cleanup] Post-build cleanup...'
            // 작업이 끝난 후 보안을 위해 .env 및 key 파일들을 모두 삭제합니다.
            sh "rm -f .env ${COMPOSE_DIR}/.env || true"
            sh '''
                rm -f backend/core-api-server/src/main/resources/keys/public_key.pem  || true
                rm -f backend/core-api-server/src/main/resources/keys/private_key.pem || true
                rm -f backend/api-gateway/src/main/resources/keys/public_key.pem      || true
            '''
            sh "docker image prune -f || true"
        }
        success {
            script {
                updateGitlabCommitStatus name: 'jenkins-ci', state: 'success'
            }
            echo '✅ [SUCCESS] CI/CD Pipeline completed!'
        }
        failure {
            script {
                updateGitlabCommitStatus name: 'jenkins-ci', state: 'failed'
            }
            echo '❌ [FAILURE] Pipeline failed. Check console output.'
        }
        aborted {
            script {
                updateGitlabCommitStatus name: 'jenkins-ci', state: 'canceled'
            }
            echo '⚠️ [ABORTED] Pipeline was aborted.'
        }
    }
}
