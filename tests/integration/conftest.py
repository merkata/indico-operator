# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
from pathlib import Path

import pytest_asyncio
import yaml
from ops.model import WaitingStatus
from pytest import Config, fixture
from pytest_operator.plugin import OpsTest


@fixture(scope="module")
def metadata():
    """Provides charm metadata."""
    yield yaml.safe_load(Path("./metadata.yaml").read_text())


@fixture(scope="module")
def app_name(metadata):
    """Provides app name from the metadata."""
    yield metadata["name"]


@fixture(scope="module")
def nginx_prometheus_exporter_image(metadata):
    """Provides the nginx prometheus exporter image from the metadata."""
    yield metadata["resources"]["nginx-prometheus-exporter-image"]["upstream-source"]


@pytest_asyncio.fixture(scope="module")
async def app(
    ops_test: OpsTest, app_name: str, pytestconfig: Config, nginx_prometheus_exporter_image: str
):
    """Indico charm used for integration testing.

    Builds the charm and deploys it and the relations it depends on.
    """
    # Deploy relations to speed up overall execution
    await asyncio.gather(
        ops_test.model.deploy("postgresql-k8s"),
        ops_test.model.deploy("redis-k8s", "redis-broker"),
        ops_test.model.deploy("redis-k8s", "redis-cache"),
    )

    charm = await ops_test.build_charm(".")
    resources = {
        "indico-image": pytestconfig.getoption("--indico-image"),
        "indico-nginx-image": pytestconfig.getoption("--indico-nginx-image"),
        "nginx-prometheus-exporter-image": nginx_prometheus_exporter_image,
    }
    application = await ops_test.model.deploy(
        charm, resources=resources, application_name=app_name
    )
    await ops_test.model.wait_for_idle()

    # Add required relations
    assert ops_test.model.applications[app_name].units[0].workload_status == WaitingStatus.name
    await asyncio.gather(
        ops_test.model.add_relation(app_name, "postgresql-k8s:db"),
        ops_test.model.add_relation(app_name, "redis-broker"),
        ops_test.model.add_relation(app_name, "redis-cache"),
    )
    await ops_test.model.wait_for_idle(status="active")

    yield application
