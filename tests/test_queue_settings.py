"""Why this file exists
=====================

The queue connects without a login locally (Redpanda in Docker) and with a
username and password when deployed (Redpanda Cloud, Confluent Cloud).
Checks memory/queue.py `connection_settings` picks the right one from the
environment.
"""

from memory import queue


def test_no_username_means_no_login(monkeypatch):
    monkeypatch.delenv("KAFKA_USERNAME", raising=False)
    assert queue.connection_settings() == {}


def test_a_username_switches_on_a_secure_login(monkeypatch):
    monkeypatch.setenv("KAFKA_USERNAME", "memory-app")
    monkeypatch.setenv("KAFKA_PASSWORD", "secret")
    monkeypatch.delenv("KAFKA_SASL_MECHANISM", raising=False)

    assert queue.connection_settings() == {
        "security_protocol": "SASL_SSL",
        "sasl_mechanism": "SCRAM-SHA-256",
        "sasl_plain_username": "memory-app",
        "sasl_plain_password": "secret",
    }


def test_the_mechanism_can_be_changed_for_confluent(monkeypatch):
    monkeypatch.setenv("KAFKA_USERNAME", "key")
    monkeypatch.setenv("KAFKA_SASL_MECHANISM", "PLAIN")
    assert queue.connection_settings()["sasl_mechanism"] == "PLAIN"
