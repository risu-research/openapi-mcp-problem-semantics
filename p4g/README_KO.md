# RISU Probe P4-G — One-Command Recovery Lens (실험용 v0.9.8)

## 바로 실행

Python 3.11 이상. 이 압축파일에 포함된 wheel을 별도 가상환경에 설치하면 실제 `risu-probe` 명령을 사용할 수 있다.

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --no-index --no-deps dist/risu_probe_preview-0.9.8.dev0-py3-none-any.whl
risu-probe analyze evidence/saved_p4de.json --recovery
```

**이제 하나의 실행 명령(`risu-probe analyze ... --recovery`)이 기존 분석 + 구조화/텍스트 복원 판정을 모두 수행한다.** 설치는 최초 한 번 필요하다. JSON 파일 저장은 다음과 같이 옵션을 추가한다.

```bash
risu-probe analyze evidence/saved_p4de.json --recovery --format json --out diagnosis.json
```

### 입력 형식

기존 `risu-probe analyze`의 **이미 수집된 HTTP/MCP matrix** JSON을 그대로 받는다. 최상위 키가 `cases`이고 각 항목에 `id`, `translator`, `source: {status,content_type,body}`, `mcp: {isError,structuredContent,content}`, 선택적으로 `observed_consumer: {consumer: ...}`가 있을 수 있다. `targets`/`checks` 형식도 지원한다. 외부 MCP/변환기/소비자 코드를 자동 설치·실행하거나 임의 API를 네트워크로 요청하지 않는다. 따라서 관측 파일을 준비하지 않은 프로젝트에서는 사전에 응답 수집이 필요하다. **'한 명령'은 이미 수집된 증거에 대한 진단 흐름을 뜻한다.**

P4-D·P4-E 재현 입력은 `evidence/saved_p4de.json`. 실험에서 사용한 LangChain과 PydanticAI 소비자 결과가 여기에 저장되어 있다. 임의 입력에 동일한 결함이 존재한다고 단정하지 않는다.

## 주요 판정 결과

| 사례 | v0.9.8 기존 판정 | 오류 표시 | MCP 본문 | 최종 소비자 |
|---|---|---|---|---|
| Meilisearch→CNOE→LangChain 200 | PRESERVED | MATCH | EXACT_MACHINE | EXACT_MACHINE |
| 동일 조합 404 | LOSS | ERROR_FLAG_LOST | NO_EXACT_OBJECT_CARRIER | 원본 `code/type/link` ABSENT_IN_OBSERVED_CARRIERS |
| DeepL→FastMCP→PydanticAI 200 | PRESERVED | MATCH | EXACT_MACHINE | EXACT_MACHINE |
| 동일 조합 456 | LOSS | MATCH | EXACT_JSON_TEXT | 오류 `code/message` PARSED_JSON_TEXT_FIELD |
| 동일 조합 429 | LOSS | MATCH | NO_EXACT_OBJECT_CARRIER | 오류 `code/message` ABSENT_IN_OBSERVED_CARRIERS |

**출력 필드 의미:**

- `TYPED_FIELD`: 원본 키와 타입과 값이 구조화된 전달 영역에 일치.
- `PARSED_JSON_TEXT_FIELD`: 허용된 전체 JSON 또는 HTTP 상태가 일치하는 특정 오류 접두어 뒤의 완전한 JSON을 엄격 파싱하여 원본 필드와 일치. 불특정 문자열 JSON 조각은 인증하지 않는다.
- `TEXT_VALUE_MENTION_ONLY`: 텍스트에 값이 일부 언급되어도 키·타입·값의 구조화 계약은 인증 불가.
- `ABSENT_IN_OBSERVED_CARRIERS`: 이번에 저장된 MCP/소비자 전달 영역에서는 찾을 수 없음. 서버 내부나 다른 실행에서도 없다는 주장 아님.
- `EXACT_MACHINE`, `EXACT_JSON_TEXT`, `NO_EXACT_OBJECT_CARRIER`: 전체 JSON 객체 단위의 보존 상황.
- `UNTESTED`: 외부 소비자 결과가 입력에 없을 때.

`--recovery`는 기본 출력과 진단 결정을 **변경하지 않는다**. 원래의 `--fail-on-loss`, calibrated `PASS/REVIEW/FAIL`은 그대로 유지한다. `--recovery` 없이 호출할 때 구 버전과 결과 구조가 동일하고 버전 문자열만 0.9.8로 바뀐다. `text`, `markdown`, `json`에서 복원 진단 표시를 지원한다. SARIF 복원 확장은 아직 없으므로 `--recovery --format sarif`는 명확히 오류를 낸다(조용히 누락하지 않음).

## 신뢰·범위

- 원본 v0.9.7 wheel은 **무수정**. 새 v0.9.8 wheel에서는 기존 모듈 20개를 원본 바이트 그대로 복사하고, 진입 모듈의 버전, `risu_analyze` 명령 처리부, `risu_recovery` 새 모듈만 변경했다. `build_wheel_offline.py`가 모든 바이트를 대조한다.
- P4-D 404의 원본 HTTP 본문은 당시 전체 바이트를 저장하지 않아 **공개 API 예시와 원래 로컬 응답 재현 코드로 재구성**한 값이다. MCP와 LangChain 결과는 당시 저장된 실행 값.
- P4-E는 DeepL 원본 공개 OpenAPI와 실제 로컬 HTTP 본문, FastMCP stdio MCP, PydanticAI 결과를 고정한 이전 실행 증거를 사용한다. API 오류의 구체적 `code` 값은 합성 실험값으로 DeepL 운영 사례로 일반화할 수 없다.
- 출력에는 원본 오류 메시지나 코드 값이 복사되지 않고 필드 경로와 확인된 상태만 노출된다. 민감한 형태의 필드명은 해시한다. 저장된 관측 원본 파일에는 원본 값이 담길 수 있으므로 **자체 관리**가 필요하다.
- 저장된 증거를 분석하는 툴이고 실제 서버 연결, 계정, LLM, 타인 코드 실행 없음. 임의의 MCP 버전 간 완전한 호환성 검증이라고 주장하지 않는다.

## 검증 재실행

```bash
python verify_all.py
```

위 명령은 네트워크 없이 원본 wheel 일치·새 wheel 소스 일치·새 통합 CLI 23개 테스트·원본 0.9.7 84개 회귀 테스트·최종 설치형 명령 결과를 다시 검사한다. `python build_wheel_offline.py`는 인터넷 의존성 없이 순수 Python wheel을 다시 생성한다.

### 이전 실제 외부 연결 CI

- P4-D: https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42164496830
- P4-E: https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42167138991
- 원본 v0.9.7: https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42153289863

**출판 상태:** 이 ZIP과 설치 테스트가 검증 대상이다. 독립 GitHub P4-G CI가 완료되었다는 주장은 하지 않는다. 메인 브랜치/기존 배포물을 교체하지 않았다. 다음 단계는 제3의 독립적인 캡처 자료로 같은 CLI의 입력 형식과 결과를 검증하고, CI 승인을 받은 후 저장소 반영을 고려한다.