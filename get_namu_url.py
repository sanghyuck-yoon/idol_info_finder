import pprint
from googleapiclient.discovery import build
import re

class GetNamuUrl:
    """입력한 검색어와 가장 일치하는 나무위키 페이지 반환"""
    
    def __init__(self, google_api_key, search_engine_key, verbose = False):
        """API 환경 설정"""
        self.google_api_key = google_api_key
        self.search_engine_key = search_engine_key
        self.verbose = verbose

    def get_url(self, query, siteDomain = "https://namu.wiki/w/"):
        "페이지 URL 반환"
        
        service = build(
        "customsearch", "v1", developerKey=self.google_api_key 
        )
        
        res = (
        service.cse()
        .list(
            q=query,
            cx=self.search_engine_key,
            siteSearch=siteDomain,
            siteSearchFilter='i',
            cr = 'countryKR' ,
            hl = 'ko',
            orTerms = '데뷔'
            
        )
        .execute()
        )
        
        if self.verbose == True:
            pprint.pprint(res['searchInformation'])
        
        if int(res['searchInformation']['totalResults']) == 0:
            """최초 입력 검색어로 검색 실패 시 수정된 검색어로 재검색 시도"""
            
            # Regular expression to capture everything before " site"
            pattern = r'^(.*?) site'

            try:
                text = res['spelling']['correctedQuery']
                
                # Using re.search to find the match
                match = re.search(pattern, text)

                # Extracting and printing the result
                if match:
                    adj_query = match.group(1)
                    
                    res = (
                    service.cse()
                    .list(
                        q=adj_query,
                        cx=self.search_engine_key,
                        siteSearch=siteDomain,
                        siteSearchFilter='i',
                        cr = 'countryKR' ,
                        hl = 'ko',
                        orTerms = '데뷔'
                        
                    )
                    .execute()
                    )
                    
            except:
                print("Can't Not found Urls from keyword") #수정된 검색어가 없는 경우

        url = res['items'][0]['formattedUrl']
        url = re.sub(r'//en\.', '//', url) #영문 페이지 반환 시, 한국어 페이지로 반환하도록 url 변경
                
        return url
