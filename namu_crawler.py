import requests
from bs4 import BeautifulSoup
import re

class NamuCrawler(object):
    def __init__(self, url, hop):
        self.url = url
        self.hop = hop # 현재 문서가 몇번째 hop(depth)으로 크롤링 되고 있는지
        self.session = requests.Session()
        html_doc = self.session.get(url)
        self.soup = BeautifulSoup(html_doc.text, 'html.parser')

    def construct_toc(self):
        """## 목차(TOC) 정보 추출 및 TOC 딕셔너리 구성"""
        toc = self.soup.find("div", class_ = 'toc-indent')
        self.toc_dict = dict()

        """만약 프로필이 있는 문서라면 가장 앞에 구성"""
        html_str = str(self.soup)
        start_pos = html_str.find(str('<body>')) + len(str('<body>'))
        toc_str = str(self.soup.find("div", class_='wiki-macro-toc'))
        end_pos = html_str.find(toc_str)
        between_content = html_str[start_pos:end_pos]
        soup_between = BeautifulSoup(between_content, 'html.parser')

        if len(profile := soup_between.find_all('div', class_ = 'wiki-table-wrap table-right')) > 0:
            self.toc_dict['s-p'] = (("0.",'PROFILE'), profile[-1]) # dictionary의 첫번째 아이템으로 넣기

        
        """목차 아이템들을 하나씩 딕셔너리에 저장(key = s-#.#.#, value = (목차 명, 목차 element))"""
        pattern = r'^(\d+\.)+' # 제목 파싱용 패턴

        for i, e in enumerate(toc.find_all("span", class_  = "toc-item")):
            item_value = e.get_text()
            numbers = re.match(pattern, item_value).group()
            text = re.sub(pattern, '', item_value).strip()
            self.toc_dict[e.find('a')['href'].replace("#", "")] = ((numbers, text), self.soup.find('a', id=e.find('a')['href'].replace("#", "")))

        """마지막 원소로 각주영역 저장, 없다면 None 저장"""
        self.toc_dict['s-f'] = (("EOD.", 'FOOTNOTES'), self.soup.find("div", class_ = 'wiki-macro-footnote')) # 마지막엔 각주 영역

    def get_doc_title(self):
        return self.soup.find("a", href = "/w/"+self.url.split("/w/")[-1].split("?")[0]).get_text()

    def print_toc(self):
        """목차 프린트용 메서드"""
        print(f"\nDocument of {self.get_doc_title()}\n")
        print("\n================== Table of Contents  ==================\n")
        for k, v in self.toc_dict.items():
            num = v[0][0].count(".")
            if num == 0:
                print(v[0][0] + " " + v[0][1])
            else:
                print("".join(["\t"] * (num - 1)) + v[0][0] + " " + v[0][1])

    def strip_footnotes(slef, ele):
        """각주를 벗겨 텍스트에 삽입하는 함수"""
        content_list = []
        prv_tag = None
        for c in ele.descendants:
            if c.name == 'a' and 'wiki-fn-content' in c.get('class', []):
                # 'wiki-fn-content' 클래스를 가진 'a' 태그를 리스트에 추가
                content_list.append(f"({c['href']}; {c['title']})")
                prv_tag = True
            elif isinstance(c, str):
                # 텍스트 노드를 리스트에 추가
                if prv_tag == True:
                    prv_tag = False
                    continue
                content_list.append(c.string.strip())
                prv_tag = False
        return "".join(content_list)

    def get_content_between_tags(self, head, start_tag, end_tag):
        """두개의 태그 사이의 wiki-paragraph 정보 추출"""
        html_str = str(self.soup)

        # 시작 태그와 끝 태그의 위치를 찾아 사이의 컨텐츠를 추출, 임시 soup로 만듦
        start_pos = html_str.find(str(start_tag))
        end_pos = html_str.find(str(end_tag))
        between_content = html_str[start_pos:end_pos]
        soup_between = BeautifulSoup(between_content, 'html.parser')

        # wiki-paragraph를 가진 엘리먼트를 수집, 텍스트 컨텐츠 추출
        elements_between = soup_between.find_all('div', class_='wiki-paragraph')

        if len(elements_between) == 0:
            # 설명이 아예 없는 경우 아래 안내 메세지 반환
            return (head, "해당 섹션에 대한 설명이 없거나 하위 문서로 대체됩니다.")
        elif (ext_icon := elements_between[0].find("img", alt = '상세 내용 아이콘')) != None:
            # 타 문서로 설명이 대체된 경우엔 링크 반환
            ext_link = elements_between[0].find("a", class_ = "wiki-link-internal")['href']
            return (head, ext_link)
        else: 
            # 설명이 있는 경우엔 get_text()로 텍스트 반환
            text_content = []
            for element in elements_between:
                # 만약 펼치기/접기 버튼이 있으면 그냥 넘어가기 : 데이터가 중복임
                if element.find("dl", class_ = 'wiki-folding') != None:
                    continue
                # 만약 각주가 있는 엘리먼트라면 각주를 strip하는 함수 적용
                elif element.find("a", class_ = 'wiki-fn-content') != None:
                    text_content.append(self.strip_footnotes(element))
                #아니면 그냥 일반 get_text() 적용
                else:
                    text_content.append(element.get_text())
            return (head, text_content)
        

    def get_item_and_next(self, target_key):
        """toc_dict에서 현재 헤드의 다음 헤드 값을 반환"""
        keys = list(self.toc_dict.keys())
        values = list(self.toc_dict.values())
        
        if target_key in self.toc_dict:
            index = keys.index(target_key)
            if index < len(keys) - 1:
                return keys[index + 1], values[index + 1]
            else:
                return {keys[index]: values[index]}  # 마지막 키인 경우 다음 아이템이 없음
        else:
            return None

    def get_content_heading(self, heading_idx):
        """헤드 값의 컨텐츠 내용을 반환"""
        start_tag = self.toc_dict.get(heading_idx)[1]
        try:
            end_tag = self.get_item_and_next(heading_idx)[1][1] 
        except(KeyError): #마지막 헤딩(보통 각주영역)의 경우엔 직접 로딩
            if self.toc_dict.get(heading_idx)[1] == None: # 각주가 없는 문서
                return (self.toc_dict.get(heading_idx)[0], None)
            else:
                return (self.toc_dict.get(heading_idx)[0], self.toc_dict.get(heading_idx)[1].get_text())
        content = self.get_content_between_tags(head = self.toc_dict.get(heading_idx)[0], start_tag= start_tag, end_tag= end_tag)

        return content