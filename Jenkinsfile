pipeline {
    agent any

    options {
        gitLabConnection('SSAFY-GitLab')
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        PROD_COMPOSE_FILE = 'infra/docker/prod/docker-compose.prod.yml'
        PROD_ENV_FILE = 'infra/docker/prod/.env'
        PROD_ENV_CREDENTIAL_ID = 'theseus-prod-env'
        FRONTEND_DIR = 'frontend'
        API_SERVER_DIR = 'backend/theseus-api-server'
        CORE_SERVER_DIR = 'backend/theseus-core-server'
        CORE_SERVER_CI_IMAGE = "theseus-core-server-ci:${BUILD_NUMBER}"
        FRONTEND_CI_IMAGE = "theseus-frontend-ci:${BUILD_NUMBER}"
        API_SERVER_CI_IMAGE = "theseus-api-server-ci:${BUILD_NUMBER}"
    }

    stages {
        stage('Initialize GitLab Status') {
            steps {
                updateGitlabCommitStatus(name: 'Jenkins CI/CD', state: 'running')
            }
        }

        stage('Checkout') {
            steps {
                echo '[CI] Checking out source code'
                checkout scm
            }
        }

        stage('Validate Pipeline Context') {
            steps {
                script {
                    def branchName = env.BRANCH_NAME ?: ''
                    def isConventionBranch = branchName ==~ /^(feat|fix|refactor|chore|docs|test|hotfix)\/.+/

                    env.IS_MR_BUILD = (env.CHANGE_ID || env.gitlabMergeRequestIid) ? 'true' : 'false'
                    env.IS_DEPLOY_BRANCH = (env.BRANCH_NAME == 'dev' && env.IS_MR_BUILD != 'true') ? 'true' : 'false'
                    env.IS_CI_BRANCH = (env.IS_MR_BUILD == 'true' || isConventionBranch) ? 'true' : 'false'

                    echo "Branch: ${env.BRANCH_NAME}"
                    echo "MR build: ${env.IS_MR_BUILD}"
                    echo "Convention branch: ${isConventionBranch}"
                    echo "CI branch: ${env.IS_CI_BRANCH}"
                    echo "Deploy branch: ${env.IS_DEPLOY_BRANCH}"
                }

                sh '''
                    set -eu
                    test -f Jenkinsfile
                    test -f "${PROD_COMPOSE_FILE}"
                    git diff --check
                '''
            }
        }

        stage('Detect Changes') {
            when {
                expression { env.IS_CI_BRANCH == 'true' || env.IS_DEPLOY_BRANCH == 'true' }
            }
            steps {
                script {
                    sh 'git fetch --unshallow || true'

                    def changedFiles = ''
                    try {
                        if (env.GIT_PREVIOUS_COMMIT && env.IS_MR_BUILD != 'true') {
                            echo "Detecting changes in push build: ${env.GIT_PREVIOUS_COMMIT}...HEAD"
                            changedFiles = sh(
                                script: "git diff --name-only ${env.GIT_PREVIOUS_COMMIT} HEAD",
                                returnStdout: true
                            ).trim()
                        } else if (env.IS_MR_BUILD == 'true') {
                            def targetBranch = env.gitlabTargetBranch ?: env.CHANGE_TARGET ?: 'dev'
                            echo "Detecting changes in MR build against origin/${targetBranch}"
                            sh "git fetch origin ${targetBranch} || true"
                            changedFiles = sh(
                                script: "git diff --name-only origin/${targetBranch}...HEAD",
                                returnStdout: true
                            ).trim()
                        } else {
                            echo 'Detecting changes in first or manual build: HEAD~1...HEAD'
                            changedFiles = sh(
                                script: 'git diff --name-only HEAD~1 HEAD',
                                returnStdout: true
                            ).trim()
                        }
                    } catch (Exception e) {
                        echo "Change detection failed. Building all modules as fallback. ${e}"
                        changedFiles = [
                            'Jenkinsfile',
                            "${FRONTEND_DIR}/",
                            "${API_SERVER_DIR}/",
                            "${CORE_SERVER_DIR}/",
                            'infra/docker/prod/'
                        ].join('\n')
                    }

                    echo "Changed files:\n${changedFiles}"

                    env.CHANGED_PIPELINE = changedFiles.contains('Jenkinsfile') ? 'true' : 'false'
                    env.CHANGED_FRONTEND = changedFiles.contains("${FRONTEND_DIR}/") ? 'true' : 'false'
                    env.CHANGED_API_SERVER = changedFiles.contains("${API_SERVER_DIR}/") ? 'true' : 'false'
                    env.CHANGED_CORE_API_SERVER = (
                        changedFiles.contains("${CORE_SERVER_DIR}/") ||
                        changedFiles.contains('infra/docker/prod/') ||
                        changedFiles.contains('infra/docker/local/docker-compose.core.yml')
                    ) ? 'true' : 'false'
                    env.CHANGED_INFRA = changedFiles.contains('infra/docker/prod/') ? 'true' : 'false'

                    if (env.CHANGED_PIPELINE == 'true') {
                        env.CHANGED_FRONTEND = 'true'
                        env.CHANGED_API_SERVER = 'true'
                        env.CHANGED_CORE_API_SERVER = 'true'
                        env.CHANGED_INFRA = 'true'
                    }

                    echo "CHANGED_FRONTEND=${env.CHANGED_FRONTEND}"
                    echo "CHANGED_API_SERVER=${env.CHANGED_API_SERVER}"
                    echo "CHANGED_CORE_API_SERVER=${env.CHANGED_CORE_API_SERVER}"
                    echo "CHANGED_INFRA=${env.CHANGED_INFRA}"
                }
            }
        }

        stage('Prepare') {
            when {
                expression { env.IS_CI_BRANCH == 'true' || env.IS_DEPLOY_BRANCH == 'true' }
            }
            steps {
                echo '[Prepare] Injecting env file'
                withCredentials([
                    file(credentialsId: "${PROD_ENV_CREDENTIAL_ID}", variable: 'THESEUS_PROD_ENV')
                ]) {
                    sh '''
                        set -eu
                        cp "${THESEUS_PROD_ENV}" "${PROD_ENV_FILE}"
                        sed -i 's/\\r$//' "${PROD_ENV_FILE}"
                        chmod 600 "${PROD_ENV_FILE}"
                    '''
                }
            }
        }

        stage('Frontend Build') {
            when {
                expression { env.CHANGED_FRONTEND == 'true' }
            }
            steps {
                echo '[CI] Building frontend Docker image'
                sh '''
                    set -eu
                    docker build \
                        -t "${FRONTEND_CI_IMAGE}" \
                        --build-arg VITE_API_BASE_URL=http://localhost \
                        -f "${FRONTEND_DIR}/Dockerfile" \
                        "${FRONTEND_DIR}"
                '''
            }
        }

        stage('API Server Build') {
            when {
                expression { env.CHANGED_API_SERVER == 'true' }
            }
            steps {
                echo '[CI] Building API server Docker image'
                sh '''
                    set -eu
                    docker build -t "${API_SERVER_CI_IMAGE}" -f "${API_SERVER_DIR}/Dockerfile" "${API_SERVER_DIR}"
                '''
            }
        }

        stage('Core Server Build') {
            when {
                expression { env.CHANGED_CORE_API_SERVER == 'true' }
            }
            steps {
                echo '[CI] Building Core server Docker image'
                sh '''
                    set -eu
                    docker build -t "${CORE_SERVER_CI_IMAGE}" -f "${CORE_SERVER_DIR}/Dockerfile" "${CORE_SERVER_DIR}"
                '''
            }
        }

        stage('Core Server Python Import Smoke Test') {
            when {
                expression { env.CHANGED_CORE_API_SERVER == 'true' }
            }
            steps {
                echo '[CI] Validating Core server Python imports inside Docker image'
                sh '''
                    set -eu
                    docker run --rm -i \
                        -e ENV=dev \
                        -e AUTH_MODE=spring \
                        -e CORE_KAFKA_CONSUMER_ENABLED=false \
                        -e SANDBOX_STARTUP_CHECK=false \
                        -e LANGCHAIN_TRACING_V2=true \
                        -e LANGCHAIN_API_KEY=dummy-langsmith-key \
                        -e THESEUS_TRACING_ENABLED=true \
                        -e OPENAI_API_KEY=dummy-openai-key \
                        --entrypoint python \
                        "${CORE_SERVER_CI_IMAGE}" \
                        - <<'PY'
import inspect

import src.main
from src.config import settings
from src.tool_plan.planner import ToolPlanPlanner
from theseus_engine.validators.execution_validator import ExecutionValidator
from theseus_engine.validators.query_validator import QueryValidator
from theseus_engine.validators.suggestion_validator import SuggestionValidator

required_settings = [
    'CORE_KAFKA_CONSUMER_ENABLED',
    'CORE_TOOL_PLAN_CONSUMER_ENABLED',
    'CORE_TOOL_PLAN_MAX_AGENT_TURNS',
    'CORE_TOOL_BUILD_RUN_TIMEOUT_SECONDS',
]
missing = [name for name in required_settings if not hasattr(settings, name)]
assert not missing, f'missing settings: {missing}'

plan_signature = inspect.signature(ToolPlanPlanner.plan)
assert 'checkpoint' in plan_signature.parameters, plan_signature
assert 'checkpoint_callback' in plan_signature.parameters, plan_signature

print('src.main import ok')
print('ExecutionValidator.validate', inspect.signature(ExecutionValidator.validate))
print('QueryValidator.validate', inspect.signature(QueryValidator.validate))
print('SuggestionValidator.review', inspect.signature(SuggestionValidator.review))
print('ToolPlanPlanner.plan', plan_signature)
print('required settings ok', required_settings)
PY
                '''
            }
        }

        stage('Core Server Worker Contract') {
            when {
                expression { env.CHANGED_CORE_API_SERVER == 'true' }
            }
            steps {
                echo '[CI] Validating Core server single-worker runtime contract'
                sh '''
                    set -eu
                    grep -Eq '"--workers", "1"|--workers[ =]1' "${CORE_SERVER_DIR}/Dockerfile"
                '''
            }
        }

        stage('Docker Compose Config') {
            when {
                expression { env.IS_DEPLOY_BRANCH == 'true' && env.CHANGED_INFRA == 'true' }
            }
            steps {
                echo '[CD] Validating production Docker Compose config'
                sh '''
                    set -eu
                    docker compose --env-file "${PROD_ENV_FILE}" -f "${PROD_COMPOSE_FILE}" config --quiet
                '''
            }
        }

        stage('Deploy Production') {
            when {
                expression { env.IS_DEPLOY_BRANCH == 'true' }
            }
            steps {
                echo '[CD] Deploying changed production services'
                script {
                    def deployed = false

                    if (env.CHANGED_API_SERVER == 'true') {
                        echo '[CD] Deploying theseus-api-server'
                        sh '''
                            set -eu
                            docker compose --env-file "${PROD_ENV_FILE}" -f "${PROD_COMPOSE_FILE}" up -d --no-deps --build theseus-api-server
                        '''
                        deployed = true
                    }
                    if (env.CHANGED_CORE_API_SERVER == 'true') {
                        echo '[CD] Deploying theseus-core-server'
                        sh '''
                            set -eu
                            grep -Eq '"--workers", "1"|--workers[ =]1' "${CORE_SERVER_DIR}/Dockerfile"
                            docker compose --env-file "${PROD_ENV_FILE}" -f "${PROD_COMPOSE_FILE}" up -d --no-deps --build theseus-core-server
                        '''
                        deployed = true
                    }
                    if (env.CHANGED_FRONTEND == 'true') {
                        echo '[CD] Deploying theseus-frontend and nginx'
                        sh '''
                            set -eu
                            docker compose --env-file "${PROD_ENV_FILE}" -f "${PROD_COMPOSE_FILE}" up -d --no-deps --build theseus-frontend theseus-nginx
                        '''
                        deployed = true
                    }
                    if (env.CHANGED_INFRA == 'true' && !deployed) {
                        echo '[CD] Deploying all services for infra-only changes'
                        sh '''
                            set -eu
                            docker compose --env-file "${PROD_ENV_FILE}" -f "${PROD_COMPOSE_FILE}" up -d --build
                        '''
                        deployed = true
                    }
                    if (!deployed) {
                        echo '[CD] No deployable services changed. Skipping deployment.'
                    }
                }
            }
        }

        stage('Container Status') {
            when {
                expression { env.IS_DEPLOY_BRANCH == 'true' }
            }
            steps {
                echo '[CD] Checking production container status'
                sh '''
                    set -eu
                    docker compose --env-file "${PROD_ENV_FILE}" -f "${PROD_COMPOSE_FILE}" ps
                '''
            }
        }
    }

    post {
        always {
            echo '[Cleanup] Removing injected env file and temporary images'
            sh '''
                rm -f "${PROD_ENV_FILE}" || true
                docker image rm "${CORE_SERVER_CI_IMAGE}" "${FRONTEND_CI_IMAGE}" "${API_SERVER_CI_IMAGE}" || true
                docker image prune -f || true
            '''
        }
        success {
            echo '[SUCCESS] Pipeline completed'
            updateGitlabCommitStatus(name: 'Jenkins CI/CD', state: 'success')
        }
        failure {
            echo '[FAILURE] Pipeline failed'
            updateGitlabCommitStatus(name: 'Jenkins CI/CD', state: 'failed')
        }
    }
}
