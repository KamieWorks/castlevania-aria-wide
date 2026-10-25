# 构建与离线验证

正式 DLL 仅需 Windows、Python 3.12+、MSVC C++ x86 工具链及 Windows SDK。
使用 Visual Studio Installer 安装 C++ 桌面开发工具；build.ps1 自动发现工具链。
不需要游戏、ROM、Frida 或网络下载第三方 C 源码。

```powershell
python dev.py audit
python dev.py build
python dev.py test
python dev.py package
```

DLL 位于 out/build/d3d9.dll。最小 ZIP 位于 out/releases/，严格只有 DLL 和
README.txt；第三方完整许可合并在 README。打包脚本拒绝覆盖既有包。
离线 test 构建一个 x86 非游戏进程，验证 Install 返回未知 EXE 拒绝码 -10，
没有启用挂钩，同时 Direct3DCreate9 仍成功转发系统实现。

已在独立公开源码目录重建本体、原生输入 guard 和冻结 PPU 参考渲染器。
本体与已验收的 v26 发行 DLL 仅有 PE/导出时间戳的四个字节不同；机器码一致。
不同时间/工具链重编译不应直接要求整个 DLL 文件哈希等于旧发行物。
可使用 tools/compare_build.py 对比原发行 DLL 与本机构建，工具仅忽略 PE 时间戳。

可选后台诊断需要 Python 图像/PE 库及 Node Frida：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm ci
python dev.py build-debug
```

依赖版本与原测试环境一致：Python 3.14、Node 24 的环境已实测；源码入口最低
Python 3.12。构建和 offline test 不导入这些可选诊断依赖。
Node 工具使用本仓库 package.json 的 Frida，不依赖作者安装的其他软件包。
第三方各自许可证继续适用。

source-index.json 是正式源码及导出适配的逐文件映射。修改代码后为新发布更新
该映射与 source-distribution.json，不能无说明地把旧二进制哈希当作新构建哈希。
