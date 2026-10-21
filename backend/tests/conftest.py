import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def isolated_app_database(tmp_path_factory):
    previous = os.environ.get("SEO_WORKSPACE_DATA_DIR")
    os.environ["SEO_WORKSPACE_DATA_DIR"] = str(tmp_path_factory.mktemp("app-data"))
    yield
    if previous is None:
        os.environ.pop("SEO_WORKSPACE_DATA_DIR", None)
    else:
        os.environ["SEO_WORKSPACE_DATA_DIR"] = previous
