# pylint: disable=trailing-whitespace, line-too-long
"""Namuwiki crawler class"""
import re
import requests
from bs4 import BeautifulSoup
import urllib.parse
import os
from operator import itemgetter
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.output_parsers import JsonOutputParser

class NamuCrawler():
    """나무 위키 문서 크롤러 클래스"""
    def __init__(self, url, hop):
        self.url = url
        self.hop = hop # 현재 문서가 몇번째 hop(depth)으로 크롤링 되고 있는지
        self.session = requests.Session()
        html_doc = self.session.get(url)
        self.soup = BeautifulSoup(html_doc.text, 'html.parser')
        self.toc_dict = {}

        #파싱용 LLM 모델 셋팅
        os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
        os.environ['LANGCHAIN_API_KEY'] = os.getenv("LANGCHAIN_API_KEY")

        self.llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = "langchain-academy"
        
    def construct_toc(self) -> bool:
        """## 목차(TOC) 정보 추출 및 TOC 딕셔너리 구성"""
        if (toc := self.soup.find("div", class_ = 'toc-indent')) == None:
            return False # "해당 문서를 찾을 수 없습니다."의 비정상 경우 False로 종료


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
        return True # 정상 종료
    
    def get_doc_title(self) -> str:
        """URL에서 현재 문서의 타이틀(주제) 반환 """
        topic = self.url.split("/w/")[-1].split("?")[0]
        # topic = urllib.parse.unquote(topic)
        return self.soup.find("a", href = "/w/"+topic).get_text()

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
        
        #문서 인덱스가 아무 이유없이 맨 뒤에 .만 있는 경우
        toc_index = toc_index[:-1] if toc_index [-1] == "." else toc_index

        if level is None:
            level = len(toc_index.split(".")) - 1
            
        cur_toc_index = toc_index
        ancestors = []
        for i in range(level):
            try:
                ancestors.insert(
                    0, self.toc_dict.get(f"s-{'.'.join(cur_toc_index.split(sep = '.')[:-1])}")[0]
                )
            except:
                return self.toc_dict.get(f"s-{'.'.join(cur_toc_index.split(sep = '.'))}")[0][1] #문서 인덱스에 오류가 발생하면 일딴 현재 위치를 메타 데이터로 반환
            
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

        # print(head[1]) #작업 위치 프린트

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
            # content = self.strip_table(soup_between.find("table"))
            tbl_origin = soup_between.find("table")
            
            # PROFILE에서는 <dl>로 감춰둔 내용은 필요 없으므로 미리 제거
            dl_tags = tbl_origin.find_all('dl')

            # <dl> 태그와 포함된 내용을 제거
            for dl_tag in dl_tags:
                dl_tag.decompose()  # 태그 삭제

            transformed_tbl = self.transform_nested_table(tbl_origin)
            tbl_array = self.table_to_array(transformed_tbl)
            content = self.tbl_array_to_json(tbl_array)
            return (head, [content])
        # PROFILE이 아닌 경우: 추출할 원소들 리스트에 부모의 태그가 td가 아닌 경우 wiki-paragraph를 가진 엘리먼트를 수집, 거기에 wiki-table까지 추가로 넣기
        elements_between = [ele for ele in soup_between.find_all('div', class_='wiki-paragraph') if ele.find_parent().name != "td"]
        elements_between += self.get_outer_tables(soup_between)
        # elements_between += list(soup_between.find_all('table', class_ = 'wiki-table'))

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

            # 만약 펼치기/접기 버튼이 있으면 그냥 넘어가기 : 데이터가 중복임 => 안에 있는 테이블 파싱 진행 필요하여 생략
            # if element.find("dl", class_ = 'wiki-folding') is not None:
            #     continue
            
            # 만약 테이블 요소를 가지고 있거나 자체가 테이블 클래스라면 테이블을 파싱 & LLM으로 복구하는 코드로 변경 예정
            if element.find("table", class_ = 'wiki-table') is not None or element.get('class')[0] == 'wiki-table':
                #     text_content.append(self.strip_table(element))
                transformed_tbl = self.transform_nested_table(element)
                tbl_array = self.table_to_array(transformed_tbl)
                text_content.append(self.tbl_array_to_json(tbl_array))

            # 만약 각주가 있는 엘리먼트라면 각주를 strip하는 함수 적용
            elif element.find("a", class_ = 'wiki-fn-content') is not None:
                text_content.append(self.strip_footnotes(element))
            
            # 외부 링크가 있으면 링크를 strip 하는 함수 적용 => 추가 개발 필요
            # elif element.find("a", class_ = 'wiki-link-external') is not None:
            #     text_content.append(self.strip_ex_links(element))    

            else: #아니면 그냥 일반 get_text() 적용
                text_content.append(element.get_text())
                
        return (head, text_content)
        
    def get_outer_tables(self, soup):
        """가장 바깥쪽 table 태그만 파싱하는 함수"""
        outer_tables = []
        for table in soup.find_all("table", class_ = 'wiki-table'):
            # 부모가 다른 table이 아닌 경우에만 추가
            if not table.find_parent("table", class_ = 'wiki-table'):
                outer_tables.append(table)
        return outer_tables


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
    
    def transform_nested_table (self, tbl):
        """
            <table> 하위에 <dl>로 숨겨진 테이블을 중첩한 경우
            <dl> 하위의 테이블을 파싱한 뒤, 중첩된 테이블을 삭제
            파싱한 하위 테이블은 <dl>이 속한 <tr> 바로 뒤에 삽입하여 부모 테이블의 구조로 병합
            적용 가능한 범위는 2 depth 중첩인 경우만, 그 이상 중첩은 처리할 수 없음
        """
    
        tbl_simple = self.simplify_table(tbl)
        
        # <dl> 내부에 중첩된 <table>을 처리
        for dl in tbl_simple.find_all("dl"):
            nested_table = dl.find("table")  # <dl> 내부의 <table> 찾기
            if nested_table:
                # 중첩된 <table>의 <tr> 태그를 추출
                nested_rows = nested_table.find_all("tr")
                parent_tbdy = dl.find_parent("tbody")  # <dl>의 부모 <tbody> 찾기
                if parent_tbdy is None: # <dl>의 부모가 없으면 <table> 중첩 아니므로 생략
                    continue
                parent_tr = dl.find_parent('tr') # <dl>의 부모 <tr> 찾기
                
                # 병합된 컬럼인 dl.dt는 신규 tr.dt로 생성 후 append 시키기
                new_tr = BeautifulSoup().new_tag('tr')
                new_td = BeautifulSoup().new_tag('td')
                new_td.string = dl.dt.text
                new_tr.append(new_td)
                parent_tbdy.append(new_tr)

                # 파싱한 <tr> 태그를 부모 <tbody>에 추가
                for tr in nested_rows:
                    parent_tbdy.append(tr)

                # 중첩된 <table>를 포함한 tr 태그를 제거
                parent_tr.decompose()

        # 병합한 tbl 반환
        return tbl_simple

    def table_to_array (self, tbl):
        """
            HTML Table을 2차원 배열로 치환 -> LLM으로 JSON 변환하는 함수
            병합된 행이 있으면 행을 먼저 분할하고 각 행에 넣어준 뒤에 2차원 배열로 변환
            병합된 열은 적용하지 않음.
        """

        # 가장 바깥쪽 테이블 태그만 가져오기
        # table = ele.find_all('table', class_='wiki-table')[0]

        # Initialize variables
        rows = tbl.find_all('tr')
        parsed_data = [] # 파싱한 결과가 들어갈 2차원 배열
        rowspans = {}  # rowspan이 있으면 병합된 행이 존재, 병합된 행의 idx와 병합된 행의 수를 체크해서 병합을 풀어주는데 사용

        # row 단위로 접근하여 컬럼을 파싱
        for row_idx, row in enumerate(rows):
            cells = row.find_all('td')
            parsed_row = []
            col_idx = 0

            for cell in cells:
                # rowspan이 td 내에 있는 경우 rowspans를 이용해서 직전 행에 있는 중복 값을 새로운 행에 적용
                while col_idx in rowspans and rowspans[col_idx] > 0:
                    parsed_row.append(parsed_data[-1][col_idx])
                    rowspans[col_idx] -= 1
                    col_idx += 1

                # 그 외의 경우 cell의 값을 그대로 가져옴
                cell_value = cell.get_text(strip=True)

                # 현재 td tag에 rowspan이 적용됐는지 확인하고 적용됐다면 rowspans에 추가
                rowspan = int(cell.get('rowspan', 1))
                if rowspan > 1:
                    rowspans[col_idx] = rowspan - 1

                parsed_row.append(cell_value)
                col_idx += 1

            # Fill in any remaining rowspan cells
            while col_idx in rowspans and rowspans[col_idx] > 0:
                parsed_row.append(parsed_data[-1][col_idx])
                rowspans[col_idx] -= 1
                col_idx += 1

            parsed_data.append(parsed_row)
            
        # Print the parsed data
        # for row in parsed_data:
        #     print(row)
        
        return parsed_data

    def simplify_table(self, tbl):
        """ 
            테이블 디자인을 위한 불필요한 div 태그 제거
        """
        for div in tbl.find_all('div'):
            # 디자인 목적의 div만 제거 (단, 필요 시 보존)
            if div.get('style') and not div.get('class'):
                div.unwrap()

        # 중첩된 span 태그도 제거
        for span in tbl.find_all('span'):
            span.unwrap()
        
        # 중첩된 img 태그도 제거
        for span in tbl.find_all('img'):
            span.unwrap()
            
        # 제거하고자 하는 텍스트
        stopwords = ["행정구","속령"]

        # 특정 텍스트가 포함된 모든 태그 찾기
        for word in stopwords:
            tags_to_remove = tbl.find_all(string=lambda text: word in text)

            # 찾은 태그들 제거
            for tag in tags_to_remove:
                tag.parent.decompose()
        
        return tbl

    def tbl_array_to_json(self, arr) -> str:
        """
            LLM을 이용해서 2차원 배열을 JSON 형태로 변환하는 함수
        """

        append_row = []
        for row in arr:
            append_row.append(",".join(col for col in row))
        str_table = "\n\n ".join(row for row in append_row)

        prompt = ChatPromptTemplate.from_messages(
            [
                # role, message
                ("system", """You are an expert in data parsing and JSON conversion. Your task is to analyze and transform structured text data into properly formatted JSON objects. The data may have the following characteristics:

                        1. Some rows may be entirely empty. Ignore these rows and do not include them in the final output.
                        2. If a row has a different number of columns than the previous rows, it indicates merged cells or inconsistent formatting. Interpret these cases carefully to maintain data consistency.
                        3. Records may be structured either by rows or by columns. You need to analyze the entire dataset to determine whether the primary record structure should be row-based or column-based before generating the JSON.
                        4. Strings in the form of [\d+] are footnotes, so they do not need to be included in the output.

                        Your job is to accurately identify and handle these variations to create a clean, valid JSON output that reflects the data structure.
                        Output only the final JSON representation, without any additional explanations or text.
                        If the output format is a code block, please output it in JSON format with the code block removed.
                        """),
                ("human", """"I have a structured string representing tabular data where each row is separated by '\n\n' and columns by commas. 
                Here is the structured string:
                <string>{table}</string>
                Parse the input, then generate JSON where each subsequent row corresponds to a JSON object with the respective header keys.
        """)
            ]
        )

        # 수정된 체인 생성 코드
        chain = {
                'table': itemgetter('table') | RunnablePassthrough()
        } | prompt | self.llm | StrOutputParser()

        result = chain.invoke({"table":str_table}) 

        return result