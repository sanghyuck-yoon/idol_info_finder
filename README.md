# idol_info_finder

할 일 

[ ] 데이터 로드
    `wev-dev-analytics.namu_wiki.artists`에 저장한 데이터를 로드
    page_content, abs_page_toc_item, toc_item, artist_info은 필수로 포함
[ ] 텍스트 분할
    page_content를 적절히 나누고(휴리스틱), abs_page_toc_item + toc_item + artist_info를 넣어준다. 메타데이터 + 본문 최상단에
[ ] 인덱싱
    벡터DB에 저장 -> 여기서는 빅쿼리 > 버텍스 AI 강제(?) ㄴㄴ BigQueryVectorStore 
    다른 저장소를 사용할 수 있을지도 검토 필요
[ ] 검색
    리트리버 최적화(휴리스틱?)
[ ] 생성
    질문 입력 후 답변 생성 에어전트 개발