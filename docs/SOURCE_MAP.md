# 源码地图与来源

仓库根即 DEV_ROOT。aria-wide/src 是唯一正式运行实现；不是只提供玩家 ZIP。

| 文件 | 作用 |
| --- | --- |
| aria-wide/src/proxy.cpp、proxy.def | x86 系统 D3D9 转发和初始化入口 |
| aria-wide/src/realtime.cpp | 原版身份验证、宽屏、HUD、视差、云、状态历史及生命周期修正 |
| aria-wide/build.ps1、package.ps1 | 独立构建和严格两文件发布包 |
| aria-wide/vendor/minhook | 固定上游版本、HDE、完整许可和哈希清单 |
| debug-v2/harness.py、probe.js、bridge.mjs | 有界进程内控制、PPU 截图、快照、逐帧遥测 |
| debug-v2/input-guard.cpp | 保留寄存器/浮点状态的原生后台 GBA 输入 |
| debug-v2/background-launch.mjs、quiet-game.py | 隐藏、不抢焦点、仅游戏会话静音 |
| debug-v2/cloud-isolate.mjs | 调试时保护 Steam 存储、统计和成就 |
| debug-v2/render-prototype.cpp | 独立冻结 PPU 的原生渲染参考 |
| debug-v2/check-*.py | 构图、HUD、连续边缘、云、状态、混帧、仿射、菜单等诊断 |
| debug-v2/room-graph.py、audit-*.py | 私有本地资源的结构审计，不附带资源本身 |
| historical/ | 所有保留的自编旧原型/源码检查点，不参与正式构建 |
| tools/ | 导出、精确暂存隐私扫描、包验证和二进制时间戳对照 |

source-index.json 为每个从原工作树导出的文件记录原始哈希、公开副本哈希及
是否作了移植适配。正式 C/C++ 核心与固定供应源码保持逐字节一致。
公开调试工具移除了作者账号、私人 npm 导入位置、硬编码个人 Steam profile，
改用配置发现或环境变量；没有把个人运行数据改名后随源码发放。

检查点仅提取自编 cpp/def/构建脚本，不复制其二进制、存档、快照或资源。
早期 sotn16x9 名称是历史误名，不意味着本仓库针对月下夜想曲。
这些 Direct3D 包装原型已撤回且曾崩溃，不能用于玩家安装。
部分历史构建脚本保留旧工具链路径；正式入口始终是根 dev.py。

完整公开集合另由 source-distribution.json 覆盖。原游戏资源、ROM、汉化包、
个人存档、截图/内存转储、日志、已下载工具与旧 Git 历史均不在集合内。
