"""Register the `installer` marker used by tests that run templates/*.sh."""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "installer: runs a script from templates/, which is not installed in an "
        "adopter repository (skipped there)")
