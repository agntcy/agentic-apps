apiVersion: spire.spiffe.io/v1alpha1
kind: ClusterSPIFFEID
metadata:
  name: slim-node-${NODE_NAME}
spec:
  className: lumuscar-spire-spire
  dnsNameTemplates:
  - ${NODE_NAME}
  - ${NODE_NAME}.${NAMESPACE}.svc.cluster.local
  podSelector:
    matchLabels:
      app.kubernetes.io/instance: slim-${NODE_NAME}
      app.kubernetes.io/name: slim
  spiffeIDTemplate: spiffe://${SPIRE_TRUST_DOMAIN}/ns/{{ .PodMeta.Namespace }}/sa/slim
  workloadSelectorTemplates:
  - k8s:ns:${NAMESPACE}
  - k8s:sa:slim
