# CMModemPasswordRetrieval

这是一个用于获取中国移动光猫超级管理员账户 `CMCCAdmin` 密码的 Windows 命令行工具。项目适用于部分 HG 系列光猫，已在 HG6821M 和 HG6042A1 上测试。

仅可在自己拥有或已获授权管理的设备上使用本工具。

感谢 [marcos1](https://github.com/Criogaid/CMModemPasswordRetrieval/pull/3) 完善了获取方式，并且已于HG6042A1上进行了测试。

**原作者：** [布束砥信](https://space.bilibili.com/521361612)  
**出处：** [bilibili](https://www.bilibili.com/read/cv21044770)

我们欢迎任何形式的贡献，包括但不限于提交问题、改进代码、提供文档等。感谢您对CMModemPasswordRetrieval项目的支持。

感谢[YxVM](https://yxvm.com/aff.php?aff=717)提供的服务器支持，使我能够在旅行期间顺利进行远程开发工作。

![yxvm](https://yxvm.com/assets/img/logo.png)

## 环境要求

- Windows 10 或 Windows 11
- Python 3.9 至 Python 3.13
- 电脑与光猫处于可直接访问的本地网络

Python 3.12 及以下使用标准库 `telnetlib`。Python 3.13 已移除该模块，因此依赖文件会仅在 Python 3.13 及以上安装 `telnetlib3`，并加载它提供的同步兼容实现。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 运行

```powershell
python main.py
```

Enter a modem IPv4 address, or press Enter to check `192.168.0.1` first and `192.168.1.1` second. The program selects the first reachable address with a valid MAC in the ARP table and stops if neither qualifies. This order is defined by `DEFAULT_HOSTS` in [main.py](main.py). An explicitly entered address is checked on its own; reusing saved configuration skips address detection.

## 工作流程

### 使用已保存配置

如果脚本目录存在 `CMCCModelConfig.json`，程序会询问是否复用。确认后会校验并直接使用其中保存的 IP 和 MAC，跳过 ping、TCP 80 和 ARP 检查，以便快速重复获取密码。

配置文件格式：

```json
{
  "date": "2026-01-01 00:00:00",
  "host": "192.168.0.1",
  "mac_address": "FFFFFFFFFFFF"
}
```

配置直通模式信任保存的数据。如果更换光猫、修改网络或 MAC 已变化，请拒绝复用配置并重新检测，或者删除该文件。

### 重新检测

Without saved configuration, the program validates an explicitly entered IPv4 address or uses the default candidates described above. For each candidate, it sends one ping and, if that fails, tries TCP port 80. A reachable candidate must also have a valid MAC in the Windows ARP table; manual MAC entry is not supported. In automatic mode, an unreachable candidate or a missing or invalid ARP entry advances to the next address. Once an address and MAC are selected, Telnet checks and credential retrieval run only for that device.

### 获取密码

After obtaining the MAC address, the program requests `/cgi-bin/telnetenable.cgi?telnetenable=1&key=<MAC>`. The response must be HTTP 200; redirects are not followed and the response body is not used to select a retrieval method. It then opens and closes a TCP connection to the Telnet port (23). If either check fails, the program stops before attempting any login or credential query.

The program tries `root`, then `admin`, using `Fh@` followed by the last six uppercase MAC characters as the Telnet password. Each username is authenticated at most once per run. After login, an empty line must produce a new CLI prompt before queries begin. The same session then tries `cat /flash/cfg/agentconf/factory.conf` (`TelecomAccount` and `TelecomPasswd`), `cfg_cmd get InternetGatewayDevice.DeviceInfo.X_CMCC_TeleComAccount.Username` and `.Password`, and finally `load_cli factory` followed by `show admin_name` and `show admin_pwd`. Factory mode runs last so subsequent readers do not depend on exiting it correctly. A complete result stops all further attempts.

A reader succeeds only when its responses contain both a nonempty account and password. Error wording such as `Unknown command` or `FHAPI_INIT Error!` does not control fallback. A completed response without the required fields advances to the next reader. Partial results are retained without guessing an account or combining fields from different readers or sessions. If no complete result is found, any retained fields are displayed with the missing field marked unconfirmed, and the program exits without offering to save configuration. Passwords are taken directly from device output, without adding an account prefix; `cfg_cmd` results exclude the `get success!value=` marker.

Login and password prompts are matched without regard to letter case. Commands wait for a shell or CLI prompt ending in `#`, `$`, or `>` instead of using fixed delays. If a command times out, the program waits once more for that command's prompt, then sends one empty line and consumes its new prompt. This keeps a delayed command response from being mistaken for the next command's output. A recovered session continues without accepting the incomplete response. A failed interaction check or a disconnected session closes that connection and advances to the next username, without logging in again as the same user. HTTP requests, TCP connections, and prompt reads have bounded timeouts defined by `HTTP_TIMEOUT_SECONDS` and `TELNET_TIMEOUT_SECONDS` in [main.py](main.py).

成功后，程序会显示凭据，并询问是否保存当前 IP 和 MAC 供下次直接使用。失败时会立即退出，不保存配置。

## 调试与安全

The program logs complete ARP output and decoded Telnet replies, which can contain device MAC addresses and administrator credentials, including an echoed Telnet password. Redact terminal logs, recordings, and screenshots before sharing them.

`CMCCModelConfig.json` 已加入 `.gitignore`，不要提交真实设备配置或凭据。程序启用 Telnet 后不会自动关闭该服务；完成操作后应按设备管理要求关闭 Telnet 或重启光猫。

## 测试

```powershell
python -m unittest discover -s tests -v
python -m pytest -q
```

Automated tests simulate HTTP, ARP, and Telnet interactions, including a local TCP server and replay of [sanitized device responses](tests/fixtures/README.md). The recordings cover rejected authentication, missing commands and files, delayed prompts, and session exit. They include a regression for an extra prompt left behind during timeout recovery. Tests do not require a physical modem.

## Code structure

The module-level `main()` function handles command-line input, configuration, and output. Device operations receive explicit arguments: `get_mac_address(host)` detects the MAC, and `retrieve_credentials(host, mac_address, port)` runs `enable_telnet()` before `get_admin_credentials()`. Callers supply a validated IPv4 address and normalized MAC; the port defaults to `TELNET_PORT`. Telnet connections remain scoped to their login attempts, and `Credentials` represents complete or partial results.

## 许可证

<p align="center">
  <img src="http://mirrors.creativecommons.org/presskit/buttons/88x31/png/by-nc-sa.png" />
</p>

本项目遵循互联网的开放、自由、共享的原则，采用[CC BY-NC-SA 4.0 许可协议](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans) 进行授权。

如需转载或引用本项目，请务必遵守许可协议的条款。在您的文章或项目开头部分，必须注明原作者、标注原项目链接，并以同样的方式，即CC BY-NC-SA 4.0许可协议，分享您的作品。

任何不遵循 CC BY-NC-SA 4.0 许可协议进行分发的行为，将被视为侵权。
