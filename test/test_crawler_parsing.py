import sys
import os
from bs4 import BeautifulSoup

# Add current directory to path
sys.path.append(os.getcwd())

from namu_crawler import NamuCrawler
import unittest.mock as mock

class LocalNamuCrawler(NamuCrawler):
    def __init__(self, file_path, url, hop=0):
        super().__init__(url, hop)
        
        # Load from file instead of URL
        with open(file_path, 'r', encoding='utf-8') as f:
            html_text = f.read()

        with open("dummy_namu.html", 'r', encoding='utf-8') as f:
            self.tbl_html = f.read()
            
        self.soup = BeautifulSoup(html_text, 'html.parser')
        
        # Mock LLM and environment setup
        # self.llm = mock.MagicMock()
        # Mocking the invoke method of the chain (which is called insde llm_parse) is tricky because llm_parse constructs the chain internally.
        # Instead, we will mock the invoke method of the llm object itself, as that's what the chain eventually calls.
        # However, since line 326: chain = prompt | self.llm | StrOutputParser()
        # The chain.invoke() will call self.llm.invoke(). 
        # We need to configure the mock to return a valid response object that StrOutputParser can handle.
        
        # mock_response = mock.MagicMock()
        # mock_response.content = "### Mocked Markdown Output"
        # self.llm.invoke.return_value = mock_response

    def test_clean_nested_html(self):
        """Unit test for clean_nested_html"""
        print("\n--- Testing clean_nested_html ---")
        
        raw_html = """
        <div>
            <img alt="Flag">
            <noscript><img alt="Duplicate"></noscript>
            <p>Line 1<br>Line 2</p>
            <hr>
            <table>
                <tr style="color:red"><td>Cell</td></tr>
            </table>
        </div>
        """
        cleaned = self.clean_nested_html(raw_html)
        print(f"Cleaned HTML:\n{cleaned.strip()}")
        
        # assertions
        if "(icon: Flag)" in cleaned: print("PASS: Icon marker found")
        else: print("FAIL: Icon marker missing")
        
        if "Duplicate" not in cleaned: print("PASS: Noscript removed")
        else: print("FAIL: Noscript persisted")
        
        if "\\n" in cleaned: print("PASS: BR tag converted")
        else: print("FAIL: BR tag conversion failed")
        
        if "|" in cleaned: print("PASS: HR tag converted")
        else: print("FAIL: HR tag conversion failed")

    def test_llm_parse(self):
        """Unit test for llm_parse flow"""
        print("\n--- Testing llm_parse (Mocked) ---")
        html = self.tbl_html
        result = self.llm_parse(html)
        print(f"LLM Parse Result: {result}")
        
        # if result == "### Mocked Markdown Output":
        #     print("PASS: Mocked response received")
        # else:
        #     print("FAIL: Unexpected response")

if __name__ == "__main__":
    file_path = "rose_html.txt"
    # Namuwiki URL for Rosé to satisfy url parsing in get_doc_title etc.
    url = "https://namu.wiki/w/%EB%A1%9C%EC%A0%9C(BLACKPINK)"
    
    print(f"--- Evaluating NamuCrawler with {file_path} (Synthetic Data) ---")
    
    try:
        crawler = LocalNamuCrawler(file_path, url)
        
        # 0. Run Unit Tests (New Functions)
        crawler.test_clean_nested_html()
        crawler.test_llm_parse()

        # 1. Test TOC Construction
        print("\n--- Testing TOC Construction ---")
        success = crawler.construct_toc()
        print(f"TOC Construction: {'Success' if success else 'Failed'}")
        
        if success:
            crawler.print_toc()
            
            # 2. Test Content Extraction
            print("\n--- Testing PROFILE Extraction ---")
            if 's-p' in crawler.toc_dict:
                # This will internally call llm_parse, which uses our mock
                heading, content = crawler.get_content_heading('s-p')
                print(f"Heading: {heading}")
                print(f"Content Snippet: {str(content)[:500]}...")
            else:
                print("PROFILE section not found in toc_dict.")

            # Test a regular section
            first_section_key = list(crawler.toc_dict.keys())[1] if len(crawler.toc_dict) > 1 else None
            if first_section_key:
                print(f"\n--- Testing Section Extraction: {first_section_key} ---")
                heading, content = crawler.get_content_heading(first_section_key)
                print(f"Heading: {heading}")
                print(f"Content Snippet: {str(content)[:500]}...")

    except Exception as e:
        print(f"Error during evaluation: {e}")
        import traceback
        traceback.print_exc()
