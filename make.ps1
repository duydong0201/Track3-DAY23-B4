param (
    [string]$Target = "test"
)

$VENV_PYTHON = ".\.venv\Scripts\python.exe"
$VENV_PYTEST = ".\.venv\Scripts\pytest.exe"

switch ($Target) {
    "test" {
        & $VENV_PYTEST --basetemp=./.pytest_tmp
    }
    "run-scenarios" {
        & $VENV_PYTHON -m langgraph_agent_lab.cli run-scenarios --config configs/lab.yaml --output outputs/metrics.json
    }
    "grade-local" {
        & $VENV_PYTHON -m langgraph_agent_lab.cli validate-metrics --metrics outputs/metrics.json
    }
    default {
        Write-Host "Usage: .\make.ps1 [test | run-scenarios | grade-local]"
    }
}
