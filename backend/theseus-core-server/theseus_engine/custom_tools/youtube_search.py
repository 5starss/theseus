import asyncio
import json
from pathlib import Path
from typing import List

from playwright.async_api import async_playwright
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult
from pydantic import BaseModel, Field

class YoutubeSearchToolInput(BaseModel):
    query: str = Field(..., description="유튜브에서 검색할 검색어")
    max_results: int = Field(default=5, description="가져올 최대 영상 개수")

class YoutubeSearchTool(BaseTool):
    name = "youtube_search"
    description = "유튜브에서 검색어를 입력받아 관련 영상의 URL 목록을 반환합니다."
    input_model = YoutubeSearchToolInput
    permission_level = 1
    example_queries = ["유튜브에서 'Python' 검색해줘", "최신 뉴스 영상 찾아줘", "Rickroll 영상 보여줘"]

    async def execute(self, arguments: YoutubeSearchToolInput, context: ToolExecutionContext) -> ToolResult:
        query = arguments.query
        max_results = arguments.max_results
        
        # Playwright를 사용하여 스크래핑 수행
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                # 유튜브 검색 URL 생성 (검색어 인코딩 포함)
                # 쿼리를 URL safe하게 만들기 위해 간단한 처리 (실제로는 urllib.parse.quote 권장)
                safe_query = query.replace(" ", "+")
                search_url = f"https://www.youtube.com/results?search_query={safe_query}"
                await page.goto(search_url)
                
                # 페이지 로딩 대기
                await page.wait_for_selector("a#video-title")
                
                # 영상 URL 추출
                video_elements = await page.query_selector_all("a#video-title")
                urls = []
                
                for element in video_elements:
                    if len(urls) >= max_results:
                        break
                    
                    href = await element.get_attribute("href")
                    if href and "/watch?v=" in href:
                        # 상대 경로를 절대 경로로 변환
                        full_url = href if href.startswith("http") else f"https://www.youtube.com{href}"
                        # 불필요한 파라미터 제거 (깔끔한 URL을 위해)
                        clean_url = full_url.split("&")[0]
                        if clean_url not in urls:
                            urls.append(clean_url)
                
                await browser.close()
                
                # CRITICAL FIX: 결과값을 반드시 JSON String으로 변환하여 반환
                # Pydantic validation error (input should be a valid string) 해결
                result_data = {"urls": urls}
                return ToolResult(output=json.dumps(result_data, ensure_ascii=False))
                
            except Exception as e:
                if browser:
                    await browser.close()
                return ToolResult(output=f"Error during scraping: {str(e)}", is_error=True)
