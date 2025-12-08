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
  namespace: ${NAMESPACE:-lumuscar-jobs}
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
          image: ${IMAGE_REGISTRY:-ghcr.io/agntcy}/guide-agent:${IMAGE_TAG:-latest}
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
            - "--guide-id=${GUIDE_ID}"
            - "--categories=${GUIDE_CATEGORIES:-culture,history}"
            - "--available-start=${GUIDE_START:-2025-06-01T09:00:00}"
            - "--available-end=${GUIDE_END:-2025-06-01T17:00:00}"
            - "--hourly-rate=${GUIDE_RATE:-50}"
            - "--max-group-size=${GUIDE_MAX_GROUP:-5}"
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "250m"
