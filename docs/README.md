# 手动获取光猫超级管理员账号和密码

仅可在自己拥有或已获授权管理的设备上操作。以下步骤面向 Windows 10/11，适用于部分中国移动 HG 系列光猫；同一型号的不同固件也可能有差异。

原作者：[布束砥信](https://space.bilibili.com/521361612)；原出处：[B 站专栏](https://www.bilibili.com/read/cv21044770/)；整理项目：[CMModemPasswordRetrieval](https://github.com/Criogaid/CMModemPasswordRetrieval)。原帖已无法访问，此处按[仓库代码](../main.py)和 [marcos1 的 PR #3](https://github.com/Criogaid/CMModemPasswordRetrieval/pull/3) 整理操作步骤，并非原文备份。本文沿用项目的 [CC BY-NC-SA 4.0 许可协议](../LICENSE)，转载请保留署名、来源和相同许可。

## 先连接，再选择读取方法

先完成本页的连接步骤，再按下列顺序尝试。每种方法都在已登录的 Telnet 窗口内操作，取得完整账号和密码后即可结束。

| 教程 | 使用条件 | 已有依据 |
| --- | --- | --- |
| [方法一：读取 factory.conf](factory-conf.md) | 普通命令行能读取配置文件 | 仓库原有方式；现有实机已通过 `root` 读取成功 |
| [方法二：使用 cfg_cmd 查询](cfg-cmd.md) | 普通命令行支持 `cfg_cmd` | [仓库代码](../main.py)中的查询方式；现有实机不支持该命令 |
| [方法三：使用工厂命令行查询](factory-cli.md) | 支持 `load_cli factory` 和 `show` 查询 | [PR #3](https://github.com/Criogaid/CMModemPasswordRetrieval/pull/3) 报告在重庆移动 HG6042A1 上使用；现有实机不支持 |

工厂命令行放在最后，避免后续命令因所处模式不同而无法执行。三种方法不固定绑定某个 Telnet 用户名。

## 1. 确认光猫地址和 MAC

将电脑接到光猫的局域网，优先使用网线。先在浏览器打开光猫管理地址，常见为 `http://192.168.0.1` 或 `http://192.168.1.1`；以实际设备为准。如果电脑接在另一个路由器后面，默认网关可能是路由器，需要先确认目标确实是光猫。

以下以 `192.168.0.1` 为例。打开命令提示符，执行：

```bat
ping -n 1 192.168.0.1
arp -a
```

在 ARP 表中找到 IP **恰好为 `192.168.0.1`** 的那一行，记下物理地址。不要取电脑自身或其他设备的 MAC。如果 ping 无响应但管理页面能打开，仍可继续查看 ARP；找不到目标条目时先检查连接和地址。

将 MAC 中的 `-` 或 `:` 去掉，字母改成大写。例如，假设物理地址为 `aa-bb-cc-dd-ee-ff`：

| 用途 | 示例值 |
| --- | --- |
| 开启 Telnet 时使用的完整 MAC | `AABBCCDDEEFF` |
| MAC 后六位 | `DDEEFF` |
| Telnet 登录密码 | `Fh@DDEEFF` |

这些只是示例，必须换成自己的设备数据。Telnet 登录密码和稍后读取的网页超级管理员密码是两回事。

## 2. 开启并检查 Telnet

在浏览器按 F12 打开开发者工具，切到“网络”，然后在地址栏访问下面的地址。访问前，替换其中的 IP 和 `key=` 后的完整 MAC：

```text
http://192.168.0.1/cgi-bin/telnetenable.cgi?telnetenable=1&key=AABBCCDDEEFF
```

在网络记录中找到这条 `telnetenable.cgi` 请求，确认它本身的状态码为 **200**；不要把重定向后的登录页 200 当成成功。页面是否显示“telnet开启”不能代替连接检查。

接着在 Windows PowerShell 中执行：

```powershell
Test-NetConnection -ComputerName 192.168.0.1 -Port 23
```

只有 `TcpTestSucceeded : True` 才继续。若开启请求不是 200，或端口无法连接，先停止，检查地址、MAC 和固件是否支持该接口，无需尝试用户名和读取命令。

## 3. 登录并确认可以交互

如果系统没有 `telnet` 命令，按 `Win + R`，输入 `optionalfeatures`，在“启用或关闭 Windows 功能”中勾选“Telnet 客户端”并确认。安装可能需要管理员权限。

在命令提示符中执行：

```bat
telnet 192.168.0.1 23
```

出现 `login:` 后输入 `root`；出现 `Password:` 后输入 `Fh@` 加 MAC 后六位大写字符。输入密码时通常不会显示字符。

登录后通常会出现以 `#`、`$` 或 `>` 结尾的提示符。先空按一次回车，确认能再次出现提示符，再进入读取教程。仅仅看到欢迎文字不代表命令行已经可用。

如果 `root` 被拒绝，可以尝试一次 `admin`，密码公式相同。每个用户名在本轮操作中最多尝试一次；固件的失败次数限制和锁定时间不明，反复重跑并不会保证计数清零。设备提示锁定或尝试过多时立即停止，不要通过反复连接继续试密码。

登录成功后，优先在同一连接中尝试三种读取方法。若当前用户的三种方法均未取得完整结果，再考虑尚未尝试的另一个用户名；不要为了换方法重复登录。连接断开后也不要反复重试已经用过的用户名。

## 4. 读取、判断结果和结束操作

从[方法一](factory-conf.md)开始，每条命令执行完都要等提示符重新出现，再输入下一条。不要把窗口里的 `#`、`$` 或 `Config\factorydir#` 一起复制为命令。

遇到迟迟不返回的命令，先等待原命令结束；不要连续按回车或粘贴下一组命令。原提示符回来后，可空按一次回车确认仍能交互，再尝试下一种方法；不采用不完整的输出。若一直没有响应，结束当前连接。

是否成功以同一种方法实际返回的非空账号和密码为准，不依赖 `Unknown command` 等报错措辞。只读到密码时，账号仍未确认；不要默认补成 `CMCCAdmin`，也不要拼接不同方法的结果。教程中的输出均为虚构示例。

取得完整结果后，在光猫管理页面使用读取到的账号和密码登录。复制密码时保留其中的 `#`、`=` 等字符，不包含输出字段名前缀或下一行的提示符，不额外添加 `CMCCAdmin`。

使用 Windows Telnet 客户端时，可按 `Ctrl + ]` 返回本地 `Microsoft Telnet>` 提示符，再输入 `quit` 结束连接。这个操作只关闭客户端连接，不会关闭光猫的 Telnet 服务；完成后应通过设备支持的管理方式关闭 Telnet，并确认端口不再可连接。分享截图或日志前遮盖账号、密码和 MAC。

Windows 命令参考：[Telnet](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/telnet)、[Test-NetConnection](https://learn.microsoft.com/en-us/powershell/module/nettcpip/test-netconnection)。
