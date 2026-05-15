# 运势生成

- **作者**: [kldhsh123](https://github.com/kldhsh123)
- **插件文件**: `fortune_plugin.py`
- **命令**: `/运势`
- **描述**: 生成今日运势值和描述；同一用户同一天重复调用会返回相同结果

## 安装

1. 将 `fortune_plugin.py` 复制到 HiklQQBot 主仓库的 `plugins/` 目录
2. 启动机器人，或执行 `/hiklqqbot_reload`
3. 插件首次运行时会自动创建 `data/fortune/fortune_records.json`

## 使用方法

```text
/运势
```

## 功能说明

- 每个用户每天只会生成一次新的运势
- 当天重复调用时，会返回第一次生成的结果
- 运势记录默认保留 30 天，过期记录会自动清理
- 返回内容包含 1 到 100 的运势值，以及对应的运势评价

## 数据文件

- `data/fortune/fortune_records.json`

插件会自动创建数据目录和数据文件，一般不需要手动准备。

## 示例输出

```text
✨ 今日运势: 88
💫 运势评价: 超级幸运！今天宜大胆行动！
```

## 注意事项

- 当前实现不依赖额外第三方库
- 插件需要运行在 HiklQQBot 主框架内，依赖 `plugins.base_plugin`
