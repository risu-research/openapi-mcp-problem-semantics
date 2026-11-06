# RISU Probe P4-S: 필드 중요도와 보존 의무의 근거 분리

2026-11-06 · v0.9.15 experimental · GitHub branch `qualification/p4s-field-importance-contract-obligation-20261106`

## 무엇이 바뀌었나

기존 P4-R은 원본 JPO API 응답에서 MCP 결과로 이동한 필드, 정규화된 필드, MCP 결과에 나타나지 않은 필드를 구별했다. P4-S는 여기에 **누구의 보존 요구인지**와 **요구를 뒷받침하는 기계 검증 가능 근거**를 구분하는 선택형 판정 계층을 추가한다.

- `RECORDED_MCP_OUTPUT_SCHEMA`: 같은 실행의 실제 `tools/list` JSON-RPC 응답에 포함된 해당 도구의 `outputSchema.required`를 직접 검사한다. 단순 `properties` 등장이나 도구 설명 문장만으로 필수 의무를 선언하지 않는다. 타입도 검사한다. 이 증거는 **서버가 광고한 스키마**이지 서명된 독립 계약서나 법적 보존 의무의 입증은 아니다.
- `OPERATOR_POLICY`: 사용자가 캡처 폴더 **밖에서 명시적으로 선택한** 정책으로 요구사항과 중요도, 적용 조건을 정한다. 기존 P4-R 실제 비노출 결과가 있을 때만 미충족으로 판정한다. 이는 사용자 내부의 CI 승인 기준이다. 공급자와의 계약이나 외부 개발자의 결함이 자동으로 증명되는 것은 아니다.

중요도 `CRITICAL/HIGH/MEDIUM/LOW`는 반드시 구체적인 이유를 입력해야 하지만 **운영자의 평가**다. 검증기는 중요도의 객관성을 임의로 인증하지 않고 그 출처와 입력 정책의 해시를 남긴다.

## 제3자 원본 기반 측정

출처: `parkerhancock/patent-client-agents` 고정 커밋 `e7f0bcf2175823baaceb4844e84f9fc10ef00b40`, 실제 제3자 VCR 카세트의 HTTP 200 정상 응답을 해당 프로젝트 원본 FastMCP 서버에서 **RISU가 다시 재생**해 관측한 JSON-RPC 스키마와 응답이다. 새로 기록한 MCP wire는 제3자가 독립적으로 당시 보존한 wire가 아니다.

| 원본 또는 대상 | 실제 증거 | 판정 |
|---|---|---|
| MCP `/summary` | `tools/list` 출력 스키마의 `required` | 요구 충족 |
| MCP `/items` | 동일 | 요구 충족 |
| MCP `/provenance` | 동일 | 요구 충족 |
| 원본 `/result/remainAccessCount` | HTTP 값 `799`; 구조화 MCP·텍스트 carrier에서 비노출 | **운영자가 '매번 노출'을 요구한 기준 미충족** |
| 원본 `/result/errorMessage` | 원본 값은 빈 문자열; 운영자는 비어 있지 않을 때만 노출 요구 | **이번 사례에 정책 조건 비적용** |
| 공급자의 quota 출력 필수 주장 | MCP `outputSchema.required`에는 `remain_access_count` 없음 | **관측된 서버 스키마로 뒷받침되지 않음** |
| MCP `/not_found`의 필수 주장 | `properties`에는 있지만 `required`에는 없음 | **필수 주장 뒷받침되지 않음** |

정확한 집계: 서버가 광고한 필수 필드 **3/3 충족**, 운영자 의무 **1건 미충족**, 비어 있지 않은 오류문구에 대한 조건부 의무 **1건 비적용**, 필수라고 주장했지만 스키마가 뒷받침하지 않는 항목 **2건**.

제3자 원본 `ApiResult` 모델에는 `error_message`와 `remain_access_count`가 정의되어 있지만, JPO 디자인 조회 클라이언트는 `DesignProgressData.model_validate(result.data)`로 **원본 envelope 바깥의 데이터 부분을 모델로 변환**한다. MCP 도구가 `dump(result)`와 `FetchedList`를 반환하는 경로도 원본 코드에 있다. 이 점은 실제 비노출의 코드 경로와 일치하지만 해당 envelope 필드의 MCP 보존 의무를 자동으로 만들지는 않는다.

기존 원본 필드 판정 **132/134 (98.51%)** 유지. 원시 `LOSS`, 보수적 `REVIEW`, 인과관계 `CONDITIONAL_MISMATCH`, `CONFIRMED_LOSS=0` 모두 변화 없음. 외부 실환경 오탐률은 계산할 독립 정답 자료가 없어 정의되지 않는다.

## 사용법

```bash
risu-probe analyze ./capture-folder \
  --semantic-map ./semantic-map.json \
  --field-coverage --array-map ./array-map.json \
  --residual-map ./residual-map.json \
  --obligation-map ./obligation-policy.json \
  --format json
```

선택형 CI 실패 기준:

- `--fail-on-operator-duty`: 운영자 요구에 대한 관측된 미충족만 차단한다. JPO 정상 사례 **종료 코드 1**.
- `--fail-on-schema-duty`: 실제 서버가 광고한 **필수** 출력 필드가 없거나 타입이 틀렸을 때만 차단한다. JPO 정상 사례 **종료 코드 0**.
- `--fail-on-unsupported-schema-claim`: 출력 스키마를 근거로 필수라고 주장했지만 `required`가 이를 뒷받침하지 않으면 차단한다. 제공된 샘플에서는 **종료 코드 1**.

정책 입력은 `risu-explicit-field-obligation-policy-v1`, 결과는 `field_obligations_v1`. 정책은 캡처 밖 일반 파일이어야 하며 중복 경로·규칙·출처 혼동·잘못된 필수 주장에 대해 보수적으로 처리한다. 현재 SARIF 출력은 이 계층을 지원하지 않는다.

## 검증 수준

GitHub CI는 제3자 저장소의 원본 커밋과 핵심 소스 파일 3개의 Git blob SHA를 확인하고 원본 카세트를 격리 환경에서 오프라인으로 재생했다. 신규 단위 및 실제 wheel CLI 시험 **40/40**, 독립 허위 주장 반례 **11/11**, 기존 P4-J~R 검증 통과. 원본 외부 개발자 코드를 수정하지 않았고 JPO 자격증명이나 live 호출을 사용하지 않았다.

중요한 제한: 보고서는 서버가 광고한 필수 스키마의 **관측된 자기선언**과 운영자 정책만 평가한다. 법률상 계약 위반, 독립 관측에 의한 실제 HTTP→MCP 인과관계, 모든 원본 필드의 의미 보존, 외부 사용자의 실제 오탐률은 이 보고서의 범위 밖이다.

## 재현

1. `python verify_bundle.py`로 모든 파일 해시·독립 감사 영수증·wheel 소스 동일성을 점검한다.
2. `python verify_bundle.py --full`로 새 가상환경에 wheel 설치, 32개 단위 테스트, 8개 설치형 CLI 테스트를 재실행한다. 오프라인 fixture는 **제3자 원본 HTTP와 동일한 구조로 재구성한 합성 자료**이고 MCP wire는 GitHub CI가 생성한 실제 재생 기록임을 표시한다.
3. 제3자의 고정 커밋을 새로 내려받아 **원본 HTTP를 다시 재생하는 전체 CI 재현**은 GitHub Actions가 수행한다. 원본 VCR 본문은 이 패키지에 임의로 복제하지 않았으며, 현재 아티팩트는 독립 원본 wire가 아니다.