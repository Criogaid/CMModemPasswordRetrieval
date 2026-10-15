import socketserver
import threading
import unittest
from unittest.mock import MagicMock, patch

import requests

from main import Credentials, get_admin_credentials, retrieve_credentials

CONFIG_COMMAND = b"cat /flash/cfg/agentconf/factory.conf\n"
FACTORY_COMMAND = b"load_cli factory\n"
USERNAME_COMMAND = (
    b"cfg_cmd get InternetGatewayDevice.DeviceInfo.X_CMCC_TeleComAccount.Username\n"
)
PASSWORD_COMMAND = (
    b"cfg_cmd get InternetGatewayDevice.DeviceInfo.X_CMCC_TeleComAccount.Password\n"
)


def telnet_session(responses=None, login_prompt=b"Login: ", login_result=b"$ "):
    responses = {
        command: list(result) if isinstance(result, list) else result
        for command, result in (responses or {}).items()
    }
    session = MagicMock()
    session.__enter__.return_value = session
    session.eof = False
    writes = []
    session.write.side_effect = writes.append

    def expect(patterns, timeout):
        if timeout is None or timeout <= 0:
            raise AssertionError("Telnet reads must have a finite positive timeout")
        if not writes:
            result = login_prompt
        elif len(writes) == 1:
            result = b"Password: "
        elif len(writes) == 2:
            result = login_result
        else:
            default = b"# " if writes[-1] == b"\n" else b"operation unavailable\r\n# "
            result = responses.get(writes[-1], default)
            if isinstance(result, list):
                result = result.pop(0)
            if isinstance(result, Exception):
                raise result
        for index, pattern in enumerate(patterns):
            match = pattern.search(result)
            if match:
                return index, match, result
        return -1, None, result

    session.expect.side_effect = expect
    return session


class TelnetGateTests(unittest.TestCase):
    def setUp(self):
        self.host = "192.168.1.1"
        self.mac_address = "AABBCCDDEEFF"

    def test_http_200_and_open_port_allow_retrieval_regardless_of_body(self):
        telnet_port = 2323
        for body in ("", "unexpected page", "if (1 == 1)", "telnet开启"):
            with (
                self.subTest(body=body),
                patch(
                    "main.requests.get",
                    return_value=MagicMock(status_code=200, text=body),
                ) as request,
                patch("main.socket.create_connection") as connect,
                patch(
                    "main.get_admin_credentials",
                    return_value=Credentials("account", "secret"),
                ) as retrieve,
            ):
                self.assertEqual(
                    retrieve_credentials(self.host, self.mac_address, telnet_port),
                    Credentials("account", "secret"),
                )
                request.assert_called_once()
                self.assertIn("key=AABBCCDDEEFF", request.call_args.args[0])
                self.assertGreater(request.call_args.kwargs["timeout"], 0)
                connect.assert_called_once()
                self.assertEqual(connect.call_args.args[0], (self.host, telnet_port))
                self.assertGreater(connect.call_args.kwargs["timeout"], 0)
                connect.return_value.__exit__.assert_called_once()
                retrieve.assert_called_once_with(
                    self.host, self.mac_address, telnet_port
                )

    def test_non_200_stops_before_connecting_or_retrieving(self):
        for status in (204, 302, 401, 500):
            with (
                self.subTest(status=status),
                patch(
                    "main.requests.get",
                    return_value=MagicMock(status_code=status, text="telnet开启"),
                ),
                patch("main.socket.create_connection") as connect,
                patch("main.get_admin_credentials") as retrieve,
            ):
                self.assertFalse(retrieve_credentials(self.host, self.mac_address))
                connect.assert_not_called()
                retrieve.assert_not_called()

    def test_http_failure_stops_before_connecting_or_retrieving(self):
        with (
            patch("main.requests.get", side_effect=requests.exceptions.Timeout),
            patch("main.socket.create_connection") as connect,
            patch("main.get_admin_credentials") as retrieve,
        ):
            self.assertFalse(retrieve_credentials(self.host, self.mac_address))
            connect.assert_not_called()
            retrieve.assert_not_called()

    def test_closed_telnet_port_stops_before_retrieval(self):
        with (
            patch("main.requests.get", return_value=MagicMock(status_code=200)),
            patch("main.socket.create_connection", side_effect=ConnectionRefusedError),
            patch("main.get_admin_credentials") as retrieve,
        ):
            self.assertFalse(retrieve_credentials(self.host, self.mac_address))
            retrieve.assert_not_called()


class TelnetRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.host = "192.168.1.1"
        self.mac_address = "AABBCCDDEEFF"
        self.success_responses = (
            {CONFIG_COMMAND: b"TelecomAccount=account\r\nTelecomPasswd=p=a#ss\r\n# "},
            {
                USERNAME_COMMAND: b"FHAPI_INIT Error!\r\nget success!value=account\r\n# ",
                PASSWORD_COMMAND: b"get success!value=p=a#ss\r\n# ",
            },
            {
                FACTORY_COMMAND: b"Config\\factorydir# ",
                b"show admin_pwd\n": b"Success! admin_pwd=p=a#ss\r\nConfig\\factorydir# ",
                b"show admin_name\n": b"Success! admin_name=account\r\nConfig\\factorydir# ",
            },
        )

    def test_each_reader_reuses_one_authenticated_and_confirmed_session(self):
        commands_by_reader = (
            [CONFIG_COMMAND],
            [CONFIG_COMMAND, USERNAME_COMMAND, PASSWORD_COMMAND],
            [
                CONFIG_COMMAND,
                USERNAME_COMMAND,
                PASSWORD_COMMAND,
                FACTORY_COMMAND,
                b"show admin_name\n",
                b"show admin_pwd\n",
            ],
        )
        for username in (b"root\n", b"admin\n"):
            for reader_index, responses in enumerate(self.success_responses):
                with self.subTest(username=username, reader=reader_index):
                    accepted = telnet_session(responses)
                    sessions = (
                        []
                        if username == b"root\n"
                        else [telnet_session(login_result=b"Login: ")]
                    )
                    sessions.append(accepted)
                    with patch("main.Telnet", side_effect=sessions) as connect:
                        self.assertEqual(
                            get_admin_credentials(self.host, self.mac_address),
                            Credentials("account", "p=a#ss"),
                        )
                    self.assertEqual(connect.call_count, len(sessions))
                    writes = [call.args[0] for call in accepted.write.call_args_list]
                    self.assertEqual(
                        writes,
                        [username, b"Fh@DDEEFF\n", b"\n"]
                        + commands_by_reader[reader_index],
                    )
                    for session in sessions:
                        session.__exit__.assert_called_once()
                    for call in connect.call_args_list:
                        self.assertGreater(call.kwargs["timeout"], 0)

    def test_rejected_username_is_not_retried_for_each_reader(self):
        rejected = telnet_session(login_result=b"Error!\r\nLogin: ")
        accepted = telnet_session(self.success_responses[0])
        with patch("main.Telnet", side_effect=[rejected, accepted]):
            self.assertEqual(
                get_admin_credentials(self.host, self.mac_address),
                Credentials("account", "p=a#ss"),
            )
        self.assertEqual(rejected.write.call_count, 2)
        self.assertEqual(accepted.write.call_args_list[0].args[0], b"admin\n")

    def test_login_prompt_variants(self):
        for prompt in (b"Login:", b"login: ", b"(none) login: "):
            with (
                self.subTest(prompt=prompt),
                patch(
                    "main.Telnet",
                    return_value=telnet_session(
                        self.success_responses[0], login_prompt=prompt
                    ),
                ),
            ):
                self.assertEqual(
                    get_admin_credentials(self.host, self.mac_address),
                    Credentials("account", "p=a#ss"),
                )

    def test_cli_must_respond_to_blank_line_before_queries(self):
        sessions = [telnet_session({b"\n": b""}) for _ in range(2)]
        with patch("main.Telnet", side_effect=sessions):
            self.assertIsNone(get_admin_credentials(self.host, self.mac_address))
        for session in sessions:
            writes = [call.args[0] for call in session.write.call_args_list]
            self.assertEqual(len(writes), 3)
            self.assertEqual(writes[-1], b"\n")

    def test_command_timeout_recovers_once_and_continues_without_login(self):
        responses = dict(self.success_responses[1])
        responses[CONFIG_COMMAND] = [b"TelecomAccount=truncated", b"\r\n# "]
        session = telnet_session(responses)
        with patch("main.Telnet", return_value=session) as connect:
            self.assertEqual(
                get_admin_credentials(self.host, self.mac_address),
                Credentials("account", "p=a#ss"),
            )
        connect.assert_called_once()
        writes = [call.args[0] for call in session.write.call_args_list]
        self.assertEqual(
            writes,
            [
                b"root\n",
                b"Fh@DDEEFF\n",
                b"\n",
                CONFIG_COMMAND,
                b"\n",
                USERNAME_COMMAND,
                PASSWORD_COMMAND,
            ],
        )

    def test_unrecoverable_timeout_or_disconnect_moves_to_next_username(self):
        for failure in (b"", EOFError(), ConnectionResetError()):
            with self.subTest(failure=failure):
                failed = telnet_session({CONFIG_COMMAND: failure, b"\n": [b"# ", b""]})
                accepted = telnet_session(self.success_responses[0])
                with patch("main.Telnet", side_effect=[failed, accepted]) as connect:
                    self.assertEqual(
                        get_admin_credentials(self.host, self.mac_address),
                        Credentials("account", "p=a#ss"),
                    )
                self.assertEqual(connect.call_count, 2)
                self.assertEqual(accepted.write.call_args_list[0].args[0], b"admin\n")
                writes = [call.args[0] for call in failed.write.call_args_list]
                self.assertNotIn(USERNAME_COMMAND, writes)
                self.assertLessEqual(writes.count(b"\n"), 2)
                failed.__exit__.assert_called_once()

    def test_all_unsupported_readers_use_only_two_logins(self):
        sessions = [telnet_session() for _ in range(2)]
        with patch("main.Telnet", side_effect=sessions) as connect:
            self.assertIsNone(get_admin_credentials(self.host, self.mac_address))
        self.assertEqual(connect.call_count, 2)

    def test_partial_password_is_preserved_without_guessing_account(self):
        responses = dict(self.success_responses[2])
        del responses[b"show admin_name\n"]
        with patch(
            "main.Telnet", side_effect=[telnet_session(responses), telnet_session()]
        ):
            result = get_admin_credentials(self.host, self.mac_address)
        self.assertEqual(result, Credentials("", "p=a#ss"))
        self.assertFalse(result.complete)

    def test_partial_fields_from_different_methods_are_not_combined(self):
        responses = {
            CONFIG_COMMAND: b"TelecomAccount=first-account\r\n# ",
            PASSWORD_COMMAND: b"get success!value=second-password\r\n# ",
        }
        with patch(
            "main.Telnet", side_effect=[telnet_session(responses), telnet_session()]
        ):
            self.assertEqual(
                get_admin_credentials(self.host, self.mac_address),
                Credentials("", "second-password"),
            )

    def test_complete_result_after_partial_result_wins(self):
        responses = dict(self.success_responses[1])
        responses[CONFIG_COMMAND] = b"TelecomPasswd=earlier-password\r\n# "
        with patch("main.Telnet", return_value=telnet_session(responses)) as connect:
            self.assertEqual(
                get_admin_credentials(self.host, self.mac_address),
                Credentials("account", "p=a#ss"),
            )
        connect.assert_called_once()

    def test_empty_fields_are_not_accepted(self):
        responses = {
            CONFIG_COMMAND: b"TelecomAccount= \r\nTelecomPasswd= \r\n# ",
            b"show admin_pwd\n": b"Success! admin_pwd=\r\n# ",
            USERNAME_COMMAND: b"get success!value=\r\n# ",
            PASSWORD_COMMAND: b"get success!value=\r\n# ",
        }
        with patch(
            "main.Telnet", side_effect=[telnet_session(responses) for _ in range(2)]
        ):
            self.assertIsNone(get_admin_credentials(self.host, self.mac_address))

    def test_incomplete_login_prompt_never_sends_credentials(self):
        sessions = [
            telnet_session(login_prompt=b"Starting device...") for _ in range(2)
        ]
        with patch("main.Telnet", side_effect=sessions):
            self.assertIsNone(get_admin_credentials(self.host, self.mac_address))
        for session in sessions:
            session.write.assert_not_called()
            session.__exit__.assert_called_once()


