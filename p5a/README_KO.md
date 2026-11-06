# RISU Probe P5-A — 판정 정확성 및 설치형 제품 통합

- **목적:** P4-V `$ref`/`anyOf` 중첩 구조 분석을 P4-T 이후의 실제 제품 CLI에 통합하고, 새로운 선택 출력 필드가 구 소비자의 닫힌 객체 검증을 깨는 반례를 탐지한다.
- **기존 제품 유지:** `risu-probe --version`, 기존 analyze/정적 검사 및 `contract-history`는 그대로 통과한다. `risu_analyze.py`, `risu_causality.py`, P4-S 의무 판정, P4-T 이력 판정 소스는 **byte-identical**로 유지한다.
- **신규 명령:** `risu-probe schema-compat --old OLD_TOOLS_LIST.json --new NEW_TOOLS_LIST.json --tool convert_time [--fail-on-possible-break]`. `--old`와 `--new`는 원본 JSON-RPC 메시지 혹은 독립 스키마, hash-verified P4-T 스냅샷도 받는다.
- **중요한 구분:** 선택 필드 추가는 *새로운 필수 출력 의무*를 만들지 않지만, **구 소비자가 `additionalProperties: false`로 닫힌 객체를 검증하면** 새 필드가 거부될 수 있다. 이는 실제 소비자 장애의 증거가 아니라 구 JSON Schema 검증의 잠재적 호환성 반례다.
- **검증 판정:** `POTENTIAL_VALIDATOR_BREAK` 또는 `REVIEW_REQUIRED`일 때 선택적인 `--fail-on-possible-break`는 exit 1; 파싱·지원되지 않는 스키마 또는 무효 원본은 exit 2; 정상 분석은 exit 0. 이 규칙으로 기존 소비자 코드를 무단 실행하지 않는다.
- **제한:** 복잡한 `allOf`, 순환 참조, 외부 `$ref`, 모호한 분기 매핑 등은 fail-closed. 실제 생산 환경의 장애·계약 위반은 추론하지 않는다. 스키마 수준 판정 통과는 범용 호환성을 보장하지 않는다.
- **재현:** 새 wheel에서 `risu-probe schema-compat ...`를 실행하고, 동일한 wheel의 모듈로 adversarial 테스트와 실제 두 MCP 공개 릴리스 기록을 실행한다. 기존 P4-T 재현 워크플로 뒤에 P5-A 패치를 추가한다.
