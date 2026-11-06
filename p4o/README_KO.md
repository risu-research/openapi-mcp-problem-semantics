# RISU Probe P4-O — 관측된 스키마 변환의 의미 대응 검사

## 목표

기존 P4-N 외부 오픈소스 `patent-client-agents`의 원본 JPO VCR 응답을 실제 FastMCP stdio 도구 호출로 재생한 증거를 사용한다. P4-J까지의 단순 JSON 동일 경로 비교는 원본 `result`가 MCP `structuredContent.items` 또는 `not_found`로 옮겨갈 때 원시 `LOSS`를 보고한다. 이번 계층은 **관측 가능한 의미 대응에 관한 명시적인 검증 규칙**을 적용해 그 차이를 분류한다.

**매핑 규칙 일치는 원본 전체의 의미 보존 증명이 아니다.** 검증기는 전체 원본 필드 보존이나 매핑의 도메인 의미가 법적·업무적으로 올바르다고 증명하지 않는다. 제3자 독립 녹화가 아닌 우리의 VCR 재생이므로 P4-J의 확인된 인과적 손실 판정도 승격하지 않는다.

## 새 명령

```bash
risu-probe analyze ./captured-call/ --recovery \
  --semantic-map ./operator_mapping_for_that_call.json \
  --format json --out diagnosis.json

# 선언한 대응 규칙이 관측값과 모순될 때 종료코드 1
risu-probe analyze ./captured-call/ --recovery \
  --semantic-map ./operator_mapping_for_that_call.json \
  --fail-on-semantic-contradiction
```

매핑 파일은 반드시 캡처 디렉터리 **밖**에 둔다. 1~50개 case, case당 1~30개 규칙, 총 120개 이하의 규칙을 허용한다. JSON pointer는 한정된 RFC 6901 정적 경로만 지원한다. eval, Python 표현식, 자의적 함수, 동적 JSONPath, 네트워크 호출, SDK 또는 LLM 실행은 없다.

## 지원하는 보수적 두 종류의 규칙

- `equal_paths`: 원본 HTTP JSON 필드와 MCP의 **machine-readable `structuredContent`**에 나타난 필드의 실제 JSON 값을 정확하게 비교한다. 예시 `/result/data/designArticle` → `/items/0/design_article`. 불리언과 정수, 문자열과 수치는 혼동하지 않는다. MCP의 텍스트에 우연히 유사한 문자열이 있다는 이유만으로 통과시키지 않는다.
- `lookup_transition`: 명시된 원본 응답 코드와 실제 MCP 요청 인자, 원본 HTTP URL 끝의 신청번호, MCP `items`와 `not_found`, 구조화 결과, 오류 플래그를 함께 확인한다. `statusCode: "100"`과 1건의 조회 결과, `statusCode: "107"`과 원본 HTTP 200 및 정확한 `not_found: [신청번호]`가 각각 조건을 만족해야 통과한다. 이는 다른 API의 코드 107이 같은 뜻이라는 주장과 무관하다.

규칙 결과는 `OBSERVED_MATCH`, `CONTRADICTED`, `INSUFFICIENT`로 나뉜다. 조건에 맞는 모든 규칙이 성공하더라도 결과는 `ALL_DECLARED_CHECKS_MATCH`이며, `FULL_INFORMATION_PRESERVED` 같은 명칭을 사용하지 않는다. 검증하지 않은 원본 JSON 필드는 여전히 미확인이다.

**HTTP 자체가 오류(4xx/5xx)인데 MCP가 `isError: true`가 아닌 경우에는, 어떤 사용자 매핑 규칙으로도 해당 경보를 숨길 수 없다.**

## 외부 원본 P4-N 검증 대상

- **정상**: JPO HTTP 200, 내부 상태 `100`; MCP 실제 `tools/call`에서는 자료가 `structuredContent.items[0]`에 저장됐다. 선언한 7개 규칙으로 신청번호, 디자인 속성, 날짜, 등록번호, 첫 출원인 코드, 서지번호의 대응을 검증한다.
- **자료 없음**: JPO HTTP 200, 내부 상태 `107`; 실제 MCP 결과는 `isError: false`, `items: []`, `not_found: ["9999999999"]`. 선언한 1개 `lookup_transition`으로 관측 대응을 검증한다.

이 JPO 캡처들은 원본 제3자 VCR을 우리가 다시 실행한 것이며, 제3자가 처음부터 MCP wire까지 녹화한 완전한 독립 증거가 아니다. 두 호출에 대해 소스가 유래한 제3자 커밋은 `e7f0bcf2175823baaceb4844e84f9fc10ef00b40`으로 고정한다.

## 기존 판정과 공존

오래된 필드/JSON 경로 기반 `LOSS` 판정, 보수적 `REVIEW`, P4-J 인과관계 게이트의 `CONDITIONAL_MISMATCH`와 `CONFIRMED_LOSS` 수치는 그대로 유지한다. 새 진단은 별도 `semantic_mapping_v1` 필드로 표시한다. **매핑 계약은 사용자 선언이므로 독립 서명 증거로 승격시키지 않는다.**

SARIF에서 새로운 의미 규칙을 조용히 누락하는 일은 금지한다. `--semantic-map --format sarif`는 명확한 오류로 종료한다.

## 재현 방법

CI는 P4-N의 원본 JPO FastMCP 서브서버와 제3자 VCR 카세트를 고정 커밋으로 설치해 실제 MCP stdio JSON-RPC를 다시 기록한다. 기존 P4-J source pins를 검증한 뒤 P4-O 최소 패치를 적용해 **실제 설치된 v0.9.11 wheel**로 진단한다. 컴퓨터에서 확인하려면 CI에서 나온 P4-O 아티팩트와 전체 핸드오프 ZIP의 `verify_bundle.py`를 사용한다.

기존 P4-N 정상·자료 없음 결과의 구조화 응답과 보수적 판단을 변경하지 않는다. 독립된 불일치·거짓 주장·HTTP 오류 누락·타입 혼동 테스트를 통해 과장된 보존 주장을 차단한다.

## 출판 및 제품 배포

현재는 **experimental qualification branch**이다. 메인 브랜치나 기존 공개 제품을 바꾸지 않았다. 실제 제3자 독립 완전 HTTP→MCP 정상/오류 쌍의 확보량은 0이며 실환경 오탐률 FPR도 측정 불가다. P4-O는 선언한 경로 값과 상태 변환이 특정 관측에 들어맞는지 검증하는 기술적 단계다.
