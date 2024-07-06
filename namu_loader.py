import os
from namu_crawler import namuCrawler
from langchain_core.documents import Document
from langchain_community.document_loaders.base import BaseLoader
from typing import Iterator
import time

class NamuLoader(BaseLoader):
    """Load NamuWiki pages using `namuClawler`."""
    def __init__(self, url, max_hop, verbose = False):
        self.url = url
        self.max_hop = max_hop
        self.verbose = verbose
        self.base_nc = namuCrawler(url = self.url, hop = 0)
        self.base_nc.construct_toc()
        if (self.verbose) == True:
            self.base_nc.print_toc()

    def get_total_content(self, parent_item, sub_url, hop):
        sub_nc = namuCrawler(url = sub_url, hop = hop)
        sub_nc.construct_toc()
        # print(sub_nc.get_doc_title(), parent_item, sub_nc.hop, max_hop)
        to_return = ""
        start = time.time()
        for k, v in sub_nc.toc_dict.items():
            cur_toc_item, content = sub_nc.get_content_heading(k)
            
            if type(content) == str and f'/w/' in content: # content가 링크 대체이면서 
                if sub_nc.hop < self.max_hop: #현재 문서의 hop이 max_hop보다 적거나 같으면 더 들어가기
                    content = self.get_total_content(parent_item = parent_item, sub_url = base_url + content, hop = sub_nc.hop + 1)
                else: # max_hop과 같으면 그냥 링크로 대체한다고만 써주기
                    content = f"{cur_toc_item[1]}: 다음 문서로 대체 설명: {base_url + content}"
            else: # 일반 설명은 {현재 목차 : 설명} 꼴로 구성
                content = f'{cur_toc_item[1]}: {" ".join(content) if type(content) == list else ""}'
            
            to_return = to_return + "\n" + content + "\n"

        # if self.verbose:
        print(f"Sub document {sub_nc.get_doc_title()} done (hop : {sub_nc.hop}/{self.max_hop} \t elapsed_time: {round(time.time() - start, 1)} seconds)")
        return to_return

    def get_a_content(self, header):
        """하나의 header의 본문 내용 가져오기"""
        cur_toc_item, content = self.base_nc.get_content_heading(header)
        if content == None:
            return (cur_toc_item, None)
        elif type(content) == str and '/w/' in content: # content가 링크 대체라면
            return (cur_toc_item, self.get_total_content(parent_item = self.base_nc.toc_dict.get(header)[0], sub_url = base_url + content, hop = self.base_nc.hop + 1))
        else:
            return (cur_toc_item, " ".join(content))
        
    def lazy_load(self) -> Iterator[Document]:
        """Iterate over content items to load Documents"""
        for s, header in self.base_nc.toc_dict.items():
            ((index, toc_item), cur_content) = self.get_a_content(s)
            cur_metadata = {
                "index" : index,
                "toc_item" : toc_item
            }

            if self.verbose == True:
                print(">> ", s, header[0][1])
                print("\t", cur_content)
            yield Document(page_content= cur_content, metadata = cur_metadata)