class TelnetSocketTests(unittest.TestCase):
    def test_real_sessions_switch_login_and_reader_and_preserve_password(self):
        attempts = []
        errors = []
        server_timeout_seconds = 2

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(server_timeout_seconds)
                try:
                    self.wfile.write(b"Login: ")
                    username = self.rfile.readline().strip()
                    self.wfile.write(b"Password: ")
                    password = self.rfile.readline().strip()
                    commands = []
                    attempts.append((username, password, commands))
                    if username == b"root":
                        self.wfile.write(b"Error!\r\n")
                        return
                    self.wfile.write(b"$ ")
                    while command := self.rfile.readline():
                        commands.append(command)
                        if command == b"\n":
                            response = b"$ "
                        elif command == FACTORY_COMMAND:
                            response = b"Config\\factorydir# "
                        elif command == b"show admin_pwd\n":
                            response = (
                                b"Success! admin_pwd=p=a#ss#\r\nConfig\\factorydir# "
                            )
                        elif command == b"show admin_name\n":
                            response = (
                                b"Success! admin_name=account\r\nConfig\\factorydir# "
                            )
                        else:
                            response = b"Unknown command\r\n$ "
                        self.wfile.write(response)
                except OSError as error:
                    errors.append(error)

        with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
            worker = threading.Thread(
                target=server.serve_forever, kwargs={"poll_interval": 0.01}
            )
            worker.start()
            try:
                host, port = server.server_address
                self.assertEqual(
                    get_admin_credentials(host, "AABBCCDDEEFF", port),
                    Credentials("account", "p=a#ss#"),
                )
            finally:
                server.shutdown()
                worker.join(timeout=server_timeout_seconds)

        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual([attempt[0] for attempt in attempts], [b"root", b"admin"])
        self.assertTrue(all(attempt[1] == b"Fh@DDEEFF" for attempt in attempts))
        self.assertEqual(attempts[0][2], [])
        self.assertEqual(
            attempts[1][2],
            [
                b"\n",
                CONFIG_COMMAND,
                USERNAME_COMMAND,
                PASSWORD_COMMAND,
                FACTORY_COMMAND,
                b"show admin_name\n",
                b"show admin_pwd\n",
            ],
        )


if __name__ == "__main__":
    unittest.main()
