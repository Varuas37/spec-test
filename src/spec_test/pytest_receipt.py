"""Private subprocess plugin that records pytest events rather than parsing stdout."""

import json

import pytest


def pytest_addoption(parser):
    parser.addoption("--spec-test-receipt", type=str)


def pytest_configure(config):
    config.pluginmanager.register(Receipt(config.getoption("--spec-test-receipt")))


class Receipt:
    def __init__(self, output):
        self.output = output
        self.tests = {}

    def pytest_runtest_logreport(self, report):
        self.tests.setdefault(report.nodeid, []).append(
            (report.when, report.outcome, getattr(report, "wasxfail", None) is not None)
        )

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        if self.output:
            with open(self.output, "w", encoding="utf-8") as file:
                json.dump(
                    {"root": str(session.config.rootpath), "tests": self.tests}, file
                )
