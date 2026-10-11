from unittest import mock

from django.test import SimpleTestCase

from server.tests import localserver


class TestSharedTestServer(SimpleTestCase):
    def test_every_class_shares_one_pair_of_servers(self) -> None:
        # Each class started its own Django and webpack servers: the webpack
        # compile alone took ~25 s, seven times a run.
        with (
            mock.patch.object(localserver, "_servers", None),
            mock.patch("server.tests.localserver.subprocess.Popen") as popen,
            mock.patch.object(localserver, "wait_server_start"),
            mock.patch.object(localserver, "set_up_django"),
            mock.patch("server.tests.localserver.atexit.register") as at_exit,
        ):
            popen.return_value.poll.return_value = None  # still running
            for _ in range(3):
                with localserver.running_test_server():
                    pass
        self.assertEqual(2, popen.call_count)  # Django and webpack, once each
        at_exit.assert_called_once()

    def test_servers_that_fail_to_start_are_stopped(self) -> None:
        # Or they keep their ports, and every later run fails to start.
        with (
            mock.patch.object(localserver, "_servers", None),
            mock.patch("server.tests.localserver.subprocess.Popen") as popen,
            mock.patch.object(localserver, "wait_server_start", side_effect=TimeoutError),
            mock.patch.object(localserver, "set_up_django"),
            self.assertRaises(TimeoutError),
            localserver.running_test_server(),
        ):
            pass
        self.assertEqual(2, popen.return_value.terminate.call_count)
