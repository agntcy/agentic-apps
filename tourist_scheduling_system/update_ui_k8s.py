
import os

file_path = 'deploy/k8s/ui-agent.yaml'

env_vars_to_add = """            # Model Configuration
            - name: MODEL_PROVIDER
              value: "${MODEL_PROVIDER}"
            - name: MODEL_NAME
              value: "${MODEL_NAME}"
            - name: GOOGLE_API_KEY
              value: "${GOOGLE_API_KEY}"
            - name: AZURE_OPENAI_API_KEY
              value: "${AZURE_OPENAI_API_KEY}"
            - name: AZURE_OPENAI_ENDPOINT
              value: "${AZURE_OPENAI_ENDPOINT}"
            - name: AZURE_OPENAI_API_VERSION
              value: "${AZURE_OPENAI_API_VERSION}"
            - name: AZURE_OPENAI_DEPLOYMENT_NAME
              value: "${AZURE_OPENAI_DEPLOYMENT_NAME}"
"""

with open(file_path, 'r') as f:
    content = f.readlines()

new_content = []
env_section_found = False
inserted = False

for line in content:
    new_content.append(line)
    if 'env:' in line:
        env_section_found = True

    if env_section_found and not inserted and '- name: PORT' in line:
        # Insert after PORT
        new_content.append(env_vars_to_add)
        inserted = True

with open(file_path, 'w') as f:
    f.writelines(new_content)

print(f"Updated {file_path}")
