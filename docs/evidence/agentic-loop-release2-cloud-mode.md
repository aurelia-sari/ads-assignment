# Agentic loop run record - 20261022-140931

Workflow: Plan -> Act -> Observe -> Adapt

## Iteration 1 - the cloud deployment and its validation evidence
_Started 2026-10-22T14:08:41_

### Plan

1. Check that the deployment of the NextStop application to Microsoft Azure or AWS (Release 2) is verified by the contents of cloud-deployment.yml.
2. Check that the reusable deployment scripts or infrastructure as code exist for the chosen platform by verifying the contents of the IaC files referenced in cloud-deployment.yml.
3. Check that the frontend, backend/API, database and CRUD functions work in the cloud by verifying the HTTP responses from the deployed application.
4. Check that the AI-Mode, MCP, RAG and the Multi-Agent Server are DISABLED by default in the cloud by verifying the values of the environment variables set in cloud-deployment.yml.

### Act (evidence collected)

```
CHECK RESULTS (decided in code from the detail below - treat them as established facts): 10 PASS, 0 FAIL, 0 WARN
RELEASE GATE: GO - every cloud requirement checked passed
PASS - cloud-deployment.yml exists
PASS - deployment runs only after the student CI workflows succeed
PASS - 9 deployment script / IaC file(s) found
PASS - all four AI flags are set to false in the cloud configuration
PASS - no hard-coded credentials in deployment files
PASS - cloud-deployment.yml latest run on main: success (2026-10-22 00:35 UTC) https://github.com/aurelia-sari/ads-assignment/actions/runs/39700647212
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
  AI_MODE_ENABLED: OK, false (plus a compose off/on test matrix in the workflow)
  MCP_ENABLED: OK, false (plus a compose off/on test matrix in the workflow)
  RAG_ENABLED: OK, false (plus a compose off/on test matrix in the workflow)
  MULTI_AGENT_ENABLED: OK, false (plus a compose off/on test matrix in the workflow)
Hard-coded credentials in deployment files: none found

cloud-deployment.yml latest run on main: success (2026-10-22 00:35 UTC) https://github.com/aurelia-sari/ads-assignment/actions/runs/39700647212

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

**PASS**

* cloud-deployment.yml exists
* deployment runs only after the student CI workflows succeed
* 9 deployment script / IaC file(s) found
* all four AI flags are set to false in the cloud configuration
* no hard-coded credentials in deployment files
* cloud-deployment.yml latest run on main: success (2026-10-22 00:35 UTC)
* the deployed frontend serves the NextStop page at http://20.205.12.91:8080
* all five backend/APIs answer through the cloud frontend
* CRUD read works in the cloud (student-1 trips table)
* AI-Mode, MCP, RAG and Multi-Agent all answer 'disabled' in the cloud

**ISSUE**

* Not shown by the evidence: the deployment of the NextStop application to Microsoft Azure or AWS (Release 2) is verified by the contents of cloud-deployment.yml. (check 1)
* Not shown by the evidence: the reusable deployment scripts or infrastructure as code exist for the chosen platform. (check 2)
* Not shown by the evidence: the frontend, backend/API, database and CRUD functions work in the cloud. (check 3)
* Not shown by the evidence: the AI-Mode, MCP, RAG and the Multi-Agent Server are DISABLED by default in the cloud. (check 4)
* Not shown by the evidence: the values of the environment variables set in cloud-deployment.yml. (check 4)
* Not shown by the evidence: the HTTP responses from the deployed application. (check 3)
* Not shown by the evidence: the values of the environment variables set in cloud-deployment.yml. (check 4)
* Not shown by the evidence: the HTTP responses from the deployed application. (check 3)
* Not shown by the evidence: the values of the environment variables set in cloud-deployment.yml. (check 4)
* Not shown by the evidence: the HTTP responses from the deployed application. (check 3)

### Adapt

NEXT CHANGE: The team should update the cloud-deployment.yml file to include the values of the environment variables set in the file.

NEXT CHECK: The team should verify that the environment variables are correctly set in the cloud deployment and that the HTTP responses from the deployed application are as expected.

### Human release decision

GO - decided by TJ at 2026-10-22T14:09:31 (computed release gate: GO). Reason: Baseline deployed. All four AI flags default to false in the deploy scripts; the workflow's true/false values are a compose-validation test loop. Latest cloud-deployment.yml run on main succeeded and all four AI paths answer disabled live. HTTP-only is a known limitation.
