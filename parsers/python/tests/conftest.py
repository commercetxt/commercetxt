import pytest
from pathlib import Path


@pytest.fixture
def vectors_root():
    return Path(__file__).parent / "vectors"
