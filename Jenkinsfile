openshift.withCluster() {
    env.APP_NAME = 'hello-world-service'
    env.NAMESPACE = openshift.project()
    env.PROD_NAMESPACE = NAMESPACE.replaceAll(/-cicd/, '')
    def configMap = openshift.selector('configmap', 'istio-app-subdomain').object()
    env.SUBDOMAIN = configMap.data["subdomain"]
    echo "APP_NAME: ${APP_NAME}"
    echo "NAMESPACE: ${NAMESPACE}"
    echo "PROD_NAMESPACE: ${PROD_NAMESPACE}"
    echo "SUBDOMAIN: ${SUBDOMAIN}"
}

pipeline {
    agent any
    stages {
        stage("SCM Checkout") {
            steps {
                script {
                    checkout scm
                }
            }
        }
        stage("Build image") {
            steps {
                script {
                    openshift.withCluster() {
                        buildSelector = openshift.selector('bc', APP_NAME).startBuild("--from-dir .", "--wait", "--follow")
                        echo "Build complete: " + buildSelector.names()
                    }
                }
            }
        }
        stage("Canary deployment") {
            steps {
                script {
                    openshift.withCluster() {
                        echo "Tagging ${PROD_NAMESPACE}/${APP_NAME}:canary from ${NAMESPACE}/${APP_NAME}:latest"
                        openshift.tag("${NAMESPACE}/${APP_NAME}:latest", "${PROD_NAMESPACE}/${APP_NAME}:canary")
                        openshift.withProject("${PROD_NAMESPACE}") {
                            def dc_selector = openshift.selector('dc', "${APP_NAME}-canary")
                            if (dc_selector.exists()) {
                                echo "Setting dc/${APP_NAME}-canary to ${PROD_NAMESPACE}/${APP_NAME}:canary"
                                openshift.set('image', "dc/${APP_NAME}-canary", "${APP_NAME}-canary=${PROD_NAMESPACE}/${APP_NAME}:canary", "--source=imagestreamtag")
                                openshift.selector('dc', "${APP_NAME}-canary").rollout().latest()
                                openshift.selector('dc', "${APP_NAME}-canary").rollout().status()
                                def latestVersion = openshift.selector('dc', "${APP_NAME}-canary").object().status.latestVersion
                                echo "Latest Version is ${latestVersion}"
                                echo "Canary pod(s) are up: " + openshift.selector('pod',['deployment':"${APP_NAME}-canary-${latestVersion}"])
                            }
                        }
                    }
                }
            }
        }
        stage("Configuring Mirror Traffic") {
            steps {
                sh "sed 's/<istio-subdomain>/${SUBDOMAIN}/g' k8s/istio/hello-world-virtual-service-mirror.yaml.tmpl > k8s/istio/hello-world-virtual-service-mirror.yaml"
                sh 'oc apply -n ${PROD_NAMESPACE} -f k8s/istio/hello-world-virtual-service-mirror.yaml'
            }
        }

        /*************
         * Ask to release canary to 10% - when canaryDc.exists()
         *************/
        stage("Verify Mirror Traffic") {
            steps {
                script {
                    promoteOrRollback = input message: 'Release canary deployment to 10% of Traffic?',
                            parameters: [choice(name: "Promote or Rollback?", choices: 'Promote\nRollback', description: '')]
                }
            }
        }
        
        stage("Rollback Mirror"){
            when{
                expression {
                    return promoteOrRollback == 'Rollback'
                }
            }
            steps{
                echo "Rollback for canary deployment."
                sh "sed 's/<istio-subdomain>/${SUBDOMAIN}/g' k8s/istio/hello-world-virtual-service-init.yaml.tmpl > k8s/istio/hello-world-virtual-service-init.yaml"
                sh 'oc apply -n ${PROD_NAMESPACE} -f k8s/istio/hello-world-virtual-service-init.yaml'
            }
        }

        stage("Release Canary to 10%") {
            steps {
                sh "sed 's/<istio-subdomain>/${SUBDOMAIN}/g' k8s/istio/hello-world-virtual-service-canary-90-10.yaml.tmpl > k8s/istio/hello-world-virtual-service-canary-90-10.yaml"
                sh 'oc apply -n ${PROD_NAMESPACE} -f k8s/istio/hello-world-virtual-service-canary-90-10.yaml'
            }
        }
        
        /*************
         * Ask to release canary to 50% - when canaryDc.exists()
         *************/
        stage("Verify Canary") {
            steps {
                script {
                    promoteOrRollback = input message: 'Release canary deployment to 50% of Traffic?',
                            parameters: [choice(name: "Promote or Rollback?", choices: 'Promote\nRollback', description: '')]
                }
            }
        }

        stage("Rollback canary"){
            when{
                expression {
                    return promoteOrRollback == 'Rollback'
                }
            }
            steps{
                echo "Rollback for canary deployment."
                sh "sed 's/<istio-subdomain>/${SUBDOMAIN}/g' k8s/istio/hello-world-virtual-service-init.yaml.tmpl > k8s/istio/hello-world-virtual-service-init.yaml"
                sh 'oc apply -n ${PROD_NAMESPACE} -f k8s/istio/hello-world-virtual-service-init.yaml'
            }
        }

        stage("Releasing Canary to 50%") {
            steps {
                sh "sed 's/<istio-subdomain>/${SUBDOMAIN}/g' k8s/istio/hello-world-virtual-service-canary-50-50.yaml.tmpl > k8s/istio/hello-world-virtual-service-canary-50-50.yaml"
                sh 'oc apply -n ${PROD_NAMESPACE} -f k8s/istio/hello-world-virtual-service-canary-50-50.yaml'
            }
        }

         /*************
         * Ask to promote to production
         *************/
        stage("Complete Rollout?") {
            steps {
                script {
                    promoteOrRollback = input message: 'Complete Rollout?',
                            parameters: [choice(name: "Complete Rollout or Rollback?", choices: 'Promote\nRollback', description: '')]
                }
            }
        }

        stage("Production deployment") {
            when {
                expression {
                    return promoteOrRollback != 'Rollback'
                }
            }
            steps {
                script {
                    openshift.withCluster() {
                        openshift.withProject("$PROD_NAMESPACE") {
                            openshift.tag("$NAMESPACE/$APP_NAME:latest", "$PROD_NAMESPACE/$APP_NAME:production")
                            openshift.set('image', "dc/${APP_NAME}", "${APP_NAME}=${PROD_NAMESPACE}/${APP_NAME}:production", "--source=imagestreamtag")
                            openshift.selector('dc', "${APP_NAME}").rollout().latest()
                            openshift.selector('dc', "${APP_NAME}").rollout().status()
                            def latestVersion = openshift.selector('dc', "${APP_NAME}").object().status.latestVersion
                            echo "Latest Version: ${latestVersion}"
                            echo "Production pod(s) are up: " + openshift.selector('pod',['deployment':"${APP_NAME}-${latestVersion}"])
                            // Remove Mirror
                            sh "sed 's/<istio-subdomain>/${SUBDOMAIN}/g' k8s/istio/hello-world-virtual-service-init.yaml.tmpl > k8s/istio/hello-world-virtual-service-init.yaml"
                            sh 'oc apply -n ${PROD_NAMESPACE} -f k8s/istio/hello-world-virtual-service-init.yaml'
                        }
                    }
                }
            }
        }
    }
}