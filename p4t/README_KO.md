# RISU Probe P4-T — 버전별 MCP 출력 계약·운영자 의무 변경 추적

**상태: 로컬 단위 테스트 60/60 및 P4-T 실제 GitHub Actions 통합 검증 통과.** 기존 P4-S v0.9.15를 덮어쓰지 않고, 선택 명령 `risu-probe contract-history`를 추가할 수 있는 패치다. P4-S에서 관측한 `tools/list`의 출력 스키마를 실제 기준점으로 사용할 수 있다. 포함된 두 번째 스키마와 운영자 정책은 **명시적인 가상 업그레이드 시나리오**이며, 제3자 개발자가 실제 배포한 변경이 아니다.

## 사용법

기존 P4-S 제품 빌드 후 `python p4t/apply_upgrade.py`로 통합하고 wheel을 다시 만든다. 단독 사용은 `python p4t/risu_contract_history.py` 또는 `PYTHONPATH=p4t python -m risu_contract_history`.

```bash
risu-probe contract-history snapshot --schema p4n/results/normal/observed_stdio_wire.jsonl \
  --tool get_jpo_progress --policy p4s/fixtures/jpo_obligation_policy.json \
  --version observed-p4s --out p4t/results/observed.json
python p4t/upgrade_scenario.py --observed p4t/results/observed.json \
  --schema-out p4t/results/hypothetical_schema.json \
  --policy-out p4t/results/hypothetical_policy.json
risu-probe contract-history snapshot --schema p4t/results/hypothetical_schema.json \
  --tool get_jpo_progress --policy p4t/results/hypothetical_policy.json \
  --version hypothetical-v2 --previous p4t/results/observed.json \
  --out p4t/results/hypothetical.json
risu-probe contract-history diff p4t/results/observed.json p4t/results/hypothetical.json \
  --out p4t/results/diff.json --fail-on-potential-breaking
risu-probe contract-history timeline p4t/results/observed.json p4t/results/hypothetical.json
```

`--fail-on-potential-breaking`는 위험한 **선언 변경 가능성**에 종료 코드 `1`을 반환하며, 통상 검사 `0`, 잘못된 입력 및 증거 검증 실패 `2`다. `snapshot`은 덮어쓰기를 거부한다. SHA-256 링크는 기록 간 무결성을 확인할 뿐, 배포 순서·독립 관측·서명자 신원까지 보증하지는 않는다.

## 검증 내용과 범위

- MCP `outputSchema.required`가 추가·삭제되거나 선택→필수·필수→선택으로 바뀌는 경우를 분리한다.
- `type`이 바뀌거나 필드 자체가 삭제된 경우를 구분한다.
- 상위 필수 여부 변화가 4개 하위 필드에 미친 영향은 **파급효과**로 별도 집계해 직접 변경 4건을 부풀리지 않는다.
- 운영자 정책의 규칙 추가·삭제·속성 변경을 독립 집계한다. 정책이 바뀌었다고 공급자 계약 위반이라고 주장하지 않는다.
- 새 스냅샷은 이전 스냅샷의 SHA-256을 연결하며 `timeline`은 해시 연결과 변조를 확인한다.
- `oneOf`, `$ref`, `items` 하위 스키마의 의미 변화, 실제 HTTP→MCP 인과관계, 실제 소비자의 호환성 오류, 법적 계약 위반은 별도 실증이 필요하다. JSON Schema 전체 의미를 계산하는 범용 판정기가 아니다.

## 현재 결과

단독 60개 `unittest`가 통과했다. 합성 예시의 정확한 변화는 스키마 직접 변경 **4**, 파급효과 **4**, 운영자 정책 이벤트 **6**, 잠재 breaking 변경 **3**. 기존 P4-S 원본의 132/134 커버리지나 CONFIRMED_LOSS=0 등의 결과를 변경하려는 패치는 포함하지 않았다.

P4-T 통합 CI 실행 **#42300393742**에서 제3자 고정 HTTP 기록을 원본 MCP 서버로 실제 재생하고, P4-S 원본 `tools/list` 스키마를 다시 수집했다. 해당 실제 기준점에서 가상 업그레이드를 생성하여 4/4/6/3 결과를 강제 검증했고, P4-T 단위 테스트 60개, 이전 단계 전체, SHA-256 변조 반례까지 통과했다. [재현 CI](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42300393742). 이 성공은 고정된 재생 환경과 가상 변경 시나리오에 한정된다.

## 정밀 재감사 보강

GitHub 최초 CI에서 P4-S의 실물 운영자 정책이 `cases[].obligations[]`를 사용한다는 점을 확인했다. 이 형식을 직접 해석하도록 개선하고, 알 수 없는 정책 형식을 빈 규칙 집합처럼 무시하지 않도록 실패 처리한다.

`python p4t/upgrade_scenario.py --observed p4t/results/observed_snapshot.json --schema-out p4t/results/derived_upgrade_schema.json --policy-out p4t/results/derived_upgrade_policy.json`는 **동일한 실제 MCP 스키마를 복제한 뒤 제한된 가상 변경만 적용**한다. 이 실험에서 스키마 직접 변경 4, 상위 필수 조건의 하위 파급효과 4, 운영자 의무 변경 6, 잠재적 breaking 3으로 집계한다. 정책 6건에는 두 건의 새로운 가상 요구, 한 건의 삭제, 오류 요구 조건과 중요도·이유의 변경 3건이 들어간다. 모두 실제 배포 사실이 아니다.
