# CMModemPasswordRetrieval

这是一个用于获取中国移动光猫超级管理员账户 `CMCCAdmin` 密码的 Windows 命令行工具。项目适用于部分 HG 系列光猫，已在 HG6821M 和 HG6042A1 上测试。

仅可在自己拥有或已获授权管理的设备上使用本工具。

感谢 [marcos1](https://github.com/Criogaid/CMModemPasswordRetrieval/pull/3) 完善了获取方式，并且已于HG6042A1上进行了测试。

**原作者：** [布束砥信](https://space.bilibili.com/521361612)  
**出处：** [bilibili](https://www.bilibili.com/read/cv21044770)

我们欢迎任何形式的贡献，包括但不限于提交问题、改进代码、提供文档等。感谢您对CMModemPasswordRetrieval项目的支持。

感谢[YxVM](https://yxvm.com/register?ref=W717)提供的服务器支持，使我能够在旅行期间顺利进行远程开发工作。

[![YxVM](assets/yxvm.png)](https://yxvm.com/register?ref=W717)

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

输入光猫的 IPv4 地址，或直接回车，依次自动检查 `192.168.0.1`、`192.168.1.1`，使用第一个能连接且能获取 MAC 的地址。手动输入地址时只检查该地址；复用已保存配置时跳过地址探测。

## 手动教程

不使用脚本时，可按 [手动连接指南](docs/README.md) 登录光猫，再依次尝试 [读取 factory.conf](docs/factory-conf.md)、[cfg_cmd 查询](docs/cfg-cmd.md) 和 [工厂命令行查询](docs/factory-cli.md)。取得完整账号和密码后即可停止。

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

程序会检查光猫是否可达，并自动获取 MAC，无需手动填写。自动探测时，一个地址不可用就检查下一个；两个地址都不可用则停止。选定设备后，后续尝试都只针对该设备。

### 获取密码

程序先请求开启 Telnet，确认收到 HTTP 200 响应且 Telnet 端口能连接后，才开始登录。任一步失败都会停止。

程序依次尝试 `root` 和 `admin`，密码均为 `Fh@` 加 MAC 地址的后六位大写字符。每次运行中，每个用户名最多登录一次。登录并确认命令行能正常交互后，在同一连接内依次尝试读取 `factory.conf`、使用 `cfg_cmd` 查询、进入工厂命令行查询，无需手动选择方案。取得完整账号和密码后立即停止尝试。

是否成功以实际读到的账号和密码为准，不依赖固件的报错文字。一种方法未取得完整结果时会继续尝试；若最终只取得部分信息，会显示已有内容并标明缺失项，不猜测账号，也不拼接不同方法或连接的结果。

命令响应超时后，程序会短暂等待并检查连接是否仍可交互；恢复后继续尝试，但不会采用不完整的响应。连接断开或无法恢复时，会结束当前连接并尝试下一个用户名，不重复登录同一用户。

成功后，程序会显示凭据，并询问是否保存当前 IP 和 MAC 供下次直接使用。失败时会立即退出，不保存配置。

## 调试与安全

终端日志可能包含设备 MAC、登录密码和超级管理员账号密码。分享日志或截图前，请遮盖这些信息。

`CMCCModelConfig.json` 已加入 `.gitignore`，不要提交真实设备配置或凭据。程序启用 Telnet 后不会自动关闭该服务；完成操作后应按设备管理要求关闭 Telnet 或重启光猫。

## 测试

```powershell
python -m unittest discover -s tests -v
python -m pytest -q
```

自动化测试无需连接真实光猫，覆盖连接失败、命令不支持、超时和断开等情况。

## 许可证

<p align="center">
  <img src="http://mirrors.creativecommons.org/presskit/buttons/88x31/png/by-nc-sa.png" />
</p>

本项目遵循互联网的开放、自由、共享的原则，采用[CC BY-NC-SA 4.0 许可协议](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans) 进行授权。

如需转载或引用本项目，请务必遵守许可协议的条款。在您的文章或项目开头部分，必须注明原作者、标注原项目链接，并以同样的方式，即CC BY-NC-SA 4.0许可协议，分享您的作品。

任何不遵循 CC BY-NC-SA 4.0 许可协议进行分发的行为，将被视为侵权。
