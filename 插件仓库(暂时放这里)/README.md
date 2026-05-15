# HiklQQBot 插件仓库

这个目录用于整理将发布到 `https://github.com/kldhsh123/hiklqqbot-plugin` 的独立插件。

## 使用方式

1. 选择需要的插件
2. 将对应的 `.py` 文件复制到主仓库 `plugins/` 目录
3. 按插件说明准备可选的数据目录或配置
4. 重启机器人，或在机器人中执行 `/hiklqqbot_reload`

## 目录结构

- `娱乐/fortune_plugin.py`：今日运势插件
- `娱乐/fortune_plugin.md`：今日运势插件说明
- `娱乐/roll_plugin.py`：掷骰子插件
- `娱乐/roll_plugin.md`：掷骰子插件说明

## 当前插件

### 娱乐

- [运势生成](娱乐/fortune_plugin.md)
- [掷骰子](娱乐/roll_plugin.md)

## 编写约定

- 一个插件至少包含一个 `.py` 文件
- 建议同目录提供同名 `.md` 说明文件
- 说明文件至少写清楚：功能、命令、安装方式、依赖、示例和注意事项
