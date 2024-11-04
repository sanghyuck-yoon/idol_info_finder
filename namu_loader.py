import os
from namu_crawler import NamuCrawler
from langchain_core.documents import Document
from langchain_community.document_loaders.base import BaseLoader
from typing import List
import time
BASE_URL = "https://namu.wiki"

class NamuLoader(BaseLoader):
    """Load NamuWiki pages using `namuClawler`."""
    def __init__(self, url, max_hop, verbose = False):
        self.url = url
        self.max_hop = max_hop
        self.verbose = verbose
        self.base_nc = NamuCrawler(url = self.url, hop = 0)
        self.base_nc.construct_toc()
        if (self.verbose) == True:
            self.base_nc.print_toc()

    def make_sub_nc(self, parent_nc, sub_url, hop, parent_meta) -> List[Document]:
        start = time.time()
        
        sub_nc = NamuCrawler(url = sub_url, hop = hop)
        
        if sub_nc.toc_dict is None:
            return None
        
        if self.verbose:
            formatted_str = f"{'  '*sub_nc.hop}Sub Doc {sub_nc.get_doc_title()}"
            print(f"{formatted_str:<50} Start (hop : {sub_nc.hop}/{self.max_hop})")
        sub_nc.construct_toc()
        to_return_docs = []
        for s, header in sub_nc.toc_dict.items():
            to_return_docs += self.get_docs(sub_nc, s, parent_meta)
        
        if self.verbose:
            print(f"{formatted_str:<50} Done! (hop : {sub_nc.hop}/{self.max_hop}, elapsed_time: {round(time.time() - start, 1)} seconds)")

        return to_return_docs
    
    def get_docs(self, nc, s, parent_meta = None) -> List[Document]:
        """본문 내용 가져오기"""
        if nc.toc_dict is None:
            return None
        
        cur_toc_item, content = nc.get_content_heading(s)
        if parent_meta == None:
            parent_page_index = ""
            parent_page_toc_item = ""
            abs_page_toc_items = (nc.get_ancestor_items(toc_index = cur_toc_item[0]) + "/" ) + cur_toc_item[1] if nc.get_ancestor_items(toc_index = cur_toc_item[0]) != '' else '' + cur_toc_item[1]
            
        else:
            parent_page_index = parent_meta['index']
            parent_page_toc_item = parent_meta['toc_item']
            abs_page_toc_items = (
                parent_meta['abs_page_toc_item'] 
                + "//" 
                + ((nc.get_ancestor_items(toc_index = cur_toc_item[0]) + "/" ) if nc.get_ancestor_items(toc_index = cur_toc_item[0]) != '' else '')
                + cur_toc_item[1]
            )
            
        meta_data = {
            "page_topic" : nc.get_doc_title(),
            "base_page_url" : parent_meta['base_page_url'] if parent_meta else nc.url,
            "parent_page_url" : parent_meta['current_page_url'] if parent_meta else None,
            "current_page_url" : nc.url,
            "page_hop" : nc.hop,

            "parent_page_index" : parent_page_index,
            "parent_page_toc_item" : parent_page_toc_item,
            "abs_page_toc_item": abs_page_toc_items,

            "index" : cur_toc_item[0],
            "toc_item" : cur_toc_item[1],
            "ancestor_toc_item" : nc.get_ancestor_items(toc_index = cur_toc_item[0])
        }

        if content == None:
            return [Document(page_content = "", metadata = meta_data)]

        elif type(content) == str and '/w/' in content: 
            # content가 링크 대체라면 
            if nc.hop + 1 <= self.max_hop: # max_hop보다 아래라면 링크로 들어가 전체 다 가져오기
                sub_docs = self.make_sub_nc(
                    parent_nc = nc, 
                    sub_url = BASE_URL + content, 
                    hop = nc.hop + 1,
                    parent_meta = meta_data
                )
                return sub_docs
            else: # 아니라면 설명으로 대체
                return  [Document(page_content = f"다음 문서로 대체 설명: {BASE_URL + content}", metadata = meta_data)]
        else:
            return [Document(page_content = " ".join(content), metadata = meta_data)]

    def lazy_load(self) -> List[Document]:
        """Iterate over content items to load Documents"""
        
        docs = []
        start = time.time()

        if self.verbose:
            print(f"Main Doc {self.base_nc.get_doc_title():<50} Start (hop : {self.base_nc.hop}/{self.max_hop})")
        

        for s in self.base_nc.toc_dict.keys():
            cur_docs = self.get_docs(self.base_nc, s)
            docs += cur_docs
        
        if self.verbose:
            print(f"Main Doc {self.base_nc.get_doc_title():<50} Done! (hop : {self.base_nc.hop}/{self.max_hop}, elapsed_time: {round(time.time() - start, 1)} seconds)")

        return docs
