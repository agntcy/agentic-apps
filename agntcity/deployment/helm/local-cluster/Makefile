SHELL := /bin/bash
ENV_FILE ?= ../../../.env

.PHONY: create-cluster apply destroy diff install-helm-diff

create-cluster:
	kind create cluster --name lungo --config kind-config.yaml

apply:
	@bash -c "set -a; source $(ENV_FILE); set +a; \
		helm dependency update .; \
		helmfile apply --skip-diff-on-install"

destroy:
	helmfile destroy

diff:
	@bash -c "set -a; source $(ENV_FILE); set +a; helmfile diff"

install-helm-diff:
	@helm plugin install https://github.com/databus23/helm-diff || true
