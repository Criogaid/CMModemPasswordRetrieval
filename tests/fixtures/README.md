# Live Telnet regression fixtures

These recordings were collected from one authorized modem using the existing MAC-based password formula. They are device observations, not a compatibility guarantee for other firmware. Password submissions and any returned credential values are replaced with `REDACTED`; no real MAC or password is retained. Terminal echoes, line wrapping, carriage returns, and prompts are preserved.

`modem_telnet.json` contains the initial capture: root login and interactive shell confirmation, a missing file, an unsupported command, cfg_cmd queries, a delayed command, factory CLI queries, session exit, and one rejected admin login. After the command timeout, the initial recovery implementation left an extra prompt in the input stream. The subsequent command and response fields intentionally preserve that mismatch for regression testing.

`modem_telnet_recovered.json` contains the root-only verification after correcting recovery. The client waits for the original command's prompt before sending an empty line and consuming its prompt. Later responses match their commands. The rejected admin login was not repeated.

Each exchange records the login username, probe step, most recent command written, decoded reply, prompt-match status, EOF state, and any transport exception class. The `command_timeout` probe uses a sleep longer than the project's read timeout; it does not change device configuration. The missing-file and unsupported-command probes are read-only. The `exit` probe deliberately closes the session.

On this device, root plus factory.conf retrieved complete credentials in a separate normal-flow check. The recorded cfg_cmd, load_cli, and show commands were unavailable, and admin authentication was rejected. The missing configuration-node probe also stopped at the absent cfg_cmd executable; it does not establish how a supported cfg_cmd handles an unknown node. Successful cfg_cmd and factory CLI replies, missing credential fields, and an unresponsive session remain covered by synthetic tests.
