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
  namespace: ${NAMESPACE:-lumuscar-jobs}
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
          image: ${IMAGE_REGISTRY:-ghcr.io/agntcy}/tourist-agent:${IMAGE_TAG:-latest}
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
            - "--tourist-id=${TOURIST_ID}"
            - "--preferences=${TOURIST_PREFERENCES:-culture,history}"
            - "--availability-start=${TOURIST_START:-2025-06-01T09:00:00}"
            - "--availability-end=${TOURIST_END:-2025-06-01T17:00:00}"
            - "--budget=${TOURIST_BUDGET:-100}"
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "250m"
