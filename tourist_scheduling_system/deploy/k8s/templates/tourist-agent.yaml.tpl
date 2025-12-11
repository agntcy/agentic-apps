# Tourist Agent Job Template
#
# Variables (set before using envsubst):
#   NAMESPACE, IMAGE_REGISTRY, IMAGE_TAG
#   TOURIST_ID, TOURIST_PREFERENCES, TOURIST_START, TOURIST_END, TOURIST_BUDGET

---
apiVersion: batch/v1
kind: Job
metadata:
  name: tourist-agent-${TOURIST_ID}
  namespace: ${NAMESPACE}
  labels:
    app: tourist-agent
    app.kubernetes.io/name: tourist-agent
    app.kubernetes.io/part-of: tourist-scheduling
    app.kubernetes.io/component: agent
    tourist-id: "${TOURIST_ID}"
spec:
  ttlSecondsAfterFinished: 300
  backoffLimit: 2
  template:
    metadata:
      labels:
        app: tourist-agent
        tourist-id: "${TOURIST_ID}"
    spec:
      restartPolicy: Never
      containers:
        - name: tourist-agent
          image: ${IMAGE_REGISTRY}/tourist-agent:${IMAGE_TAG}
          imagePullPolicy: Always
          env:
            - name: AZURE_OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: azure-openai-credentials
                  key: api-key
            - name: AZURE_OPENAI_ENDPOINT
              valueFrom:
                secretKeyRef:
                  name: azure-openai-credentials
                  key: endpoint
            - name: AZURE_OPENAI_DEPLOYMENT_NAME
              valueFrom:
                secretKeyRef:
                  name: azure-openai-credentials
                  key: deployment-name
            - name: SCHEDULER_URL
              valueFrom:
                configMapKeyRef:
                  name: agent-config
                  key: SCHEDULER_URL
                  optional: true
            - name: TRANSPORT_MODE
              valueFrom:
                configMapKeyRef:
                  name: agent-config
                  key: TRANSPORT_MODE
                  optional: true
            - name: SLIM_GATEWAY_HOST
              valueFrom:
                configMapKeyRef:
                  name: agent-config
                  key: SLIM_GATEWAY_HOST
                  optional: true
            - name: SLIM_GATEWAY_PORT
              valueFrom:
                configMapKeyRef:
                  name: agent-config
                  key: SLIM_GATEWAY_PORT
                  optional: true
            - name: SLIM_SHARED_SECRET
              valueFrom:
                configMapKeyRef:
                  name: agent-config
                  key: SLIM_SHARED_SECRET
                  optional: true
            - name: SLIM_TLS_INSECURE
              valueFrom:
                configMapKeyRef:
                  name: agent-config
                  key: SLIM_TLS_INSECURE
                  optional: true
            - name: SCHEDULER_SLIM_TOPIC
              valueFrom:
                configMapKeyRef:
                  name: agent-config
                  key: SCHEDULER_SLIM_TOPIC
                  optional: true
            - name: HTTP_PROXY
              valueFrom:
                configMapKeyRef:
                  name: agent-config
                  key: HTTP_PROXY
                  optional: true
            - name: HTTPS_PROXY
              valueFrom:
                configMapKeyRef:
                  name: agent-config
                  key: HTTPS_PROXY
                  optional: true
            - name: NO_PROXY
              valueFrom:
                configMapKeyRef:
                  name: agent-config
                  key: NO_PROXY
                  optional: true
            - name: http_proxy
              valueFrom:
                configMapKeyRef:
                  name: agent-config
                  key: HTTP_PROXY
                  optional: true
            - name: https_proxy
              valueFrom:
                configMapKeyRef:
                  name: agent-config
                  key: HTTPS_PROXY
                  optional: true
            - name: no_proxy
              valueFrom:
                configMapKeyRef:
                  name: agent-config
                  key: NO_PROXY
                  optional: true
          args:
            - "--scheduler-url=http://scheduler-agent:10000"
            - "--tourist-id=${TOURIST_ID}"
            - "--preferences=${TOURIST_PREFERENCES}"
            - "--availability-start=${TOURIST_START}"
            - "--availability-end=${TOURIST_END}"
            - "--budget=${TOURIST_BUDGET}"
          resources:
            requests:
              memory: "512Mi"
              cpu: "100m"
            limits:
              memory: "1Gi"
              cpu: "500m"
