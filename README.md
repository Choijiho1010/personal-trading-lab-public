# Personal Trading Lab

국내주식의 주문·체결을 기록하고, 거래 이력과 출처·시점이 있는 근거를 질의하는 앱을 목표로 한다. 주문과 체결의 기준은 증권사와 거래 원장이다. 온톨로지·GraphRAG와 Codex는 거래 이력과 관련 근거를 연결하는 조회 경로로 설계한다.

첫 데모는 React 화면, Spring Boot 거래 서비스, Python 질의 서비스를 연결해 합성 체결 1건을 조회하고 답변의 근거를 확인한다. 원장·그래프 DB와 증권사 연결은 후속 단계에 둔다. 미래에셋 실주문 API 확인 현황은 [결정 기록](docs/ADR.md), 작업 순서와 인수 조건은 [단계 파일](phases/index.json)에 있다.

## 로컬에서 첫 데모 실행

Java 21, Node 22.12 이상(22.x), Python 3.9 이상을 준비한다. 저장소 루트에서 실행한다.

```sh
npm ci --prefix apps/web
(cd services/trading && ./gradlew --no-daemon bootJar)
python3 scripts/run_first_demo.py
```

[http://127.0.0.1:5173/](http://127.0.0.1:5173/)에서 합성 체결을 확인한다. “이 거래에서 몇 주 샀어?”를 제출하고 근거 보기로 원래 체결 행을 확인한다. 다른 터미널에서 `python3 scripts/verify_first_demo.py`로 HTTP 경로를 재현할 수 있다.

시간 초과를 재현하려면 실행기를 종료한 뒤 `RESEARCH_SYNTHETIC_DELAY_MS=1500 python3 scripts/run_first_demo.py`로 다시 실행한다. 같은 화면에서 질문하면 오류가 표시되고 체결과 질문이 유지된다. HTTP 검사는 `python3 scripts/verify_first_demo.py --expect-timeout`으로 반복한다. 합성 데모와 인수 범위는 [첫 데모 구현 명세](FIRST_DEMO.md)에 있다.

## 로컬 Codex 하네스

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

개발 검사와 Hook 설치는 [개발 품질 관리](docs/development-quality.md)를 따른다. 기본 테스트는 합성 서비스와 가짜 Codex 프로세스로 입력 경계와 실패 처리를 검증한다. 실제 모델의 답변 품질·프롬프트 주입 방어·전체 런타임 격리와 실계좌 안전성은 별도 검증 항목이다.

[문서 목차](docs/MOC.md)에서 관련 문서를 볼 수 있다.
