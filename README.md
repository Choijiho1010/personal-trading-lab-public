# Personal Trading Lab

국내주식의 주문·체결을 기록하고, 거래 이력과 출처·시점이 있는 근거를 질의하는 앱을 목표로 한다. 주문과 체결의 기준은 증권사와 거래 원장이다. 온톨로지·GraphRAG와 Codex는 거래 이력과 관련 근거를 연결하는 조회 경로로 설계한다.

현재 구현은 합성 자료를 사용하는 Codex 실행 하네스와 개발 검사다. FastAPI 앱, 원장·그래프 저장소, 증권사 어댑터는 후속 단계다. 미래에셋 실주문 API 확인 현황은 [결정 기록](docs/ADR.md), 작업 순서와 인수 조건은 [단계 파일](phases/index.json)에 있다.

```sh
python3 scripts/validate.py
codex login status
python3 scripts/ask.py
```

`ask.py`는 합성 자료로 로컬 Codex CLI를 호출한다. ChatGPT 로그인만 허용하고 임시 작업 디렉터리에서 읽기 전용으로 실행한다. JSONL의 성공 이벤트와 별도 최종 파일을 함께 확인한 뒤 근거 ID가 입력에 있는 답변만 출력한다. Codex 연결은 ChatGPT 서비스로 요청을 보낸다. 실데이터 연결 시에는 어떤 필드가 보내지는지 별도로 검증한다.

OpenAI 공식 문서는 다음 세 곳을 참조한다.

- [AGENTS.md 탐색과 우선순위](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [비대화형 실행, JSONL, 출력 스키마, 인증 재사용](https://learn.chatgpt.com/docs/non-interactive-mode)
- [ChatGPT 로그인과 API 키 인증](https://learn.chatgpt.com/docs/auth?surface=app)

개발 검사와 Hook 설치는 [개발 품질 관리](docs/development-quality.md)를 따른다. 기본 테스트는 가짜 프로세스로 입력 경계와 실패 처리를 검증한다. 실제 모델의 답변 품질·프롬프트 주입 방어·전체 런타임 격리와 실계좌 안전성은 이 테스트만으로 입증되지 않는다.
