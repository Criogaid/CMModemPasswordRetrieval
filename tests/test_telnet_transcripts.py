import json
import unittest
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

from main import (
    SHELL_PROMPT,
    Credentials,
    ModemManager,
    read_cfg_cmd,
    read_factory_cli,
    read_telnet_response,
    run_telnet_command,
)


@dataclass(frozen=True)
class Exchange:
    username: str
    step: str
    command: str
    response: str
    matched: bool
    eof: bool
    error: str


def load_recording(name: str) -> tuple[Exchange, ...]:
    with (Path(__file__).parent / "fixtures" / name).open(encoding="utf-8") as fixture:
        return tuple(Exchange(**entry) for entry in json.load(fixture))


EXCHANGES = load_recording("modem_telnet.json")
RECOVERED_EXCHANGES = load_recording("modem_telnet_recovered.json")


def replay_session(exchanges):
    pending = deque(exchanges)
    session = MagicMock()
    session.__enter__.return_value = session
    session.eof = False

    def expect(patterns, timeout):
        exchange = pending.popleft()
        session.eof = exchange.eof
        data = exchange.response.encode("utf-8")
        for index, pattern in enumerate(patterns):
            match = pattern.search(data)
            if match:
                return index, match, data
        return -1, None, data

    session.expect.side_effect = expect
    return session


class RealTranscriptTests(unittest.TestCase):
    def test_missing_file_and_unsupported_queries_complete_without_credentials(self):
        for exchange in EXCHANGES:
            if exchange.step not in (
                "missing_file",
                "unsupported_command",
                "missing_cfg_value",
            ):
                continue
            with self.subTest(step=exchange.step):
                session = replay_session([exchange])
                response = run_telnet_command(
                    session, exchange.command.rstrip("\n").encode("ascii")
                )
                self.assertEqual(response, exchange.response)
                session.write.assert_called_once()

    def test_real_unsupported_readers_do_not_require_unknown_command_wording(self):
        cfg_replies = [
            entry for entry in RECOVERED_EXCHANGES if entry.step == "cfg_cmd"
        ]
        factory_replies = [
            entry for entry in RECOVERED_EXCHANGES if entry.step == "factory_cli"
        ]
        for reader, replies in (
            (read_cfg_cmd, cfg_replies),
            (read_factory_cli, factory_replies),
        ):
            with self.subTest(reader=reader.__name__):
                self.assertEqual(reader(replay_session(replies)), Credentials("", ""))

    def test_actual_admin_rejection_stops_after_one_password_submission(self):
        root = replay_session(EXCHANGES[:4])
        admin = replay_session(
            [entry for entry in EXCHANGES if entry.username == "admin"]
        )
        manager = ModemManager()
        manager.host = "192.168.0.1"
        manager.mac_address = "AABBCCDDEEFF"
        with (
            patch("main.Telnet", side_effect=[root, admin]) as connect,
            patch("main.read_factory_config", return_value=Credentials("", "")),
            patch("main.read_cfg_cmd", return_value=Credentials("", "")),
            patch("main.read_factory_cli", return_value=Credentials("", "")),
        ):
            self.assertIsNone(manager.get_admin_password())
        self.assertEqual(connect.call_count, 2)
        self.assertEqual(
            [call.args[0] for call in admin.write.call_args_list],
            [b"admin\n", b"Fh@DDEEFF\n"],
        )
        admin.__exit__.assert_called_once()

    def test_actual_exit_is_a_disconnect_and_does_not_send_recovery_input(self):
        exchange = next(entry for entry in EXCHANGES if entry.eof)
        session = replay_session([exchange])
        with self.assertRaises(EOFError):
            run_telnet_command(session, b"exit")
        session.write.assert_called_once_with(b"exit\n")

    def test_timeout_recovery_consumes_original_and_blank_line_prompts(self):
        timed_out, original_prompt = [
            entry for entry in EXCHANGES if entry.step == "command_timeout"
        ]
        blank_prompt = next(
            entry for entry in EXCHANGES if entry.step == "post_timeout"
        )
        next_reply = next(
            entry for entry in EXCHANGES if entry.step == "unsupported_command"
        )
        pending = deque()
        session = MagicMock()
        session.eof = False

        def write(command):
            if command == timed_out.command.encode("ascii"):
                pending.extend((timed_out, original_prompt))
            elif command == b"\n":
                pending.append(blank_prompt)
            elif command == next_reply.command.encode("ascii"):
                pending.append(next_reply)
            else:
                raise AssertionError(f"Unexpected command: {command!r}")

        def expect(patterns, timeout):
            data = pending.popleft().response.encode("utf-8")
            match = patterns[0].search(data)
            return (0 if match else -1), match, data

        session.write.side_effect = write
        session.expect.side_effect = expect
        self.assertEqual(
            run_telnet_command(session, timed_out.command.rstrip("\n").encode("ascii")),
            "",
        )
        response = run_telnet_command(
            session, next_reply.command.rstrip("\n").encode("ascii")
        )
        self.assertEqual(response, next_reply.response)
        self.assertEqual(len(pending), 0)

    def test_recovered_device_recording_keeps_next_response_aligned(self):
        exchanges = [
            entry
            for entry in RECOVERED_EXCHANGES
            if entry.step in ("command_timeout", "post_timeout")
        ]
        session = replay_session(exchanges)
        self.assertEqual(
            run_telnet_command(
                session, exchanges[0].command.rstrip("\n").encode("ascii")
            ),
            "",
        )
        result = run_telnet_command(
            session, exchanges[-1].command.rstrip("\n").encode("ascii")
        )
        self.assertEqual(result, exchanges[-1].response)
        self.assertEqual(session.expect.call_count, len(exchanges))

    def test_partial_exit_response_is_logged_before_eof(self):
        exchange = next(entry for entry in EXCHANGES if entry.eof)
        with patch("main.logger.debug") as log, self.assertRaises(EOFError):
            read_telnet_response(replay_session([exchange]), SHELL_PROMPT)
        self.assertIn(exchange.response, log.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
