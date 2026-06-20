import json
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.agent.message import TextPart
from astrbot.core.utils.astrbot_path import get_astrbot_data_path


class HotInjectPlugin(Star):
    """热注入提示词插件 - 在不重启的情况下动态修改/追加系统提示词。"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.data_dir = Path(get_astrbot_data_path()) / "plugin_data" / self.name
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.injections_file = self.data_dir / "injections.json"
        self.injections: list[dict] = self._load_injections()

    def _load_injections(self) -> list[dict]:
        if self.injections_file.exists():
            try:
                with open(self.injections_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load injections: {e}")
        return []

    def _save_injections(self):
        with open(self.injections_file, "w", encoding="utf-8") as f:
            json.dump(self.injections, f, ensure_ascii=False, indent=2)

    def _get_next_id(self) -> int:
        if not self.injections:
            return 1
        return max(item["id"] for item in self.injections) + 1

    # ==================== Hook: LLM 请求前注入 ====================

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req):
        """在 LLM 请求前注入提示词。"""
        if not self.config.get("inject_enabled", True):
            return

        if not self.injections:
            return

        active_mode = self.config.get("default_mode", "append")

        extra_parts = []

        for item in self.injections:
            if not item.get("enabled", True):
                continue

            mode = item.get("mode", active_mode)
            content = item["content"]

            if mode == "replace":
                req.system_prompt = content
            elif mode == "append":
                req.system_prompt += content
            elif mode == "extra":
                extra_parts.append(content)

        if extra_parts:
            sep = self.config.get("extra_content_separator", "\n---\n")
            req.extra_user_content_parts.append(
                TextPart(text=sep.join(extra_parts))
            )

    # ==================== 指令：注入管理 ====================

    @filter.command("inject")
    async def inject_cmd(self, event: AstrMessageEvent):
        """注入提示词管理。用法: /inject <add|remove|list|clear|toggle> [参数]"""
        parts = event.message_str.strip().split(maxsplit=2)
        if len(parts) < 2:
            yield event.plain_result(
                "用法:\n"
                "  /inject add <mode:append|replace|extra> <内容> - 添加注入\n"
                "  /inject remove <id> - 删除指定注入\n"
                "  /inject list - 列出所有注入\n"
                "  /inject toggle <id> - 启用/禁用指定注入\n"
                "  /inject clear - 清空所有注入\n"
                "  /inject mode <append|replace|extra> - 设置默认模式\n"
                "  /inject enabled <on|off> - 开关热注入"
            )
            return

        action = parts[1].lower()

        if action == "add":
            await self._handle_add(event, parts)
        elif action == "remove":
            await self._handle_remove(event, parts)
        elif action == "list":
            await self._handle_list(event)
        elif action == "toggle":
            await self._handle_toggle(event, parts)
        elif action == "clear":
            await self._handle_clear(event)
        elif action == "mode":
            await self._handle_mode(event, parts)
        elif action == "enabled":
            await self._handle_enabled(event, parts)
        else:
            yield event.plain_result(f"未知操作: {action}，使用 /inject 查看帮助。")

    async def _handle_add(self, event: AstrMessageEvent, parts: list[str]):
        """添加注入内容。"""
        if len(parts) < 3:
            yield event.plain_result("用法: /inject add <mode:append|replace|extra> <内容>")
            return

        mode_part = parts[2]
        space_idx = mode_part.find(" ")
        if space_idx == -1:
            yield event.plain_result("用法: /inject add <mode:append|replace|extra> <内容>")
            return

        mode = mode_part[:space_idx].lower()
        content = mode_part[space_idx + 1:]

        if not content:
            yield event.plain_result("注入内容不能为空。")
            return

        if mode not in ("append", "replace", "extra"):
            yield event.plain_result("模式必须是 append、replace 或 extra。")
            return

        item = {
            "id": self._get_next_id(),
            "mode": mode,
            "content": content,
            "enabled": True,
        }
        self.injections.append(item)
        self._save_injections()

        yield event.plain_result(
            f"✅ 已添加注入 #{item['id']}\n"
            f"模式: {mode}\n"
            f"内容: {content[:100]}{'...' if len(content) > 100 else ''}"
        )

    async def _handle_remove(self, event: AstrMessageEvent, parts: list[str]):
        """删除指定注入。"""
        if len(parts) < 3:
            yield event.plain_result("用法: /inject remove <id>")
            return

        try:
            target_id = int(parts[2])
        except ValueError:
            yield event.plain_result("ID 必须是数字。")
            return

        original_len = len(self.injections)
        self.injections = [item for item in self.injections if item["id"] != target_id]

        if len(self.injections) == original_len:
            yield event.plain_result(f"未找到注入 #{target_id}。")
        else:
            self._save_injections()
            yield event.plain_result(f"✅ 已删除注入 #{target_id}。")

    async def _handle_list(self, event: AstrMessageEvent):
        """列出所有注入。"""
        if not self.injections:
            yield event.plain_result("当前没有注入内容。")
            return

        enabled_str = "开启" if self.config.get("inject_enabled", True) else "关闭"
        default_mode = self.config.get("default_mode", "append")

        lines = [f"热注入状态: {enabled_str} | 默认模式: {default_mode}\n"]

        for item in self.injections:
            status = "🟢" if item.get("enabled", True) else "🔴"
            content_preview = item["content"][:80] + ("..." if len(item["content"]) > 80 else "")
            lines.append(
                f"{status} #{item['id']} [{item['mode']}]\n{content_preview}"
            )

        yield event.plain_result("\n".join(lines))

    async def _handle_toggle(self, event: AstrMessageEvent, parts: list[str]):
        """启用/禁用指定注入。"""
        if len(parts) < 3:
            yield event.plain_result("用法: /inject toggle <id>")
            return

        try:
            target_id = int(parts[2])
        except ValueError:
            yield event.plain_result("ID 必须是数字。")
            return

        for item in self.injections:
            if item["id"] == target_id:
                item["enabled"] = not item.get("enabled", True)
                self._save_injections()
                status = "启用" if item["enabled"] else "禁用"
                yield event.plain_result(f"✅ 注入 #{target_id} 已{status}。")
                return

        yield event.plain_result(f"未找到注入 #{target_id}。")

    async def _handle_clear(self, event: AstrMessageEvent):
        """清空所有注入。"""
        self.injections = []
        self._save_injections()
        yield event.plain_result("✅ 已清空所有注入。")

    async def _handle_mode(self, event: AstrMessageEvent, parts: list[str]):
        """设置默认注入模式。"""
        if len(parts) < 3:
            yield event.plain_result("用法: /inject mode <append|replace|extra>")
            return

        mode = parts[2].lower()
        if mode not in ("append", "replace", "extra"):
            yield event.plain_result("模式必须是 append、replace 或 extra。")
            return

        self.config["default_mode"] = mode
        self.config.save_config()
        yield event.plain_result(f"✅ 默认注入模式已设置为: {mode}")

    async def _handle_enabled(self, event: AstrMessageEvent, parts: list[str]):
        """开关热注入功能。"""
        if len(parts) < 3:
            yield event.plain_result("用法: /inject enabled <on|off>")
            return

        state = parts[2].lower()
        if state == "on":
            self.config["inject_enabled"] = True
            self.config.save_config()
            yield event.plain_result("✅ 热注入已开启。")
        elif state == "off":
            self.config["inject_enabled"] = False
            self.config.save_config()
            yield event.plain_result("✅ 热注入已关闭。已注入内容保留但不再生效。")
        else:
            yield event.plain_result("参数必须是 on 或 off。")

    async def terminate(self):
        """插件卸载时的清理。"""
        logger.info("Hot Inject plugin terminated.")
