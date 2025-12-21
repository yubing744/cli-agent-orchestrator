# CAO 技能安装与使用指南

本指南帮助您正确安装和配置CAO技能，确保在任何环境下都能正常工作。

## 📦 安装方式

### 方式一：Claude Code 技能市场（推荐）

1. 在 Claude Code 中打开技能管理器
2. 搜索 "CAO" 或 "CLI Agent Orchestrator"
3. 点击安装
4. 技能将自动安装到 `~/.claude/skills/cao/`

### 方式二：OpenSkills 安装（推荐开发者）

使用 OpenSkills 工具快速安装：

```bash
# 安装到当前项目
openskills install https://github.com/yubing744/cao-skill.git

# 或安装到全局环境
openskills install --global https://github.com/yubing744/cao-skill.git

# 或安装到通用目录（推荐）
openskills install --universal https://github.com/yubing744/cao-skill.git
```

### 方式三：手动安装

```bash
# 克隆技能到 Claude Code 技能目录
git clone https://github.com/yubing744/cao-skill.git ~/.claude/skills/cao

# 或下载ZIP文件并解压
wget https://github.com/yubing744/cao-skill/archive/main.zip
unzip main.zip -d ~/.claude/skills/cao
mv ~/.claude/skills/cao/cao-skill-main ~/.claude/skills/cao/cao-skill
```

## 🎯 使用方法

### 基本使用原则

所有命令都应**从技能目录内运行**，这是最可靠的使用方式：

```bash
# 进入技能目录
cd ~/.claude/skills/cao

# 检查服务状态
python3 scripts/cao_bridge.py health

# 安装服务（如果需要）
python3 scripts/cao_bridge.py install
```

### 不同使用场景

#### 场景1：在技能目录内使用（最推荐）
```bash
cd ~/.claude/skills/cao
python3 scripts/cao_bridge.py assign developer "您的任务描述"
```

#### 场景2：从项目目录内使用
```bash
# 假设项目根目录包含 .claude/skills/cao/
cd /path/to/your/project
python3 .claude/skills/cao/scripts/cao_bridge.py health
```

#### 场景3：从任意位置使用
```bash
# 使用完整路径
python3 ~/.claude/skills/cao/scripts/cao_bridge.py health

# 或设置环境别名
alias cao="python3 ~/.claude/skills/cao/scripts/cao_bridge.py"
cao health
```

#### 场景4：在项目中配置快捷方式
```bash
# 在项目根目录创建快捷脚本
echo '#!/bin/bash
python3 ~/.claude/skills/cao/scripts/cao_bridge.py "$@"' > cao.sh
chmod +x cao.sh

# 使用
./cao.sh health
./cao.sh assign developer "任务描述"
```

## 🔧 环境要求

### 必需依赖
- Python 3.9+
- requests 库
- uvx (用于自动安装)

### 可选依赖
- GitHub CLI (gh)
- curl

### 环境检查命令
```bash
cd ~/.claude/skills/cao

# 检查Python
python3 --version

# 检查依赖
python3 -c "import requests; print('requests OK')"
uvx --version

# 检查技能功能
python3 scripts/cao_bridge.py --help
```

## 🚀 快速启动

### 首次使用
```bash
# 1. 进入技能目录
cd ~/.claude/skills/cao

# 2. 检查CAO服务
python3 scripts/cao_bridge.py health

# 3. 如需要，安装服务
python3 scripts/cao_bridge.py install

# 4. 再次检查
python3 scripts/cao_bridge.py health

# 5. 开始使用
python3 scripts/cao_bridge.py assign developer "Hello CAO!"
```

### 常用命令快速参考
```bash
# 健康检查
python3 scripts/cao_bridge.py health

# 安装服务
python3 scripts/cao_bridge.py install

# 列出会话
python3 scripts/cao_bridge.py list

# 分配任务
python3 scripts/cao_bridge.py assign developer "任务描述"

# 监控终端
python3 scripts/cao_bridge.py monitor <terminal_id>

# 删除终端
python3 scripts/cao_bridge.py delete <terminal_id>
```

## 🔍 故障排除

### 常见问题

#### 问题1：Command not found
```bash
# 确保在正确目录
cd ~/.claude/skills/cao
pwd  # 应该显示 /home/username/.claude/skills/cao
ls scripts/cao_bridge.py  # 确认文件存在
```

#### 问题2：Permission denied
```bash
# 确保文件有执行权限
chmod +x scripts/cao_bridge.py

# 或使用python3直接执行
python3 scripts/cao_bridge.py health
```

#### 问题3：Python模块找不到
```bash
# 确保使用python3
which python3
python3 --version

# 安装缺失依赖
pip3 install requests
pip3 install uvx
```

#### 问题4：路径问题
```bash
# 检查当前工作目录
pwd

# 使用绝对路径测试
python3 ~/.claude/skills/cao/scripts/cao_bridge.py --help
```

### 验证安装
```bash
cd ~/.claude/skills/cao

# 测试基本功能
python3 scripts/cao_bridge.py --help

# 测试健康检查
python3 scripts/cao_bridge.py health

# 如果成功，说明安装正确
```

## 📚 高级配置

### 环境变量配置
```bash
# 添加到 ~/.bashrc 或 ~/.zshrc
export CAO_HOME="$HOME/.claude/skills/cao"
export PATH="$CAO_HOME/scripts:$PATH"

# 创建别名
alias cao="python3 $CAO_HOME/scripts/cao_bridge.py"

# 重新加载配置
source ~/.bashrc  # 或 source ~/.zshrc
```

### 项目级配置
```bash
# 在项目中创建 .cao-config 文件
echo "CAO_SKILL_PATH=$HOME/.claude/skills/cao" > .cao-config
echo "export PATH=\"$CAO_SKILL_PATH/scripts:\$PATH\"" >> .cao-config

# 使用时加载
source .cao-config
python3 scripts/cao_bridge.py health
```

## 💡 最佳实践

1. **始终从技能目录运行命令**：这是最可靠的方式
2. **定期更新技能**：从技能市场获取最新版本
3. **检查环境依赖**：确保Python和必需库已安装
4. **使用相对路径**：在脚本中使用 `python3 scripts/cao_bridge.py`
5. **备份配置**：保存重要的别名和环境变量设置

## 🎉 完成安装

如果您能成功运行以下命令，说明安装已完成：

```bash
cd ~/.claude/skills/cao
python3 scripts/cao_bridge.py --help
python3 scripts/cao_bridge.py health
```

现在您可以开始使用CAO技能进行Agent编排和任务管理了！