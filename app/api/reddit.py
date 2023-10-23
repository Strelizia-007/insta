import os
import re
import time
from urllib.parse import urlparse

from app.core import shell
from app.core.aiohttp_tools import get_json, get_type
from app.core.scraper_config import MediaType, ScraperConfig


class Reddit(ScraperConfig):
    def __init__(self, url):
        super().__init__()
        parsed_url = urlparse(url)
        self.url: str = f"https://www.reddit.com{parsed_url.path}.json?limit=1"

    async def download_or_extract(self) -> None:
        headers: dict = {
            "user-agent": "Mozilla/5.0 (Macintosh; PPC Mac OS X 10_8_7 rv:5.0; en-US) AppleWebKit/533.31.5 (KHTML, like Gecko) Version/4.0 Safari/533.31.5"
        }
        response: dict | None = await get_json(
            url=self.url, headers=headers, json_=True
        )
        if not response:
            return

        try:
            json_: dict = response[0]["data"]["children"][0]["data"]
        except BaseException:
            return

        self.caption: str = (
            f"""__{json_["subreddit_name_prefixed"]}:__\n**{json_["title"]}**"""
        )

        self.thumb: str = json_.get("thumbnail")

        if json_.get("is_gallery"):
            self.media: list[str] = [
                val["s"].get("u", val["s"].get("gif")).replace("preview", "i")
                for val in json_["media_metadata"].values()
            ]
            self.success = True
            self.type: MediaType = MediaType.GROUP
            return

        hls: list[str] = re.findall(r"'hls_url'\s*:\s*'([^']*)'", str(json_))

        if hls:
            self.path: str = "downloads/" + str(time.time())
            os.makedirs(self.path)
            self.media: str = f"{self.path}/v.mp4"
            vid_url: str = hls[0]
            await shell.run_shell_cmd(
                f'ffmpeg -hide_banner -loglevel error -i "{vid_url.strip()}" -c copy {self.media}'
            )
            self.thumb = await shell.take_ss(video=self.media, path=self.path)
            self.success = True
            self.type: MediaType.VIDEO | MediaType.GIF = (
                MediaType.VIDEO
                if await shell.check_audio(self.media)
                else MediaType.GIF
            )
            return

        generic: str = json_.get("url_overridden_by_dest", "").strip()
        self.type: MediaType = get_type(generic)
        if self.type:
            self.media: str = generic
            self.success = True
