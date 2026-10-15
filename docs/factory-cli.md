# 方法三：使用工厂命令行查询

这是 [marcos1 的 PR #3](https://github.com/Criogaid/CMModemPasswordRetrieval/pull/3) 和用户提供的两张截图中使用的方式。PR 报告适用于重庆移动 HG6042A1；第一张截图还展示了标为 HG6145F 的示例。不同固件是否支持仍以实际设备为准，现有实机不支持这些命令。

开始前先完成[连接与登录步骤](README.md)。如果正在按顺序尝试前两种方法，继续使用同一 Telnet 连接即可。PR 使用 `admin`，截图也提到部分设备使用 `root`，不要仅凭方法名称决定用户名。

## 操作步骤

先进入工厂命令行：

```sh
load_cli factory
```

等待新提示符出现。截图中的提示符形如 `Config\factorydir#`，实际显示可能不同。空按一次回车，确认还能收到提示符，然后查询账号：

```text
show admin_name
```

等待提示符再次出现，再查询密码：

```text
show admin_pwd
```

下面是虚构的返回示例：

```text
Success! admin_name=CMCCAdmin
Success! admin_pwd=ExamplePass123#
```

`admin_name=` 后面的完整内容是网页超级管理员账号，`admin_pwd=` 后面的完整内容是密码。不要把 `Success!`、字段名或提示符复制进去。

第一张截图只查询了密码，第二张截图补充了账号查询。本教程同时查询两项，避免把 Telnet 用户名或固定的 `CMCCAdmin` 当成已经确认的网页账号。密码是否包含 `CMCCAdmin` 前缀，以设备返回的完整值为准，不自行添加或删除。

## 没有取得完整结果时

如果不能进入工厂命令行，或查询没有返回所需的非空字段，就视为此方法未取得完整结果；无需等待某一种特定的报错文字。

这已经是建议顺序中的最后一种方法。当前用户的三种方法都没有取得完整结果时，可以结束连接，按[连接指南](README.md)尝试尚未使用的另一个用户名；已尝试过两个用户名则停止，不循环重试。只读到一项时保留该项供核对，不猜测另一项，也不与其他方法的结果拼接。

取得完整结果后即可结束。关闭连接的方法见[连接指南](README.md)，无需照搬截图或旧代码连续执行多次 `exit`。

## 来源

根据 [PR #3](https://github.com/Criogaid/CMModemPasswordRetrieval/pull/3)、用户提供的两张教程截图及[仓库代码](../main.py)整理。感谢 marcos1 提供 HG6042A1 的实现与测试反馈；截图未提供可核对的原文链接，此处不收录其中的凭据。项目署名与许可见[教程首页](README.md)。
