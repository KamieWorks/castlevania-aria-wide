# AriaWide — 晓月圆舞曲 16:9 补丁源码

为 Steam《Castlevania Advance Collection》中的《晓月圆舞曲》扩大水平视野。
大房间显示 288×162 的 16:9 画面，像素保持比例；HUD 固定在屏幕四角，
背景及半透明云使用原版视差。固定房间、标题、菜单及结局插画居中。

本仓库提供 **v27 的完整自编补丁源码、调试工具、历史源码和开发说明**。
它不是原游戏或模拟器的完整源码，不附带游戏、汉化、存档或私人快照。

## 玩家安装

发布 ZIP 只有 `d3d9.dll` 和 `README.txt`。关闭游戏，将 DLL 放到 `game.exe`
旁，再从 Steam 启动。卸载时移走 DLL。无需 INI、Python、Frida 或注入器。
详细说明和完整第三方许可在 `aria-wide/README.release.txt`。

v27 发行 DLL SHA-256：
`07029ee837e1f0848bdcf7a63e39ece92945f1f82a2a83a333b443c525a6e3c6`。

## 获取和构建

源码仓库：https://github.com/KamieWorks/castlevania-aria-wide

```powershell
git clone https://github.com/KamieWorks/castlevania-aria-wide.git
Set-Location castlevania-aria-wide
```

本仓库根目录就是 `DEV_ROOT`。下载源码 ZIP 或克隆后，无需作者的盘符、
Steam 账号、NAS、Codex 技能或本地已安装的逆向工具。

需要 Windows、Python 3.12+、Visual Studio C++ x86 工具链和 Windows SDK：

```powershell
python dev.py audit
python dev.py build
python dev.py test
python dev.py package
```

构建本体不需要原游戏，也不需要下载第三方源码。产物全部写入 `out/`。
`test` 在独立的非游戏进程中验证未知 EXE 拒绝和系统 D3D9 转发，不启动游戏。
调试工具的可选依赖和运行方法见 [构建说明](docs/BUILDING.md) 与
[后台调试](docs/DEBUGGING.md)。

## 源码入口

| 内容 | 位置 |
| --- | --- |
| 唯一正式补丁源码 | `aria-wide/src/` |
| 可独立构建、最小打包脚本及固定第三方来源 | `aria-wide/` |
| Python、Node、原生输入/渲染诊断工具 | `debug-v2/` |
| 已撤回原型及旧源码检查点，供研究 | `historical/` |
| 精确来源、原始/导出文件哈希 | `source-index.json` |
| 公开文件清单与暂存区隐私检查工具 | `source-distribution.json`、`tools/` |

接手前阅读 [源码地图](docs/SOURCE_MAP.md)、[逆向与渲染说明](docs/RENDERING.md)、
[验证边界](docs/VALIDATION.md)、[AGENTS.md](AGENTS.md)。
历史目录不参与正式构建，其中旧 Direct3D 原型曾崩溃，不应安装给玩家。

## 兼容与验证

v27 修复尤里乌斯模式四种副武器及边框随镜头移动的问题。日文原版和汉化版
各通过 49 帧原生图标对照与 144 帧连续行走边缘检查，存档未改、正常退出。
原版另核对完整左上 HUD；本轮没有重新通关全部历史场景。

仅对以下 Steam `game.exe` 启用挂钩，未知版本回退到原生 D3D9：
`404e78ade8b92fe3a89aa2ed3e7de8bde3545d694e669835a81145f5e026e6bb`。

v26 已分别在纯 Steam 日文原版及日版汉化环境进行单 DLL、无 INI 的冷启动验证。
两版各 288 连续帧，标题/固定房间居中、水平扩展和半透明云合成通过。
另有 HUD、背景、混帧、仿射、真实倒带、菜单及退出回归记录。
这不等于逐个房间的全部战斗与剧情重新通关，细节见验证文档。

`ExtendFixedRooms` 的完整实验实现保留，默认关闭。补丁不改原版碰撞、
敌人激活范围、战斗边界、游戏 EXE、磁盘 ROM 或存档。

欢迎提交范围明确的修复，先读 [贡献说明](CONTRIBUTING.md)。
原创代码与文档采用 [MIT](LICENSE)，第三方及原游戏边界见
[第三方声明](THIRD_PARTY_NOTICES.md)。
