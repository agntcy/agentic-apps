
{{/*
Base name for the assistant component
*/}}
{{- define "network-of-assistants.file-assistant.name" -}}
{{- printf "%s-file-assistant" (include  "network-of-assistants.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "network-of-assistants.file-assistant.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default (include "network-of-assistants.file-assistant.name" .) .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "network-of-assistants.file-assistant.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "network-of-assistants.file-assistant.labels" -}}
{{ include "network-of-assistants.labels" . }}
app.kubernetes.io/component: "file-assistant"
{{- end }}

{{/*
Selector labels
*/}}
{{- define "network-of-assistants.file-assistant.selectorLabels" -}}
app.kubernetes.io/name: {{ include "network-of-assistants.name" . }}
app.kubernetes.io/component: "file-assistant"
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "network-of-assistants.file-assistant.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "network-of-assistants.file-assistant.name" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Base name for the LLM secret
*/}}
{{- define "network-of-assistants.file-assistant.llmRemoteAPISecretName" -}}
{{- printf "%s-llmsecrets" (include  "network-of-assistants.file-assistant.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Base name for the RAG secret
*/}}
{{- define "network-of-assistants.file-assistant.ragRemoteAPISecretName" -}}
{{- printf "%s-ragsecrets" (include  "network-of-assistants.file-assistant.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
