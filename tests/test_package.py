import tiny_harness


def test_package_exposes_a_version() -> None:
    assert tiny_harness.__version__ == "0.1.0"
