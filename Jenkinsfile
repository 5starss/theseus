pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        PROD_COMPOSE_FILE = 'infra/docker/prod/docker-compose.prod.yml'
        PROD_ENV_FILE = 'infra/docker/prod/.env'
        PROD_ENV_CREDENTIAL_ID = 'theseus-prod-env'
    }

    stages {
        stage('Checkout') {
            steps {
                echo '[CI] Checking out source code'
                checkout scm
            }
        }

        stage('Validate Pipeline Context') {
            steps {
                script {
                    env.IS_MR_BUILD = (env.CHANGE_ID || env.gitlabMergeRequestIid) ? 'true' : 'false'
                    env.IS_DEPLOY_BRANCH = (env.BRANCH_NAME == 'dev' && env.IS_MR_BUILD != 'true') ? 'true' : 'false'

                    echo "Branch: ${env.BRANCH_NAME}"
                    echo "MR build: ${env.IS_MR_BUILD}"
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

        stage('Inject Production Env') {
            when {
                expression { env.IS_DEPLOY_BRANCH == 'true' }
            }
            steps {
                echo '[CD] Injecting production env file from Jenkins credentials'
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

        stage('Docker Compose Config') {
            when {
                expression { env.IS_DEPLOY_BRANCH == 'true' }
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
                echo '[CD] Deploying production services'
                sh '''
                    set -eu
                    docker compose --env-file "${PROD_ENV_FILE}" -f "${PROD_COMPOSE_FILE}" up -d --build
                '''
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
            echo '[Cleanup] Removing injected production env file'
            sh '''
                rm -f "${PROD_ENV_FILE}" || true
                docker image prune -f || true
            '''
        }
        success {
            echo '[SUCCESS] Pipeline completed'
        }
        failure {
            echo '[FAILURE] Pipeline failed'
        }
    }
}
