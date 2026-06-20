# AstrBot Hot Inject 插件

在不重启 AstrBot、不删除会话记录的前提下，动态修改/追加系统提示词或用户消息内容。

## 功能

- 通过指令动态添加、删除、启用/禁用提示词注入
- 三种注入模式：追加、替换、额外内容
- 支持开关热注入功能
- 注入内容持久化存储，重启不丢失
- 即时生效：在 WebUI 中修改人格设定的系统提示词后，无需重启或清除会话记录，下一次 LLM 请求会自动使用更新后的提示词

## 注入模式

| 模式 | 说明 | 适用场景 | 缓存影响 |
|------|------|----------|----------|
| `append` | 追加到 `system_prompt` 末尾 | 稳定的角色设定/规则 | 会破坏缓存 |
| `replace` | 覆盖整个 `system_prompt` | 完全替换人格设定 | 会破坏缓存 |
| `extra` | 追加到 `extra_user_content_parts` | 每轮动态变化的内容 | **不影响缓存，成本最低** |

## 指令

```
/inject add <mode> <内容>    添加一条注入
/inject remove <id>          删除指定注入
/inject list                 列出所有注入
/inject toggle <id>          启用/禁用指定注入
/inject clear                清空所有注入
/inject mode <mode>          设置默认注入模式
/inject enabled <on|off>     开关热注入功能
```

### 示例

```bash
# 追加一段固定规则
/inject add append 你是一个有礼貌的助手，回答时请使用敬语。

# 替换系统提示词
/inject replace replace 你是一个专业的翻译官，只做中英互译。

# 追加动态内容到用户消息（推荐，不破坏缓存）
/inject extra extra <runtime>当前时间：2026-06-21</runtime>

# 查看当前注入
/inject list

# 关闭热注入
/inject enabled off
```

## 配置项

| 配置 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `default_mode` | string | `append` | 默认注入模式 |
| `inject_enabled` | bool | `true` | 是否启用热注入 |
| `extra_content_separator` | string | `\n---\n` | extra 模式下多个注入的分隔符 |

## 安装

将 `astrbot_plugin_hot_inject` 目录复制到 AstrBot 的 `data/plugins/` 目录下，重启或在 WebUI 重载插件。

## 注意事项

- `append` 和 `replace` 模式会修改 `system_prompt`，可能导致 LLM 缓存失效，增加请求成本
- 建议动态内容使用 `extra` 模式，对缓存无影响
- 注入内容存储在 `data/plugin_data/astrbot_plugin_hot_inject/injections.json`
- 插件卸载时通过 `terminate` 方法执行清理
