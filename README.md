# CMModemPasswordRetrieval
这是一个开源项目，旨在获取中国移动光猫超级管理员账户CMCCAdmin的密码，适用于HG系列，已在HG6821M上进行了测试。

感谢 [marcos1](https://github.com/Criogaid/CMModemPasswordRetrieval/pull/3) 完善了获取方式，并且已于HG6042A1上进行了测试。

**原作者：** [布束砥信](https://space.bilibili.com/521361612)  
**出处：** [bilibili](https://www.bilibili.com/read/cv21044770)

我们欢迎任何形式的贡献，包括但不限于提交问题、改进代码、提供文档等。感谢您对CMModemPasswordRetrieval项目的支持。

## 工作原理：

### 1. 初始化（`__init__`）

当创建`ModemManager`类的实例时，会初始化光猫的IP地址（默认是“192.168.0.1”）和Telnet端口（默认是23）。同时，也会获取光猫的MAC地址。

### 2. 获取MAC地址（`get_mac_address`）

脚本通过运行`arp -a`命令并解析其输出来获取光猫的MAC地址。此MAC地址将被用于生成管理员密码。

### 3. 启用Telnet（`enable_telnet`）

脚本将发送一个HTTP GET请求到光猫，使其开启Telnet服务。请求的URL包含了MAC地址。

### 4. 获取管理员密码（`get_admin_password`）

脚本将通过Telnet连接到光猫，并使用特定的用户名（“root”）和密码来登录。密码是由“Fh@”和MAC地址的后六位组成的。登录后，脚本将运行`cat /flash/cfg/agentconf/factory.conf`命令来获取管理员密码。

### 5. 管理光猫（`manage_modem`）

这是脚本的主要函数，先启用Telnet服务，然后获取管理员密码。

### 6. 运行脚本

如果直接运行这个脚本，它将创建一个`ModemManager`实例，并获取光猫的管理员密码。

请注意，此脚本需要在有网络连接并且能访问到光猫的计算机上运行。同时，计算机需要有Python环境，并且已安装`requests`、`loguru`库。

```python
if __name__ == "__main__":
    manager = ModemManager()
    admin_password = manager.manage_modem()
```

## 许可证

<p align="center">
  <img src="http://mirrors.creativecommons.org/presskit/buttons/88x31/png/by-nc-sa.png" />
</p>

本项目遵循互联网的开放、自由、共享的原则，采用[CC BY-NC-SA 4.0 许可协议](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans) 进行授权。

如需转载或引用本项目，请务必遵守许可协议的条款。在您的文章或项目开头部分，必须注明原作者、标注原项目链接，并以同样的方式，即CC BY-NC-SA 4.0许可协议，分享您的作品。

任何不遵循 CC BY-NC-SA 4.0 许可协议进行分发的行为，将被视为侵权。
