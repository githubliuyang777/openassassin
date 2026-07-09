---
name: pr-submit
description: Submit local changes as a PR to the remote main branch using opensourceways Issue and PR templates. Use this skill whenever the user asks to submit changes, create a PR, push changes to remote, merge to main, 提交PR, 提交代码, or any variation of wanting to send local commits upstream. Also use when the user mentions 缺陷提交模板, pull_request_template, or wants to follow the opensourceways contribution workflow.
---

# PR 提交流程（opensourceways 模板）

将本地改动通过 Issue + PR 模板方式提交到远端仓库主分支。

## 前置条件

- 已安装 `gh` CLI 并完成认证
- 当前仓库的 remote origin 指向 GitHub 上的 opensourceways 组织仓库

## 流程

按顺序执行以下 4 个步骤，任何步骤失败则停止后续步骤并报告错误。

### 步骤 1：获取模板

从 opensourceways/.github 仓库获取 Issue 和 PR 模板，以便后续步骤使用：

```bash
# 获取 Issue 模板
gh api repos/opensourceways/.github/contents/.github/ISSUE_TEMPLATE/%E7%BC%BA%E9%99%B7%E6%8F%90%E4%BA%A4%E6%A8%A1%E6%9D%BF.yaml \
  --jq '.content' | base64 -d

# 获取 PR 模板
gh api repos/opensourceways/.github/contents/.github/pull_request_template.md \
  --jq '.content' | base64 -d
```

模板关键信息：
- **Issue 模板**：标题前缀 `[缺陷]: `，label 为 `bug`，body 包含环境信息、问题详细描述（预置条件/操作步骤/结果描述/预期结果）、问题定位情况
- **PR 模板**：包含描述、相关 Issue（使用 `resolve` 关键字链接）、变更类型勾选

### 步骤 2：创建 Issue

先检查本地改动（`git status`、`git diff HEAD`），理解变更内容后，按照 Issue 模板格式创建 Issue。

Issue body 结构：
```
感谢您为社区报告缺陷！请按照以下提示提供详细信息，以便我们更好地理解并跟进。

### 环境信息
- 仓库: {当前仓库名}
- 分支: {当前分支名}
- 其他相关环境信息

### 问题详细描述

#### 预置条件
<!-- 描述变更的前置背景 -->

#### 操作步骤
<!-- 列出具体做了哪些改动 -->

#### 结果描述
<!-- 改动后的实际结果 -->

#### 预期结果
<!-- 改动后期望达成的效果 -->

### 问题定位情况
<!-- 可选，描述相关定位分析 -->
```

创建命令：
```bash
gh issue create \
  --title "[缺陷]: {简短描述}" \
  --label "bug" \
  --body "{按模板格式编写的body}"
```

记录创建成功后的 Issue URL（格式：`https://github.com/{owner}/{repo}/issues/{number}`），后续步骤需要使用 Issue 编号。

### 步骤 3：提交并推送本地改动

**只添加与改动相关的具体文件**，避免使用 `git add -A` 或 `git add .` 以防止误提交敏感文件。

```bash
# 添加文件（指定具体文件路径）
git add <file1> <file2> ...

# 提交（commit message 简要描述改动内容）
git commit -m "简述改动"

# 推送到远端
git push -u origin <branch-name>
```

### 步骤 4：创建 PR 关联 Issue

使用 PR 模板格式创建 PR，目标分支为 `main`。必须使用 `resolve` 关键字关联步骤 2 创建的 Issue。

PR body 结构：
```markdown
## 描述
<!-- 简要描述这个 PR 的目的和变更内容 -->

## 相关 Issue
resolve {步骤2中创建的Issue URL}

## 变更类型
<!-- 勾选适用的变更类型 -->
- [ ] Bug 修复
- [ ] 新功能
- [ ] 代码重构
- [ ] 文档更新
- [ ] 样式改进
- [ ] 性能优化
- [ ] 测试相关
- [ ] 其他
```

创建命令：
```bash
gh pr create \
  --title "{PR 标题}" \
  --body "{按模板格式编写的body}"
```

完成后向用户报告 Issue 和 PR 的 URL。

## 注意事项

- 步骤 2、3 无依赖关系，可以按任意顺序执行，但步骤 4 必须在步骤 2 之后（因为需要关联 Issue）
- commit message 和 PR title 保持简洁，重点描述"为什么"而非"是什么"
- 不要提交 `.env`、credentials 等敏感文件
- 如果分支已存在远端且有未同步的提交，先评估是否需要 rebase 再推送
