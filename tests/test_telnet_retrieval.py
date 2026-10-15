import socketserver
import threading
import unittest
from unittest.mock import MagicMock, patch

import requests

from main import ModemManager

CONFIG_COMMAND = b"cat /flash/cfg/agentconf/factory.conf\n"
FACTORY_COMMAND = b"load_cli factory\n"
USERNAME_COMMAND = (
    b"cfg_cmd get InternetGatewayDevice.DeviceInfo.X_CMCC_TeleComAccount.Username\n"
)
PASSWORD_COMMAND = (
    b"cfg_cmd get InternetGatewayDevice.DeviceInfo.X_CMCC_TeleComAccount.Password\n"
)


def telnet_session(
    responses=None, login_prompt=b"Login: ", login_result=b"$ ", failure=None
):
    responses = responses or {}
    session = MagicMock()
    session.__enter__.return_value = session
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
            if failure is not None:
                raise failure
            result = responses.get(writes[-1], b"Unknown command\r\n# ")
        for index, pattern in enumerate(patterns):
            match = pattern.search(result)
            if match:
                return index, match, result
        return -1, None, result

    session.expect.side_effect = expect
    return session


class TelnetGateTests(unittest.TestCase):
    def setUp(self):
        self.manager = ModemManager()
        self.manager.host = "192.168.1.1"
        self.manager.mac_address = "AABBCCDDEEFF"

    def test_http_200_and_open_port_allow_retrieval_regardless_of_body(self):
        for body in ("", "unexpected page", "if (1 == 1)", "telnet开启"):
            with (
                self.subTest(body=body),
                patch(
                    "main.requests.get",
                    return_value=MagicMock(status_code=200, text=body),
                ) as request,
                patch("main.socket.create_connection") as connect,
                patch.object(
                    self.manager,
                    "get_admin_password",
                    return_value=("account", "secret"),
                ) as retrieve,
            ):
                self.assertEqual(self.manager.manage_modem(), ("account", "secret"))
                request.assert_called_once()
                self.assertIn("key=AABBCCDDEEFF", request.call_args.args[0])
                self.assertGreater(request.call_args.kwargs["timeout"], 0)
                connect.assert_called_once()
                self.assertEqual(connect.call_args.args[0], (self.manager.host, 23))
                self.assertGreater(connect.call_args.kwargs["timeout"], 0)
                connect.return_value.__exit__.assert_called_once()
                retrieve.assert_called_once()

    def test_non_200_stops_before_connecting_or_retrieving(self):
        for status in (204, 302, 401, 500):
            with (
                self.subTest(status=status),
                patch(
                    "main.requests.get",
                    return_value=MagicMock(status_code=status, text="telnet开启"),
                ),
                patch("main.socket.create_connection") as connect,
                patch.object(self.manager, "get_admin_password") as retrieve,
            ):
                self.assertFalse(self.manager.manage_modem())
                connect.assert_not_called()
                retrieve.assert_not_called()

    def test_http_failure_stops_before_connecting_or_retrieving(self):
        with (
            patch("main.requests.get", side_effect=requests.exceptions.Timeout),
            patch("main.socket.create_connection") as connect,
            patch.object(self.manager, "get_admin_password") as retrieve,
        ):
            self.assertFalse(self.manager.manage_modem())
            connect.assert_not_called()
            retrieve.assert_not_called()

    def test_closed_telnet_port_stops_before_retrieval(self):
        with (
            patch("main.requests.get", return_value=MagicMock(status_code=200)),
            patch("main.socket.create_connection", side_effect=ConnectionRefusedError),
            patch.object(self.manager, "get_admin_password") as retrieve,
        ):
            self.assertFalse(self.manager.manage_modem())
            retrieve.assert_not_called()


class TelnetRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.manager = ModemManager()
        self.manager.host = "192.168.1.1"
        self.manager.mac_address = "AABBCCDDEEFF"
        self.success_responses = (
            {CONFIG_COMMAND: b"TelecomAccount=account\r\nTelecomPasswd=p=a#ss\r\n# "},
            {
                FACTORY_COMMAND: b"Config\\factorydir# ",
                b"show admin_pwd\n": b"Success! admin_pwd=p=a#ss\r\nConfig\\factorydir# ",
                b"show admin_name\n": b"Success! admin_name=account\r\nConfig\\factorydir# ",
            },
            {
                USERNAME_COMMAND: b"get success!value=account\r\n# ",
                PASSWORD_COMMAND: b"get success!value=p=a#ss\r\n# ",
            },
        )

    def test_each_username_and_reader_combination_can_succeed_and_stops_attempts(self):
        first_commands = (CONFIG_COMMAND, FACTORY_COMMAND, USERNAME_COMMAND)
        for successful_index in range(6):
            with self.subTest(successful_index=successful_index):
                sessions = [telnet_session() for _ in range(successful_index)]
                sessions.append(
                    telnet_session(self.success_responses[successful_index % 3])
                )
                with patch("main.Telnet", side_effect=sessions) as connect:
                    self.assertEqual(
                        self.manager.get_admin_password(), ("account", "p=a#ss")
                    )
                self.assertEqual(connect.call_count, successful_index + 1)
                for index, session in enumerate(sessions):
                    writes = [call.args[0] for call in session.write.call_args_list]
                    self.assertEqual(writes[0], b"root\n" if index < 3 else b"admin\n")
                    self.assertEqual(writes[1], b"Fh@DDEEFF\n")
                    self.assertEqual(writes[2], first_commands[index % 3])
                    session.__exit__.assert_called_once()
                for call in connect.call_args_list:
                    self.assertGreater(call.kwargs["timeout"], 0)

    def test_rejected_username_is_not_retried_for_each_reader(self):
        rejected = telnet_session(login_result=b"Error!\r\nLogin: ")
        accepted = telnet_session(self.success_responses[0])
        with patch("main.Telnet", side_effect=[rejected, accepted]):
            self.assertEqual(self.manager.get_admin_password(), ("account", "p=a#ss"))
        self.assertEqual(rejected.write.call_count, 2)
        self.assertEqual(accepted.write.call_args_list[0].args[0], b"admin\n")
        rejected.__exit__.assert_called_once()

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
                    self.manager.get_admin_password(), ("account", "p=a#ss")
                )

    def test_command_timeout_or_disconnect_continues_with_a_fresh_session(self):
        for failure in (TimeoutError("timed out"), EOFError(), ConnectionResetError()):
            with self.subTest(failure=type(failure).__name__):
                failed = telnet_session(failure=failure)
                accepted = telnet_session(self.success_responses[1])
                with patch("main.Telnet", side_effect=[failed, accepted]):
                    self.assertEqual(
                        self.manager.get_admin_password(), ("account", "p=a#ss")
                    )
                failed.__exit__.assert_called_once()

    def test_all_unsupported_combinations_return_failure(self):
        sessions = [telnet_session() for _ in range(6)]
        with patch("main.Telnet", side_effect=sessions) as connect:
            self.assertIsNone(self.manager.get_admin_password())
        self.assertEqual(connect.call_count, 6)

    def test_password_only_factory_result_uses_documented_account(self):
        responses = dict(self.success_responses[1])
        del responses[b"show admin_name\n"]
        with patch(
            "main.Telnet", side_effect=[telnet_session(), telnet_session(responses)]
        ):
            self.assertEqual(self.manager.get_admin_password(), ("CMCCAdmin", "p=a#ss"))

    def test_empty_credentials_are_not_accepted(self):
        responses = {
            CONFIG_COMMAND: b"TelecomAccount=account\r\nTelecomPasswd= \r\n# ",
            b"show admin_pwd\n": b"Success! admin_pwd=\r\n# ",
            USERNAME_COMMAND: b"get success!value=account\r\n# ",
            PASSWORD_COMMAND: b"get success!value=\r\n# ",
        }
        with patch(
            "main.Telnet", side_effect=[telnet_session(responses) for _ in range(6)]
        ):
            self.assertIsNone(self.manager.get_admin_password())

    def test_incomplete_login_prompt_never_sends_credentials(self):
        sessions = [
            telnet_session(login_prompt=b"Starting device...") for _ in range(2)
        ]
        with patch("main.Telnet", side_effect=sessions):
            self.assertIsNone(self.manager.get_admin_password())
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
                        if command == FACTORY_COMMAND:
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
                manager = ModemManager()
                manager.host, manager.port = server.server_address
                manager.mac_address = "AABBCCDDEEFF"
                self.assertEqual(manager.get_admin_password(), ("account", "p=a#ss#"))
            finally:
                server.shutdown()
                worker.join(timeout=server_timeout_seconds)

        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(
            [attempt[0] for attempt in attempts], [b"root", b"admin", b"admin"]
        )
        self.assertTrue(all(attempt[1] == b"Fh@DDEEFF" for attempt in attempts))
        self.assertEqual(attempts[0][2], [])
        self.assertEqual(attempts[1][2], [CONFIG_COMMAND])
        self.assertEqual(
            attempts[2][2], [FACTORY_COMMAND, b"show admin_pwd\n", b"show admin_name\n"]
        )


if __name__ == "__main__":
    unittest.main()
