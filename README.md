# Idol Info Finder (Namuwiki Crawler & Parser)

나무위키에서 아이돌 정보를 수집(Crawling)하고, LLM이 이해하기 쉬운 형태(Markdown)로 파싱(Parsing)하여 BigQuery에 적재하는 프로젝트입니다. RAG(Retrieval Augmented Generation) 챗봇을 위한 고품질 데이터 파이프라인 구축을 목표로 합니다.

## 🏗️ Architecture

이 프로젝트는 다음과 같은 파이프라인으로 구성됩니다:

1.  **URL Indexing**: BigQuery(`namu_wiki.artists`)에서 수집 대상 아티스트 정보 로드.
2.  **Crawling (`NamuCrawler`)**:
    - `requests` 및 `BeautifulSoup`을 사용하여 나무위키 페이지 접근.
    - **Recursive Crawling**: 링크된 하위 문서까지 설정된 깊이(`max_hop`)만큼 탐색.
3.  **Hybrid Parsing (Core Logic)**:
    - 복잡한 HTML 테이블(프로필, 디스코그래피 등)을 LLM 기반으로 "의미론적 Markdown"으로 변환.
4.  **Loading (`NamuLoader`)**:
    - LangChain `Document` 객체로 변환하여 메타데이터(TOC, Parent Info) 부착.
5.  **Storage**:
    - 처리된 데이터를 BigQuery(`namu_string_result_02`)에 적재.

---

## 🚀 Key Features: Hybrid Table Parsing Strategy

기존의 단순 정규식/HTML 파싱의 한계를 극복하기 위해, **Python 전처리와 LLM의 추론 능력을 결합한 하이브리드 전략**을 사용합니다.
(Prototype 검증 완료: `prototype_parser.py`)

### 1. 전처리 (Python Pre-processing)

HTML을 LLM에 보내기 전에 노이즈를 제거하고 구조를 단순화합니다.

- **Noise Removal**: 중복 이미지(`<noscript>`), 접힘 메뉴(`<dl>`) 제거.
- **Icon Textualization**: 국기/로고 등의 `<img>` 태그를 `(icon: alt_text)` 텍스트로 치환하여 문맥 보존.
- **Flattening**: `div`, `span` 등 스타일 태그를 제거하고 `table`, `tr`, `td` 등 핵심 구조만 유지.
- **Separator Handling**: 셀 내부의 `<br>`, `<hr>`을 `\n`, `|`로 변환하여 멀티라인 데이터 구조화.

### 2. 적응형 변환 (Adaptive RAG Prompting)

데이터의 성격에 따라 가장 적합한 Markdown 포맷을 선택하도록 LLM을 프롬프팅합니다.

| 패턴 유형       | 예시                 | 변환 전략                         | 포맷 (Markdown)                                |
| :-------------- | :------------------- | :-------------------------------- | :--------------------------------------------- | ---- | ---- | ---- | --- |
| **Entity Card** | 멤버 프로필          | 대상(Entity)별 속성 카드화        | `### 이름`<br>`- 생일: ...`<br>`- 포지션: ...` |
| **Key-Value**   | 인포박스, 요약표     | 계층형 리스트 (Hierarchical List) | `- **데뷔일**:`<br>`  - (icon: KR) 2016...`    |
| **Table**       | 음반 목록, 출연 영상 | 기존 테이블 유지                  | `                                              | 날짜 | 제목 | 링크 | `   |

> **Why?**
>
> - 복잡한 그리드(프로필)를 리스트로 풀면 "Entity-Attribute" 관계가 명확해져 RAG 검색 정확도가 향상됩니다.
> - 단순 데이터(음반)는 테이블 형식이 토큰 효율성이 높습니다.

---

## 📂 Project Structure

```
idol_info_finder/
├── namu_crawler.py       # 크롤링 및 파싱 핵심 로직 (Class: NamuCrawler)
├── namu_loader.py        # LangChain Document Loader (Class: NamuLoader)
├── idol_info_finder.ipynb # 메인 실행 노트북 (BigQuery 연동 및 파이프라인 실행)
├── get_namu_url.py       # Google Custom Search API를 이용한 URL 수집 도구
├── prototype_parser.py   # [New] 검증된 신규 파싱 로직 테스트 모듈
└── requirements.txt      # 의존성 라이브러리
```

## ✅ To-Do (Refactoring Plan)

- [x] **Parsing Strategy Verification**: 라이브 페이지 검증 및 프로토타입 작성 (`prototype_parser.py`)
- [ ] **Integration**: 프로토타입의 `clean_namu_html` 및 `get_markdown_prompt` 로직을 `namu_crawler.py`에 이식.
- [ ] **Unit Testing**: 다양한 아티스트 페이지에 대해 파싱 정확도 테스트.
- [ ] **Vector Indexing**: 처리된 Markdown 데이터를 BigQuery Vector Search에 인덱싱.
