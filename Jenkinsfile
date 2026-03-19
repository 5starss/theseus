pipeline {
    agent any

    environment {
        COMPOSE_DIR    = "docker-compose-prod"
        SERVER_COMPOSE = "docker-compose-server.yml"
        WEB_COMPOSE    = "docker-compose-web.yml"
    }

    stages {
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
                    // contains() 오탐 방지를 위해 경로 구분자('/')를 포함해 매칭
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
        // PREPARE KEYS (Build 전, 변경된 서비스가 있을 때만 실행)
        // — Jenkins 자격증명에서 JWT PEM 파일을 src/main/resources/keys/ 에 주입
        // ════════════════════════════════════════════════════════════
        stage('Prepare Keys') {
            when {
                expression { env.CHANGED_CORE_API_SERVER == 'true' || env.CHANGED_API_GATEWAY == 'true' }
            }
            steps {
                echo '🔑 [Keys] Injecting JWT key files...'
                withCredentials([
                    file(credentialsId: 'jwt-public-pem',  variable: 'JWT_PUBLIC_PEM'),
                    file(credentialsId: 'jwt-private-pem', variable: 'JWT_PRIVATE_PEM')
                ]) {
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
        // — 변경된 서비스만 빌드
        // ════════════════════════════════════════════════════════════
        stage('Build: api-gateway') {
            when { expression { env.CHANGED_API_GATEWAY == 'true' } }
            steps {
                echo '☕ [Build] Building api-gateway...'
                sh 'cd backend/api-gateway && chmod +x ./gradlew && ./gradlew clean build'
            }
        }

        stage('Build: core-api-server') {
            when { expression { env.CHANGED_CORE_API_SERVER == 'true' } }
            steps {
                echo '☕ [Build] Building core-api-server...'
                sh 'cd backend/core-api-server && chmod +x ./gradlew && ./gradlew clean build'
            }
        }

        stage('Build: matcher-server') {
            when { expression { env.CHANGED_MATCHER_SERVER == 'true' } }
            steps {
                echo '☕ [Build] Building matcher-server...'
                sh 'cd backend/matcher-server && chmod +x ./gradlew && ./gradlew clean build'
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
        // — 변경된 Java 서비스만 테스트
        // ════════════════════════════════════════════════════════════
        // Build 스테이지에서 이미 테스트까지 실행됨 (gradlew clean build)
        // 별도 Test 스테이지는 테스트 결과 리포트 수집용으로만 사용
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
        // DEPLOY (Rule B 전용: dev 브랜치 Merge 완료 후에만 실행)
        // — MR 단계(gitlabMergeRequestIid 존재 시)에는 절대 배포하지 않음
        // — 변경된 서비스만 단독 갱신 (docker-compose down 금지)
        // ════════════════════════════════════════════════════════════
        stage('Deploy') {
            when {
                allOf {
                    branch 'dev'
                    // MR 빌드가 아닌 경우에만 배포 (MR 시에는 Build/Test만 수행)
                    expression { !env.gitlabMergeRequestIid && !env.CHANGE_ID }
                }
            }
            steps {
                echo '🚀 [CD] Deploying updated services...'
                withCredentials([file(credentialsId: 'env-file', variable: 'SECURE_ENV')]) {
                    sh "cp \$SECURE_ENV ${COMPOSE_DIR}/.env"
                    script {
                        // script {} 내에서는 env.* 로 명시적 접근
                        def composeDir    = env.COMPOSE_DIR
                        def serverCompose = env.SERVER_COMPOSE
                        def webCompose    = env.WEB_COMPOSE
                        def deployed      = false

                        // 각 서비스 개별 배포 — 변경된 서비스만, 다른 서비스는 중단 없음
                        if (env.CHANGED_API_GATEWAY == 'true') {
                            echo '  → Deploying api-gateway'
                            sh "docker-compose -f ${composeDir}/${serverCompose} up -d --no-deps --build api-gateway"
                            deployed = true
                        }
                        if (env.CHANGED_CORE_API_SERVER == 'true') {
                            echo '  → Deploying core-api-server'
                            sh "docker-compose -f ${composeDir}/${serverCompose} up -d --no-deps --build core-api-server"
                            deployed = true
                        }
                        if (env.CHANGED_MATCHER_SERVER == 'true') {
                            echo '  → Deploying matcher-server'
                            sh "docker-compose -f ${composeDir}/${serverCompose} up -d --no-deps --build matcher-server"
                            deployed = true
                        }
                        if (env.CHANGED_MARKET_SERVER == 'true') {
                            echo '  → Deploying market-server'
                            sh "docker-compose -f ${composeDir}/${serverCompose} up -d --no-deps --build market-server"
                            deployed = true
                        }
                        if (env.CHANGED_AI_SERVER == 'true') {
                            echo '  → Deploying ai-server'
                            sh "docker-compose -f ${composeDir}/${serverCompose} up -d --no-deps --build ai-server"
                            deployed = true
                        }
                        if (env.CHANGED_NGINX == 'true') {
                            echo '  → Deploying nginx'
                            sh "docker-compose -f ${composeDir}/${webCompose} up -d --no-deps --build nginx"
                            deployed = true
                        }

                        if (deployed) {
                            echo '📦 Deployment Status:'
                            sh "docker-compose -f ${composeDir}/${serverCompose} ps || true"
                            sh "docker-compose -f ${composeDir}/${webCompose} ps || true"
                        } else {
                            echo '⏭️ No services changed. Skipping deployment.'
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            echo '🧹 [Cleanup] Post-build cleanup...'
            // 보안: 복사한 .env 및 PEM 키 파일 반드시 삭제
            sh "rm -f ${COMPOSE_DIR}/.env || true"
            sh '''
                rm -f backend/core-api-server/src/main/resources/keys/public_key.pem  || true
                rm -f backend/core-api-server/src/main/resources/keys/private_key.pem || true
                rm -f backend/api-gateway/src/main/resources/keys/public_key.pem      || true
            '''
            sh "docker image prune -f || true"
        }
        success { echo '✅ [SUCCESS] CI/CD Pipeline completed!' }
        failure { echo '❌ [FAILURE] Pipeline failed. Check console output.' }
    }
}
