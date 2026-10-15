# 方法二：使用 cfg_cmd 查询

这是用户提供的第二张截图中的查询方式，已纳入仓库代码。它要求固件支持 `cfg_cmd`；现有实机没有该命令，尚未在这台设备上验证成功。开始前先完成[连接与登录步骤](README.md)，确认处于普通命令行。

## 操作步骤

先查询账号：

```sh
cfg_cmd get InternetGatewayDevice.DeviceInfo.X_CMCC_TeleComAccount.Username
```

等待提示符重新出现，再查询密码：

```sh
cfg_cmd get InternetGatewayDevice.DeviceInfo.X_CMCC_TeleComAccount.Password
```

两条命令会分别返回结果。下面是虚构示例：

```text
get success!value=CMCCAdmin
```

```text
get success!value=ExamplePass123#
```

第一条查询的 `get success!value=` 后面是账号，第二条查询的同一标记后面是密码。复制时只取标记后面的完整值，不包含标记本身。

截图中即使出现 `FHAPI_INIT Error!`，后面仍可能返回有效字段。因此应分别检查两次查询是否返回非空值，不能只凭某句报错判断成功或失败。

## 没有取得完整结果时

命令不存在、查询没有返回值，或只有账号、密码其中一项时，等命令结束后继续[方法三：工厂命令行](factory-cli.md)。保持当前连接，不要为了换查询方法重新登录。

原截图先尝试工厂命令行，再使用 `exit` 后执行本方法。本教程把 `cfg_cmd` 放在工厂命令行之前，无需输入这条 `exit`。不要在普通命令行盲目输入 `exit`，它可能直接关闭 Telnet 会话。

如果你已经进入工厂模式，只有确认已经返回普通命令行后才能执行本页命令；无法确认当前模式时不要继续混用命令。超时、断开及操作结束后的处理见[连接指南](README.md)。

## 来源

根据用户提供的第二张教程截图与[仓库代码](../main.py)整理。截图展示了命令和返回值，但未提供可核对的原作者或原文链接；这里重新编写步骤，不收录截图中的凭据。项目署名与许可见[教程首页](README.md)。
