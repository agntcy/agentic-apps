# Guide Agent Job Template
#
# Variables (set before using envsubst):
#   NAMESPACE, IMAGE_REGISTRY, IMAGE_TAG
#   GUIDE_ID, GUIDE_CATEGORIES, GUIDE_START, GUIDE_END
#   GUIDE_RATE, GUIDE_MAX_GROUP

---
apiVersion: batch/v1
kind: Job
metadata:
  name: guide-agent-${GUIDE_ID}
  namespace: ${NAMESPACE}
  labels:
    app: guide-agent
    app.kubernetes.io/name: guide-agent
    app.kubernetes.io/part-of: tourist-scheduling
    app.kubernetes.io/component: agent
    guide-id: "${GUIDE_ID}"
spec:
  ttlSecondsAfterFinished: 300
  backoffLimit: 2
  template:
    metadata:
      labels:
        app: guide-agent
        guide-id: "${GUIDE_ID}"
    spec:
      restartPolicy: Never
      containers:
        - name: guide-agent
          image: ${IMAGE_REGISTRY}/guide-agent:${IMAGE_TAG}
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
          args:
            - "--scheduler-url=http://scheduler-agent:10000"
            - "--guide-id=${GUIDE_ID}"
            - "--categories=${GUIDE_CATEGORIES}"
            - "--available-start=${GUIDE_START}"
            - "--available-end=${GUIDE_END}"
            - "--hourly-rate=${GUIDE_RATE}"
            - "--max-group-size=${GUIDE_MAX_GROUP}"
          resources:
            requests:
              memory: "512Mi"
              cpu: "100m"
            limits:
              memory: "1Gi"
              cpu: "500m"
