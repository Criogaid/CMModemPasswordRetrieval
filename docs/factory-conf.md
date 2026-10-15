# 方法一：读取 factory.conf

这是仓库原有的读取方式，现有实机已通过 `root` 登录并取得完整账号和密码。开始前先完成[连接与登录步骤](README.md)，确认 Telnet 命令行可以交互。

## 操作步骤

在光猫的普通命令行中执行：

```sh
cat /flash/cfg/agentconf/factory.conf
```

等命令执行完、提示符重新出现后，在输出中查找以下两个字段。下面是虚构示例：

```text
TelecomAccount=CMCCAdmin
TelecomPasswd=ExamplePass123#
```

`TelecomAccount=` 后面的完整内容是网页超级管理员账号，`TelecomPasswd=` 后面的完整内容是密码。上例的密码是 `ExamplePass123#`，末尾的 `#` 属于密码，不要删掉。

## 没有取得完整结果时

文件不存在、没有读取权限，或缺少任一字段，都不能算完整获取成功。只要命令已结束且命令行仍能交互，就在同一连接中继续[方法二：cfg_cmd 查询](cfg-cmd.md)，无需重新登录。

如果命令一直没有返回或连接已断开，按[连接指南](README.md)中的处理方式结束当前尝试。不要创建、修改或覆盖这个配置文件。

取得完整结果后即可停止，按[连接指南](README.md)中的结束步骤关闭连接并处理 Telnet 服务。

## 来源

根据[仓库代码](../main.py)的原有读取方式和已有实机验证整理。原作者、出处与许可见[教程首页](README.md)。
