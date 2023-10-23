﻿import os
from urllib.parse import urlparse

from app import Config, Message, bot
from app.core.aiohttp_tools import get_json, get_type
from app.core.scraper_config import MediaType, ScraperConfig

API_KEYS = {"KEYS": Config.API_KEYS, "counter": 0}


async def get_key():
    keys, count = API_KEYS.values()
    count += 1
    if count == len(keys):
        count = 0
    ret_key = keys[count]
    API_KEYS["counter"] = count
    return ret_key


class Instagram(ScraperConfig):
    def __init__(self, url):
        super().__init__()
        self.shortcode = os.path.basename(urlparse(url).path.rstrip("/"))
        self.api_url = (f"https://www.instagram.com/graphql/query?query_hash=2b0673e0dc4580674a88d426fe00ea90"
                        f"&variables=%7B%22shortcode%22%3A%22{self.shortcode}%22%7D")
        self.url = url
        self.dump = True

    async def check_dump(self) -> None | bool:
        if not Config.DUMP_ID:
            return
        async for message in bot.search_messages(Config.DUMP_ID, "#" + self.shortcode):
            self.media: Message = message
            self.type: MediaType = MediaType.MESSAGE
            self.in_dump: bool = True
            return True

    async def download_or_extract(self):
        for func in [self.check_dump, self.api_3, self.no_api_dl, self.api_dl]:
            if await func():
                self.success: bool = True
                break

    async def api_3(self):
        query_api = f"https://{bot.SECRET_API}?url={self.url}&v=1"
        response = await get_json(url=query_api, json_=False)
        if not response:
            return
        self.caption = "."
        data: list = (
                response.get("videos", [])
                + response.get("images", [])
                + response.get("stories", [])
        )
        if not data:
            return
        if len(data) > 1:
            self.type = MediaType.GROUP
            self.media: list = data
            return True
        else:
            self.media: str = data[0]
            self.type: MediaType = get_type(self.media)
            return True

    async def no_api_dl(self):
        response = await get_json(url=self.api_url)
        if (
                not response
                or "data" not in response
                or not response["data"]["shortcode_media"]
        ):
            return
        return await self.parse_ghraphql(response["data"]["shortcode_media"])

    async def api_dl(self):
        if not Config.API_KEYS:
            return
        param = {
            "api_key": await get_key(),
            "url": self.api_url,
            "proxy": "residential",
            "js": "false",
        }
        response: dict | None = await get_json(
            url="https://api.webscraping.ai/html", timeout=30, params=param
        )
        if (
                not response
                or "data" not in response
                or not response["data"]["shortcode_media"]
        ):
            return
        self.caption = ".."
        return await self.parse_ghraphql(response["data"]["shortcode_media"])

    async def parse_ghraphql(self, json_: dict) -> str | list | None:
        type_check: str | None = json_.get("__typename", None)
        if not type_check:
            return
        elif type_check == "GraphSidecar":
            self.media: list[str] = [
                i["node"].get("video_url") or i["node"].get("display_url")
                for i in json_["edge_sidecar_to_children"]["edges"]
            ]
            self.type: MediaType = MediaType.GROUP
        else:
            self.media: str = json_.get("video_url", json_.get("display_url"))
            self.thumb: str = json_.get("display_url")
            self.type: MediaType = get_type(self.media)
        return self.media
