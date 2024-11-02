import discord
from discord.ext import tasks
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import os
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ProlificBot')

class ProlificBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        # Get configuration from environment variables
        self.channel_id = int(os.getenv('CHANNEL_ID'))
        self.last_studies = set()
        self.session = None
        
    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        self.check_prolific_studies.start()

    async def on_ready(self):
        logger.info(f'Bot logged in as {self.user}')
        channel = self.get_channel(self.channel_id)
        if channel:
            await channel.send("🟢 Prolific Study Monitor is now online!")

    def create_study_embed(self, study_data):
        embed = discord.Embed(
            title="💰 New Prolific Study! 📚",
            url="https://app.prolific.co/studies",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="Reward", value=f"£{study_data['reward']}", inline=True)
        embed.add_field(name="Places", value=study_data['places_left'], inline=True)
        if 'duration' in study_data:
            embed.add_field(name="Duration", value=f"{study_data['duration']} minutes", inline=True)
        
        embed.set_footer(text="Click the title to go to Prolific")
        return embed

    async def fetch_prolific_data(self):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        try:
            async with self.session.get('https://app.prolific.co/studies', headers=headers) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.error(f"Failed to fetch Prolific data: Status {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching Prolific data: {e}")
            return None

    @tasks.loop(minutes=1)  # Check every minute
    async def check_prolific_studies(self):
        try:
            channel = self.get_channel(self.channel_id)
            if not channel:
                return

            html_content = await self.fetch_prolific_data()
            if not html_content:
                return

            soup = BeautifulSoup(html_content, 'html.parser')
            study_elements = soup.find_all('div', {'data-study-id': True})
            
            current_studies = {}
            for element in study_elements:
                study_id = element.get('data-study-id')
                reward = element.find('span', {'class': 'study-reward'}).text.strip()
                places = element.find('span', {'class': 'places-left'}).text.strip()
                duration = element.find('span', {'class': 'study-duration'}).text.strip()
                
                current_studies[study_id] = {
                    'reward': reward,
                    'places_left': places,
                    'duration': duration
                }

            # Check for new studies
            for study_id, study_data in current_studies.items():
                if study_id not in self.last_studies:
                    embed = self.create_study_embed(study_data)
                    await channel.send("@everyone New study available!", embed=embed)
                    self.last_studies.add(study_id)

            # Clean up old studies
            self.last_studies = {study for study in self.last_studies if study in current_studies}

        except Exception as e:
            logger.error(f"Error in check_prolific_studies: {e}")
            
    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

def main():
    bot = ProlificBot()
    bot.run(os.getenv('DISCORD_TOKEN'))

if __name__ == "__main__":
    main()