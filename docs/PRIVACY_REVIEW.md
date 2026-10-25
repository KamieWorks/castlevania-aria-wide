# 公开前隐私与内容审查

采用独立导出目录和全新 Git 历史，不复制私有工作仓库的 .git、remote 或提交者元数据。
提交使用 GitHub noreply 身份。原创代码/文档按参考项目的方式采用 MIT，第三方许可独立。

审查对象是实际待提交文件及暂存 blob，不仅是 .gitignore 或打算公开的文件名。
检查私钥、常见令牌、凭证字面值、带密码 URL、私人用户目录、Steam 用户目录、
邮箱和内网地址；扫描输出仅包含文件/行号/规则，不输出疑似敏感值。

调试代码中的作者 npm 安装位置改为标准包依赖，Steam profile 改为自动发现/显式配置，
游戏与调试输出路径可配置，WinDbg 位置通过 PATH/环境变量获取。正式核心源码不变。

没有上传游戏/模拟器原始资源、ROM、汉化包、用户存档、个人配置、截图/内存转储、
日志、旧 Git 历史、下载工具、模型或构建产物。唯一配置模板是源码中的默认实验选项。
旧检查点只复制自编源码，原型状态和不参与正式构建的边界明确标注。

可重新运行：

```powershell
python dev.py audit
python tools/check_publication.py --staged
python tools/check_publication.py
```

source-index.json 记录正式/历史自编代码来源和移植改动，source-distribution.json
覆盖最终公开文件集合。规则扫描和人工检查共同使用；未来修改需重新检查。

本次对全部 191 个公开文件的暂存内容检查没有未处理发现。另用合成负样本验证
检查器会拒绝令牌、个人目录、内网地址、邮箱、禁止文件及二进制内容；暂存后将
工作树改成干净文本，仍能发现 Git index 中的负样本。没有使用真实凭证。
可通过 `python -m unittest discover -s tests` 重新执行该负向验证。
