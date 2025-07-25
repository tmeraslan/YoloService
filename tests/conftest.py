# tests/conftest.py
import os
import pytest
from db import engine, Base

@pytest.fixture(scope="session", autouse=True)
def create_upload_dirs():
    os.makedirs("uploads/original", exist_ok=True)
    os.makedirs("uploads/predicted", exist_ok=True)

@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    Base.metadata.create_all(bind=engine)
