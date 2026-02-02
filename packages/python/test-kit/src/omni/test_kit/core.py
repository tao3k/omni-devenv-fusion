import os
import shutil
import tempfile
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def test_root():
    """
    Create a temporary root directory for all tests in this session.
    This ensures Rust singletons (EventBus, VectorStore) use consistent paths.
    """
    tmp_dir = tempfile.mkdtemp(prefix="omni_test_root_")
    yield Path(tmp_dir)
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def temp_lancedb(test_root, request):
    """
    Provide a clean, isolated LanceDB path for each test function.
    """
    db_name = f"db_{request.node.name}"
    db_path = test_root / "vectors" / db_name
    db_path.mkdir(parents=True, exist_ok=True)

    # Set environment variable for Rust bindings
    original_path = os.environ.get("OMNI_VECTOR_DB_PATH")
    os.environ["OMNI_VECTOR_DB_PATH"] = str(db_path)

    yield db_path

    # Restore original environment
    if original_path is not None:
        os.environ["OMNI_VECTOR_DB_PATH"] = original_path
    else:
        os.environ.pop("OMNI_VECTOR_DB_PATH", None)


@pytest.fixture(scope="function")
async def clean_reactor(test_root):
    """
    Ensure the Kernel Reactor is reset between tests.
    """
    try:
        from omni.core.kernel.reactor import get_reactor

        reactor = get_reactor()

        # Stop any running reactor tasks
        try:
            await reactor.stop()
        except Exception:
            pass

        # Clear all handlers
        if hasattr(reactor, "_handlers"):
            reactor._handlers.clear()

        yield reactor

        # Cleanup after test
        try:
            await reactor.stop()
        except Exception:
            pass
        if hasattr(reactor, "_handlers"):
            reactor._handlers.clear()
    except ImportError:
        yield None
