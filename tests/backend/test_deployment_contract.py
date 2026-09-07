from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_docker_image_uses_multistage_build_and_one_non_root_runtime():
    dockerfile = (ROOT / "Dockerfile").read_text()

    assert "FROM node:24-alpine AS frontend-build" in dockerfile
    assert "RUN npm run build" in dockerfile
    assert "FROM python:3.13-slim" in dockerfile
    assert "USER billbox" in dockerfile
    assert "VOLUME [\"/data\"]" in dockerfile
    assert "HEALTHCHECK" in dockerfile

    entrypoint = (ROOT / "docker" / "entrypoint.sh").read_text()
    assert "--workers 1" in entrypoint
    assert "billbox.main:create_application" in entrypoint


def test_compose_uses_published_image_and_persistent_sqlite_volume():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())
    service = compose["services"]["billbox"]

    assert set(service) == {"image", "env_file", "ports", "volumes", "restart"}
    assert service["image"] == "${BILLBOX_IMAGE:-ghcr.io/yaho7/billbox:main}"
    assert service["env_file"] == ["${BILLBOX_ENV_FILE:-.env}"]
    assert "/data" in service["volumes"][0]
    assert service["restart"] == "unless-stopped"


def test_action_only_builds_image_for_main_push_without_git_tag_trigger():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "image.yml").read_text())
    triggers = workflow[True]

    assert triggers == {"push": {"branches": ["main"]}}
    assert workflow["permissions"] == {"contents": "read", "packages": "write"}

    steps = workflow["jobs"]["build-image"]["steps"]
    uses = [step.get("uses", "") for step in steps]
    assert "actions/checkout@v7" in uses
    assert "docker/build-push-action@v7" in uses
    assert not any("deploy" in step.get("name", "").lower() for step in steps)
    assert not any("git tag" in step.get("run", "") for step in steps)

    build_step = next(
        step for step in steps if step.get("uses") == "docker/build-push-action@v7"
    )
    assert build_step["with"]["push"] is True
