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

程序会提示输入光猫 IPv4 地址，默认值为 `192.168.0.1`。

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

未复用配置时，程序按以下顺序检查目标：

1. 校验 IPv4 地址格式。
2. 发送一次 ping；如果没有响应，则尝试建立 TCP 80 连接。
3. 两种方式都失败时立即终止。
4. 读取 Windows ARP 表，要求存在该 IP 对应的有效 MAC。
5. ARP 缺项或格式无效时立即终止，不支持手工输入 MAC。

### 获取密码

取得 MAC 后，程序调用光猫的 HTTP 接口启用 Telnet，并根据设备返回结果选择对应的 Telnet 命令流程。登录密码由 `Fh@` 和 MAC 后六位组成，随后从设备配置或厂商 CLI 中读取超级管理员账号和密码。

成功后，程序会显示凭据，并询问是否保存当前 IP 和 MAC 供下次直接使用。失败时会立即退出，不保存配置。

## 调试与安全

程序保留完整 ARP 和 Telnet 调试输出，其中可能包含设备 MAC、Telnet 登录密码和管理员凭据。分享终端日志、录屏或截图前必须先脱敏。

`CMCCModelConfig.json` 已加入 `.gitignore`，不要提交真实设备配置或凭据。程序启用 Telnet 后不会自动关闭该服务；完成操作后应按设备管理要求关闭 Telnet 或重启光猫。

## 测试

```powershell
python -m unittest discover -s tests -v
python -m pytest -q
```

自动化测试会模拟网络、ARP、Telnet 和交互输入，不需要连接真实光猫。

## 许可证

<p align="center">
  <img src="http://mirrors.creativecommons.org/presskit/buttons/88x31/png/by-nc-sa.png" />
</p>

本项目遵循互联网的开放、自由、共享的原则，采用[CC BY-NC-SA 4.0 许可协议](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans) 进行授权。

如需转载或引用本项目，请务必遵守许可协议的条款。在您的文章或项目开头部分，必须注明原作者、标注原项目链接，并以同样的方式，即CC BY-NC-SA 4.0许可协议，分享您的作品。

任何不遵循 CC BY-NC-SA 4.0 许可协议进行分发的行为，将被视为侵权。
