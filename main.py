from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import asyncio
import aiohttp

@register("steam_status", "YourName", "实时检测Steam好友状态并在状态变化时通知QQ群", "1.0.0")
class SteamStatusPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = context.get_config()
        self.steam_api_key = self.config.get("steam_api_key", "")
        self.poll_interval = self.config.get("poll_interval", 60)
        self.group_config = self.config.get("group_config", "")
        self.last_status = {}  # steamid -> status

        # 启动定时任务
        asyncio.create_task(self.poll_steam_status())

    async def poll_steam_status(self):
        while True:
            await asyncio.sleep(self.poll_interval)
            try:
                group_configs = self.parse_group_config(self.group_config)
                for group_qq, steam_ids in group_configs.items():
                    await self.check_friend_statuses(steam_ids, group_qq)
            except Exception as e:
                logger.error(f"Steam状态检查失败: {e}")

    def parse_group_config(self, config_text: str):
        """
        解析用户输入的配置文本。
        格式: 群号:SteamID1,SteamID2
        返回: dict[group_qq] = list[steam_ids]
        """
        result = {}
        lines = config_text.strip().splitlines()
        for line in lines:
            if not line.strip() or ':' not in line:
                continue
            group_part, steam_part = line.split(':', 1)
            group_qq = group_part.strip()
            steam_ids = [sid.strip() for sid in steam_part.split(',') if sid.strip()]
            if group_qq and steam_ids:
                result[group_qq] = steam_ids
        return result

    async def check_friend_statuses(self, friend_ids, target_group_id):
        if not self.steam_api_key or not friend_ids:
            return

        url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={self.steam_api_key}&steamids={','.join(friend_ids)}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"Steam API请求失败，状态码: {response.status}")
                    return
                data = await response.json()
                players = data.get("response", {}).get("players", [])

                for player in players:
                    steamid = player["steamid"]
                    current_state = player.get("personastate", 0)
                    personaname = player.get("personaname", steamid)

                    last_state = self.last_status.get(steamid)
                    if last_state is not None and current_state != last_state:
                        status_text = self.get_status_text(current_state)
                        message = f"[Steam] 好友 {personaname} 的状态已改变: {status_text}"
                        await self.send_to_group(target_group_id, message)

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

    async def send_to_group(self, group_id, message):
        chain = [message]
        await self.context.send_message(group_id, chain)