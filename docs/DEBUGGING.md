# 后台调试与本地数据

正式补丁不依赖此目录的诊断工具。诊断仅在开发者明确授权的本地安装上运行。
先执行 dev.py build-debug，并安装 requirements-dev.txt、npm ci 的可选依赖。
配置通过当前进程环境变量完成，不向 Git 写入个人路径或账号：

```powershell
$env:ARIA_GAME_ROOT = 'D:\YourGames\Castlevania Advance Collection'
$env:ARIA_PROFILE_ROOT = 'D:\YourSteamProfile\1552550\remote'
$env:ARIA_DEBUG_ROOT = (Join-Path (Get-Location) 'out/debug')
python debug-v2/quiet-game.py --launch --seconds 8
```

可省略 Steam 安装目录配置，Python 会读取注册表和 libraryfolders.vdf。
如同一安装存在多个匹配用户，必须显式指定 ARIA_PROFILE_ROOT。
独立 Node 诊断要求显式 ARIA_GAME_ROOT；ARIA_STEAM_ROOT、ARIA_DEPOT_MANIFEST、
ARIA_CDB 可分别覆盖 Steam 根、depot 清单与 x86 CDB 位置。

quiet-game 与 background-launch 限定目标进程，隐藏窗口、阻止激活并隔离本进程键盘，
只对游戏音频会话静音。进程内脉冲由原生 input guard 保留寄存器/浮点状态，
有截止时间；不得改成全局键盘输入或指令中段 Gum listener。
按键是否生效要从 GBA 状态或实际表面截图判断，不能只看注入调用计数。

Probe 提供当前 ROM 的快照、PPU 原生表面截图和逐帧采集。部分历史 check-*.py
引用当时的私有用例/报告名；这些文件不会随源码分发，也不能用汉化 CPU 快照
冒充原版测试。应先用自己的当前 ROM、当前 profile 建立相同用例。
check-install-variant-v26.py 展示从当前 ROM/存档构造测试入口、原生门过渡、
独立冻结 PPU 参考与 finally 恢复；测试前需准备有合适出口的受控存档。

调试 cloud-isolate 守护必须保留到游戏退出，保护 Steam 文件写入、成就和统计。
运行时门重定向/角色定位仅限诊断，恢复 guest 改动与最新用户快照；不写磁盘 ROM，
不把旧 SRAM 带回当前 profile。一次只有一个控制器；完成后正常退出，再使用
restore-audio-after-close.py 跨退出保留音频接口、解除静音并读回验证。

截图、ROM 指纹输入、状态、用户配置和原始逐帧数据均位于被忽略的 out/ 或明确
指定的 scratch。发布时只保留汇总、必要匿名证据，不上传原游戏、汉化或存档。
