pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                echo 'Checking out source...'
                checkout scm
            }
        }

        stage('Verify Branch') {
            steps {
                echo "Current branch: ${env.BRANCH_NAME}"
                sh 'pwd'
                sh 'ls -al'
            }
        }

        stage('Tool Check') {
            steps {
                sh 'docker --version'
                sh 'git --version'
            }
        }
    }
}