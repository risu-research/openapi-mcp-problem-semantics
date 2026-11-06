# RISU Probe P4-M — 제3자 원본 실행 산출물 확보

## 이번 단계에서 실제로 확보한 원본
1. **parkerhancock/patent-client-agents**, 고정 커밋 `e7f0bcf...`: 일본 특허청 JPO의 원본 HTTP 요청과 응답을 보존한 VCR 카세트 2개 및 당시 테스트·MCP 도구 소스 3개. 원본 Git blob SHA까지 CI에서 인증했다.
   - `TestMcpDispatchLive.test_progress_design`: 외부 개발자의 MCP 도구 **Python 디스패처 함수 테스트**가 발생시킨 실제 upstream API 카세트. HTTP 200, API 내부 statusCode 100. 원본 소스의 `get_jpo_progress(DESIGN_APP, ip_type="design")`와 대응한다.
   - `TestPatentProgressLive.test_get_patent_progress_not_found`: 외부 개발자가 직접 JPO 클라이언트로 호출하여 기록한 자료 없음 응답. HTTP 200, API 내부 statusCode 107, 비어 있는 data. **MCP 오류·HTTP 404가 아니다.**
   - 두 VCR에 OAuth 로그인 등 인증 헤더가 포함되지만 민감 필드는 외부 프로젝트에서 수정·가림 처리되었다. 이 마스터에는 원본 응답 본문을 재배포하지 않고 Git 커밋과 해시를 담았다.

2. **KryptosAI/mcp-observatory**: 실제 GitHub Actions [run 42245080723](https://github.com/KryptosAI/mcp-observatory/actions/runs/42245080723)의 자체 아티팩트 `real-server-matrix-artifacts`(artifact ID `13517149890`). GitHub 연결을 통해 원본 ZIP을 다운로드했다. 받은 ZIP SHA-256: `4e65a36b6fafcec504d116c6bab3b8b0b298b83c3f37be6560d1e6550cd380d2`. 8개 JSON 실행 결과와 8개 Markdown 보고서를 포함한다. MCP 도구 목록과 일부 적합성 검사 기록은 있지만 **JPO 호출과 관계없고 upstream REST API→MCP의 원본 쌍이 아니다.** GitHub가 보고한 archive digest는 다운로드된 ZIP의 바이트 해시와 다를 수 있으므로, 재검증에는 실제 수령한 ZIP 바이트 해시를 사용한다.

## 독립 검증 수치
- 출처가 고정된 제3자 원본: **5개 파일의 Git blob 인증 PASS** (HTTP VCR 2 + 원본 소스 3).
- 외부 원본 HTTP 정상 응답: **1건**.
- 외부 원본 HTTP API 수준 자료 없음: **1건**. HTTP 자체는 200.
- 외부 **MCP 디스패처 함수** 호출로부터 upstream HTTP 카세트가 생성된 정상 사례: **1건**.
- 실제 네트워크를 통한 MCP JSON-RPC `tools/call` 최종 원본까지 **같은 실행에 보존된 완전한 정상 쌍: 0건**.
- 동일한 조건의 완전한 오류 쌍: **0건**.
- 독립적으로 검증된 FPR: **정의 불가**.
- 거짓 증거 주장 9건에 대한 독립 감사: **9/9 차단**.

## 실행
```bash
python -m pip install 'PyYAML==6.0.2'
python p4m/qualify_originals.py --fetch
python p4m/qualify_originals.py --inspect
python p4m/independent_audit.py
```
외부의 소스·프로그램은 실행하지 않는다. 네트워크는 불변 커밋으로 고정된 공개 파일을 수집할 때만 사용한다. 원본 HTTP body, 인증 정보, 개인 정보는 결과 아티팩트에 포함하지 않는다.

## 확보 경로의 실질적 결론
이제 원본 **upstream HTTP 성공** 및 **API 수준 실패** 응답이 있다. 특히 정상 케이스는 외부 MCP 디스패처 함수와 코드 차원에서 연결되어 있다. 다음으로 필요한 것은 같은 호출의 **외부 개발자가 남긴 실제 MCP JSON-RPC 요청·응답 원본**이다. 단순 테스트 결과, 다른 CI 아티팩트, 자체 키로 서명한 기록은 이를 대신할 수 없다.

추가 확보 후보는 이 저장소의 기존 MCP 공개 실행 CI가 **`tools/call` 결과 원본을 첨부하는지**와, 원본 upstream 네트워크 카세트를 가지는 외부 변환 프로젝트의 아티팩트를 계속 검증하는 것이다. 이 경계를 넘지 못하면 `CONFIRMED_LOSS`로 승격하지 않는다. P4-J 제품 소스는 변경하지 않았다.
