#!/usr/bin/env python3
"""
🌐 WEB SEARCH SERVICE - асинхронный поиск в интернете
"""

import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import random
from config import WEB_SEARCH_TIMEOUT, WEB_SEARCH_RESULTS
from logger import get_logger

logger = get_logger(__name__)


class WebSearchService:
    """Асинхронный сервис поиска в интернете"""

    def __init__(self):
        logger.info("✅ WebSearchService инициализирована")
        self.timeout = aiohttp.ClientTimeout(total=WEB_SEARCH_TIMEOUT)
        self.max_results = WEB_SEARCH_RESULTS
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        ]

    def _get_headers(self):
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9',
            'DNT': '1',
        }

    async def search(self, query: str, num_results: int = 5) -> list:
        """Основной метод поиска"""
        try:
            logger.info(f"🔍 Web поиск: '{query[:50]}'...")

            # Пробуем DuckDuckGo Lite (самый стабильный)
            results = await self._search_ddg_lite(query)
            if results:
                logger.info(f"✅ DuckDuckGo: найдено {len(results)}")
                return results[:num_results]

            # Fallback: Bing
            logger.debug("🔍 Fallback на Bing...")
            results = await self._search_bing(query)
            if results:
                logger.info(f"✅ Bing: найдено {len(results)}")
                return results[:num_results]

            # Fallback: Google
            logger.debug("🔍 Fallback на Google...")
            results = await self._search_google(query)
            if results:
                logger.info(f"✅ Google: найдено {len(results)}")
                return results[:num_results]

            logger.warning(f"⚠️ Результаты не найдены")
            return []

        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            return []

    async def _search_ddg_lite(self, query: str) -> list:
        """DuckDuckGo Lite - самый стабильный"""
        try:
            url = "https://lite.duckduckgo.com/lite/"
            data = {'q': query}
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, data=data, headers=self._get_headers()) as response:
                    if response.status != 200:
                        return []

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    results = []
                    for row in soup.find_all('tr')[1:]:  # Пропускаем заголовок
                        try:
                            cells = row.find_all('td')
                            if len(cells) >= 2:
                                link = cells[0].find('a')
                                if link:
                                    title = link.text.strip()
                                    url = link.get('href', '')
                                    snippet = cells[1].text.strip() if len(cells) > 1 else ''
                                    
                                    if title and url and len(snippet) > 20:
                                        results.append({
                                            'title': title,
                                            'url': url,
                                            'snippet': snippet
                                        })
                        except:
                            continue

                    return results[:self.max_results]

        except Exception as e:
            logger.debug(f"🔍 DuckDuckGo: {e}")
            return []

    async def _search_bing(self, query: str) -> list:
        """Bing поиск"""
        try:
            url = f"https://www.bing.com/search?q={quote_plus(query)}"
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self._get_headers()) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    results = []
                    for item in soup.select('li.b_algo')[:self.max_results]:
                        try:
                            h2 = item.find('h2')
                            link = h2.find('a') if h2 else None
                            snippet = item.find('p')
                            
                            if link and snippet:
                                results.append({
                                    'title': link.text.strip(),
                                    'url': link.get('href', ''),
                                    'snippet': snippet.text.strip()
                                })
                        except:
                            continue

                    return results

        except Exception as e:
            logger.debug(f"🔍 Bing: {e}")
            return []

    async def _search_google(self, query: str) -> list:
        """Google поиск"""
        try:
            url = f"https://www.google.com/search?q={quote_plus(query)}"
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self._get_headers()) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    results = []
                    for g in soup.select('div.g')[:self.max_results]:
                        try:
                            link = g.find('a')
                            h3 = g.find('h3')
                            
                            if link and h3:
                                snippet_div = g.select_one('div.s, span.st')
                                snippet = snippet_div.text.strip() if snippet_div else ''
                                
                                if snippet and len(snippet) > 20:
                                    results.append({
                                        'title': h3.text.strip(),
                                        'url': link.get('href', ''),
                                        'snippet': snippet
                                    })
                        except:
                            continue

                    return results

        except Exception as e:
            logger.debug(f"🔍 Google: {e}")
            return []