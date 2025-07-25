import os
import pytest

@pytest.fixture(scope="session", autouse=True)
def create_upload_dirs():
    os.makedirs("uploads/original", exist_ok=True)
    os.makedirs("uploads/predicted", exist_ok=True)
