# Agentic loop run record - 20261022-135637

Workflow: Plan -> Act -> Observe -> Adapt

## Iteration 1 - the cloud deployment and its validation evidence
_Started 2026-10-22T13:55:04_

### Plan

1. Check that the deployment of the integrated application through GitHub Actions is verified by checking the contents of `cloud-deployment.yml`.
2. Check that reusable deployment scripts or infrastructure as code exist for the chosen platform by checking the contents of the IaC files.
3. Check that the frontend, backend/API, database and CRUD functions work in the cloud by checking the HTTP responses from the deployed application.
4. Check that AI-Mode, MCP, RAG and the Multi-Agent Server are DISABLED by default in the cloud by checking the values of `AI_MODE_ENABLED`, `MCP_ENABLED`, `RAG_ENABLED`, and `MULTI_AGENT_ENABLED` in the deployed application.

### Act (evidence collected)

```
CHECK RESULTS (decided in code from the detail below - treat them as established facts): 8 PASS, 1 FAIL, 0 WARN
RELEASE GATE: NO-GO - 1 cloud requirement(s) failed
FAIL - not set to false in the cloud configuration: AI_MODE_ENABLED, MCP_ENABLED, RAG_ENABLED, MULTI_AGENT_ENABLED
PASS - cloud-deployment.yml exists
PASS - deployment runs only after the student CI workflows succeed
PASS - 9 deployment script / IaC file(s) found
PASS - no hard-coded credentials in deployment files
PASS - the deployed frontend serves the NextStop page at http://20.205.12.91:8080
PASS - all five backend/APIs answer through the cloud frontend
PASS - CRUD read works in the cloud (student-1 trips table)
PASS - AI-Mode, MCP, RAG and Multi-Agent all answer 'disabled' in the cloud

DETAIL:
cloud-deployment.yml: present, 129 lines
  triggers: ['push', 'workflow_dispatch', 'pull_request']
  jobs: ['validate', 'deploy']
  deploys only after CI validation succeeds: OK (workflow_run on success, or needs: on test jobs)
  steps: ['actions/checkout@v4', 'actions/setup-python@v5', 'Install cloud test dependencies', 'Check deployment shell scripts', 'Test cloud configuration and failure handling without a VM', 'Test shared Multi-Agent execution and recovery', 'Test shared RAG citation handling', 'Test AI-Mode structured output transport', 'Validate cloud Compose with shared AI off and on', 'actions/checkout@v4', 'Gate on student CI/CD workflows', 'Install SSH key', 'Retain cloud AI selection for automatic deployments', 'Deploy application and selected shared AI runtime to Azure VM']
  GitHub secrets referenced: ['VM_HOST', 'VM_SSH_KEY']

Deployment scripts / infrastructure as code: deploy/azure/cloud-init.yml, deploy/azure/configure_ai.sh, deploy/azure/deploy-all.sh, deploy/azure/deploy.sh, deploy/azure/deploy_remote.sh, deploy/azure/provision.sh, deploy/azure/run_ai_service.sh, deploy/azure/smoke_cloud.sh, deploy/azure/wait_for_student_ci.py

AI services disabled by default in the cloud configuration:
  AI_MODE_ENABLED: CHECK, set to ['enable', 'enabled', 'mcp']
  MCP_ENABLED: CHECK, set to ['enable', 'enabled', 'rag']
  RAG_ENABLED: CHECK, set to ['enable', 'enabled', 'multi']
  MULTI_AGENT_ENABLED: CHECK, set to ['enable', 'enabled', 'tr']
Hard-coded credentials in deployment files: none found

cloud-deployment.yml latest run: not checked (To get started with GitHub CLI, please run:  gh auth login
Alternatively, populate the GH_TOKEN environment variable wit)

Deployed application at http://20.205.12.91:8080:
  GET / : 200, NextStop page served
  student-1-api health through the cloud frontend: 200
  student-2-api health through the cloud frontend: 200
  student-3-api health through the cloud frontend: 200
  student-4-api health through the cloud frontend: 200
  student-5-api health through the cloud frontend: 200
  CRUD read, GET /api/student-1/trips: 200, trips table returned
  AI paths (each must answer with the disabled notice, not a result):
    AI-Mode chat: OK, disabled (200)
    MCP: OK, disabled (200)
    RAG: OK, disabled (200)
    Multi-Agent: OK, disabled (200)
```

### Observe

PASS:
- `cloud-deployment.yml` exists
- `deployment` runs only after the student CI workflows succeed
- 9 deployment script / IaC file(s) found
- No hard-coded credentials in deployment files
- The deployed frontend serves the NextStop page at http://20.205.12.91:8080
- All five backend/APIs answer through the cloud frontend
- CRUD read works in the cloud (student-1 trips table)
- AI-Mode, MCP, RAG and Multi-Agent all answer 'disabled' in the cloud

ISSUE:
- `AI_MODE_ENABLED`, `MCP_ENABLED`, `RAG_ENABLED`, and `MULTI_AGENT_ENABLED` are not set to `false` in the cloud configuration

### Adapt

NEXT CHANGE: The team should set `AI_MODE_ENABLED`, `MCP_ENABLED`, `RAG_ENABLED`, and `MULTI_AGENT_ENABLED` to `false` in the cloud configuration to prevent accidental activation.

NEXT CHECK: The team should verify that these environment variables are indeed set to `false` in the cloud configuration by checking the `cloud-deployment.yml` file and the deployed frontend's configuration.

### Human release decision

DEFERRED - decided by tj at 2026-10-22T13:56:37 (computed release gate: NO-GO). Reason: gate NO-GO is a collector false positive. Live checks show AI-Mode, MCP, RAG and Multi-Agent all answer disabled in the cloud, and container flags read false. Will fix the flag check and re-run.
