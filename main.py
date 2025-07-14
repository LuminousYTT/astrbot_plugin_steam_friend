from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import asyncio
import aiohttp
import json

@register("steam_status", "author", "Steam好友状态监控插件", "1.0.0")
class SteamStatusPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = context.get_config()  # 获取插件配置
        self.steam_api_key = self.config.get("steam_api_key", "")
        self.friend_ids = self.config.get("friend_ids", [])
        self.target_group_id = self.config.get("target_group_id", "")
        self.poll_interval = self.config.get("poll_interval", 60)  # 默认每分钟检查一次
        self.last_status = {}  # 存储上次检查的好友状态

        # 启动定时任务
        asyncio.create_task(self.poll_steam_status())

    async def poll_steam_status(self):
        while True:
            await asyncio.sleep(self.poll_interval)
            try:
                await self.check_friend_statuses()
            except Exception as e:
                logger.error(f"Steam状态检查失败: {e}")

    async def check_friend_statuses(self):
        if not self.steam_api_key or not self.friend_ids:
            logger.warning("Steam API密钥或好友ID未配置，无法进行检查。")
            return

        url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={self.steam_api_key}&steamids={','.join(self.friend_ids)}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Steam API请求失败，状态码: {response.status}")
                    return
                data = await response.json()
                players = data.get("response", {}).get("players", [])

                for player in players:
                    steamid = player["steamid"]
                    current_state = player.get("personastate", 0)

                    if steamid in self.last_status:
                        if current_state != self.last_status[steamid]:
                            # 状态发生变化
                            status_text = self.get_status_text(current_state)
                            message = f"[Steam] 好友 {player['personaname']} 的状态已改变: {status_text}"
                            await self.send_to_group(message)

                    self.last_status[steamid] = current_state

    def get_status_text(self, state):
        statuses = {
            0: "离线",
            1: "在线",
            2: "忙碌",
            3: "离开",
            4: "隐身",
            5: "查找游戏",
            6: "正在游戏中"
        }
        return statuses.get(state, "未知状态")

    async def send_to_group(self, message):
        if not self.target_group_id:
            logger.warning("未配置目标群组ID，无法发送消息。")
            return

        chain = [message]
        await self.context.send_message(self.target_group_id, chain)