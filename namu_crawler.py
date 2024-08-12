# pylint: disable=trailing-whitespace, line-too-long
"""Namuwiki crawler class"""
import re
import requests
from bs4 import BeautifulSoup

class NamuCrawler():
    """나무 위키 문서 크롤러 클래스"""
    def __init__(self, url, hop):
        self.url = url
        self.hop = hop # 현재 문서가 몇번째 hop(depth)으로 크롤링 되고 있는지
        self.session = requests.Session()
        html_doc = self.session.get(url)
        self.soup = BeautifulSoup(html_doc.text, 'html.parser')
        self.toc_dict = {}

    def construct_toc(self):
        """## 목차(TOC) 정보 추출 및 TOC 딕셔너리 구성"""
        toc = self.soup.find("div", class_ = 'toc-indent')

        html_str = str(self.soup)
        start_pos = html_str.find(str('<body>')) + len(str('<body>'))
        toc_str = str(self.soup.find("div", class_='wiki-macro-toc'))
        end_pos = html_str.find(toc_str)
        between_content = html_str[start_pos:end_pos]
        soup_between = BeautifulSoup(between_content, 'html.parser')


        #만약 프로필이 있는 문서라면 가장 앞에 구성
        if len(profile := soup_between.find_all('div', class_ = 'wiki-table-wrap table-right')) > 0:
            self.toc_dict['s-p'] = (("0.",'PROFILE'), profile[-1]) # dictionary의 첫번째 아이템으로 넣기

        #목차 아이템들을 하나씩 딕셔너리에 저장(key = s-#.#.#, value = (목차 명, 목차 element))
        pattern = r'^(\d+\.)+' # 제목 파싱용 패턴

        for ele in toc.find_all("span", class_  = "toc-item"):
            item_value = ele.get_text()
            numbers = re.match(pattern, item_value).group()
            text = re.sub(pattern, '', item_value).strip()
            self.toc_dict[ele.find('a')['href'].replace("#", "")] = (
                (numbers, text), self.soup.find('a', id=ele.find('a')['href'].replace("#", ""))
            )

        #마지막 원소로 각주영역 저장, 없다면 None 저장
        self.toc_dict['s-f'] = (# 마지막엔 각주 영역
            ("EOD.", 'FOOTNOTES'), self.soup.find("div", class_ = 'wiki-macro-footnote')
        ) 

    def get_doc_title(self) -> str:
        """URL에서 현재 문서의 타이틀(주제) 반환 """
        return self.soup.find("a", href = "/w/"+self.url.split("/w/")[-1].split("?")[0]).get_text()

    def print_toc(self):
        """포맷화된 목차 프린트 메서드"""
        print(f"\nDocument of {self.get_doc_title()}\n")
        print("\n================== Table of Contents  ==================\n")
        for val in self.toc_dict.values():
            num = val[0][0].count(".")
            index = val[0][0]
            toc_item = val[0][1]
            if num == 0:
                print(index + " " + toc_item)
            else:
                print("".join(["\t"] * (num - 1)) + index + " " + toc_item)

    def get_ancestor_items(self, toc_index, level = None):
        """하나의 목차 item에 대한 상위 목차들을 모두 찾아 반환(현재 페이지 한정))"""
        toc_index = toc_index[:-1] if toc_index [-1] == "." else toc_index
        if level is None:
            level = len(toc_index.split(".")) - 1
            
        cur_toc_index = toc_index
        ancestors = []
        for i in range(level):
            ancestors.insert(
                0, self.toc_dict.get(f"s-{'.'.join(cur_toc_index.split(sep = '.')[:-1])}")[0]
            )
            cur_toc_index = ancestors[-1][0][:-1]  
        toc_items = "/".join([i[1] for i in ancestors])
        return toc_items
    
    def strip_footnotes(self, ele) -> str:
        """각주를 벗겨 텍스트에 삽입하는 함수"""
        content_list = []
        prv_tag = None
        for child in ele.descendants:
            if child.name == 'a' and 'wiki-fn-content' in child.get('class', []):
                # 'wiki-fn-content' 클래스를 가진 'a' 태그를 리스트에 추가
                content_list.append(f"({child['href']}; {child['title']})")
                prv_tag = True
            elif isinstance(child, str):
                # 텍스트 노드를 리스트에 추가
                if prv_tag is True:
                    prv_tag = False
                    continue
                content_list.append(child.string.strip())
                prv_tag = False
        return "".join(content_list)
    
    def strip_table(self, ele) -> str:
        """테이블을 comma-seperated 스타일로 변환하여 반환"""
        content_list = []
        for content in ele.find_all("div", class_ = 'wiki-paragraph'):
            if content.find("a", class_ = 'wiki-fn-content') is not None: ## 각주가 있을 경우
                content_list.append(self.strip_footnotes(content))
            else:
                content_list.append(content.get_text() + ",")
        return  "".join(content_list)
    
    def strip_ex_links(self, ele) -> str:
        """링크를 벗겨 텍스트에 삽입하는 함수, 추가 개발 필요"""
        return ele.get_text()

    def get_content_between_tags(self, head, start_tag, end_tag):
        """두개의 태그 사이의 wiki-paragraph 정보 추출"""
        html_str = str(self.soup)

        # 시작 태그와 끝 태그의 위치를 찾아 사이의 컨텐츠를 추출, 임시 soup로 만듦
        start_pos = html_str.find(str(start_tag))
        if head[1] == "PROFILE": ## 프로필 이라면 목차 전까지
            end_pos = html_str.find(str('<div class="wiki-macro-toc"'))
        else:
            end_pos = html_str.find(str(end_tag))
        between_content = html_str[start_pos:end_pos]
        soup_between = BeautifulSoup(between_content, 'html.parser')

        # 헤더가 PROFILE인 경우: 첫번째 테이블만 가져오기
        if head[1] == "PROFILE":
            content = self.strip_table(soup_between.find("table"))
            return (head, [content])
        # PROFILE이 아닌 경우: 추출할 원소들 리스트에 부모의 태그가 td가 아닌 경우 wiki-paragraph를 가진 엘리먼트를 수집, 거기에 wiki-table까지 추가로 넣기
        elements_between = [ele for ele in soup_between.find_all('div', class_='wiki-paragraph') if ele.find_parent().name != "td"]
        elements_between += list(soup_between.find_all('table', class_ = 'wiki-table'))

        if len(elements_between) == 0 or (len(elements_between) == 1 and elements_between[0].get_text() == ""):
            # 설명이 아예 없는 경우 아래 안내 메세지 반환
            return (head, ["해당 섹션에 대한 설명이 없거나 하위 문서로 대체됩니다."])
        if (elements_between[0].find("img", alt = '상세 내용 아이콘')) is not None:
            # 타 문서로 설명이 대체된 경우엔 링크 반환
            ext_link = elements_between[0].find("a", class_ = "wiki-link-internal")['href']
            return (head, ext_link)
         
        # 설명이 있는 경우엔 get_text()로 텍스트 반환
        text_content = []
        for element in elements_between:
            # 만약 펼치기/접기 버튼이 있으면 그냥 넘어가기 : 데이터가 중복임
            if element.find("dl", class_ = 'wiki-folding') is not None:
                continue
            
            # 만약 테이블 요소를 가지고 있거나 자체가 테이블 클래스라면 테이블을 strip하는 함수 적용
            if element.find("table", class_ = 'wiki-table') is not None or element.get('class')[0] == 'wiki-table':
                text_content.append(self.strip_table(element))

            # 만약 각주가 있는 엘리먼트라면 각주를 strip하는 함수 적용
            elif element.find("a", class_ = 'wiki-fn-content') is not None:
                text_content.append(self.strip_footnotes(element))
            
            # 외부 링크가 있으면 링크를 strip 하는 함수 적용 => 추가 개발 필요
            # elif element.find("a", class_ = 'wiki-link-external') is not None:
            #     text_content.append(self.strip_ex_links(element))

            

            else: #아니면 그냥 일반 get_text() 적용
                text_content.append(element.get_text())
                
        return (head, text_content)
        

    def get_next_item(self, target_key):
        """toc_dict에서 현재 헤드의 다음 헤드 값을 반환"""
        keys = list(self.toc_dict.keys())
        values = list(self.toc_dict.values())
        
        if target_key in self.toc_dict:
            index = keys.index(target_key)
            if index < len(keys) - 1:
                return keys[index + 1], values[index + 1]
            return {keys[index]: values[index]}  # 마지막 키인 경우 다음 아이템이 없음
        return None

    def get_content_heading(self, heading_idx):
        """헤드 값의 컨텐츠 내용을 반환"""
        start_tag = self.toc_dict.get(heading_idx)[1]
        try:
            end_tag = self.get_next_item(heading_idx)[1][1] 
        except KeyError: #마지막 헤딩(보통 각주영역)의 경우엔 직접 로딩
            if self.toc_dict.get(heading_idx)[1] is None: # 각주가 없는 문서
                return (self.toc_dict.get(heading_idx)[0], None)
            return (self.toc_dict.get(heading_idx)[0], [self.toc_dict.get(heading_idx)[1].get_text()])
        return self.get_content_between_tags(head = self.toc_dict.get(heading_idx)[0], start_tag= start_tag, end_tag= end_tag)
    