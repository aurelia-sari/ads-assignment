"""Keep the local AI timeout while allowing CPU cloud deployment to extend it."""
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import requests

ROOT = Path(__file__).resolve().parents[2]
CLIENT_PATH = ROOT / "student-2" / "api" / "services" / "ai_client.py"


def load_client(timeout=None):
    env = dict(os.environ)
    env.pop("AI_REQUEST_TIMEOUT_SECONDS", None)
    if timeout is not None:
        env["AI_REQUEST_TIMEOUT_SECONDS"] = timeout
    with patch.dict(os.environ, env, clear=True):
        spec = importlib.util.spec_from_file_location("student2_cloud_ai_client", CLIENT_PATH)
        client = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(client)
    return client


class Student2AITimeoutTests(unittest.TestCase):
    def test_local_default_still_times_out_after_30_seconds(self):
        client = load_client()
        response = Mock()
        response.json.return_value = {"answer": "Use the existing place data."}
        with patch.object(client.requests, "post", return_value=response) as post:
            answer = client.ask_ai("One place?", system="Use the context.", context="A place.")
        self.assertEqual(answer, "Use the existing place data.")
        self.assertEqual(post.call_args.kwargs["timeout"], 30)
        self.assertEqual(post.call_args.kwargs["json"], {
            "question": "One place?", "max_tokens": 300,
            "system": "Use the context.", "context": "A place.",
        })
        response.raise_for_status.assert_called_once_with()

    def test_cloud_can_allow_180_seconds_for_generation(self):
        client = load_client("180")
        response = Mock()
        response.json.return_value = {"answer": "A real model answer."}
        with patch.object(client.requests, "post", return_value=response) as post:
            self.assertEqual(client.ask_ai("One place?"), "A real model answer.")
        self.assertEqual(post.call_args.kwargs["timeout"], 180)

    def test_timeout_is_reported_to_the_existing_route(self):
        client = load_client("180")
        failure = requests.Timeout("generation exceeded the configured limit")
        with patch.object(client.requests, "post", side_effect=failure):
            with self.assertRaises(requests.Timeout) as caught:
                client.ask_ai("One place?")
        self.assertIs(caught.exception, failure)

    def test_http_failure_is_not_converted_into_an_answer(self):
        client = load_client("180")
        response = Mock()
        failure = requests.HTTPError("AI service returned 503")
        response.raise_for_status.side_effect = failure
        with patch.object(client.requests, "post", return_value=response):
            with self.assertRaises(requests.HTTPError):
                client.ask_ai("One place?")
        response.json.assert_not_called()

    def test_invalid_timeout_configuration_fails_visibly(self):
        with self.assertRaises(ValueError):
            load_client("not-a-number")


if __name__ == "__main__":
    unittest.main(verbosity=2)
