apiVersion: spire.spiffe.io/v1alpha1
kind: ClusterSPIFFEID
metadata:
  name: slim-control
spec:
  className: lumuscar-spire-spire
  dnsNameTemplates:
  - slim-control
  - slim-control.${NAMESPACE}.svc.cluster.local
  podSelector:
    matchLabels:
      app.kubernetes.io/name: slim-control-plane
  spiffeIDTemplate: spiffe://${SPIRE_TRUST_DOMAIN}/ns/{{ .PodMeta.Namespace }}/sa/slim-control
  workloadSelectorTemplates:
  - k8s:ns:${NAMESPACE}
  - k8s:sa:slim-control
