# K-V3 잔여 항목 분석 및 대책안

> **발행일**: 2026-04-14  
> **기준 문서**: `k_v3_integrated_inspection_report.md` (검수본, 48915d2)  
> **현재 상태**: STANDBY | P3 NON-INTERFERENCE = TRUE  
> **문서 성격**: 잔여 장부 (residual ledger) — 미완성 16 + 이슈 14 + 부족점 10 = 총 40항목

---

# A. 미완성 16항목 — 이유·근거·대책

---

## A-01. P3 관측 윈도우 완료

**상태**: PENDING  
**이유**: P3 윈도우는 2026-04-14 시작, ~04-28 종료 예정. 최소 336 bars(1H × 14D)와 10 novelty events 필요. 시간이 물리적으로 아직 경과하지 않았음.  
**근거**: VAL-PDC-002 criteria #1 MIN_BARS ≥ 336. 통계적 유효성을 위한 최소 관측량.  
**현시점 대책**:
- 대기 (시간 경과 필수, 가속 불가)
- ops_state.json의 P3 observation 카운터 정합성 주기 확인
- Celery beat scheduler가 데이터 수집을 정상 수행 중인지 모니터링

---

## A-02. VAL-PDC-002 실행

**상태**: PENDING  
**이유**: P3 윈도우 종료 전에는 실행 불가. 관측 데이터가 불완전한 상태에서 판정하면 통계적 왜곡 발생.  
**근거**: REEVAL-PLAN-D001 §1 "evaluation_basis_window 종료 후 실행". FT-06 P3 윈도우 수동 단축 금지.  
**현시점 대책**:
- VAL-PDC-002 7개 criteria 실행 스크립트/절차 사전 점검 (dry-run 준비)
- `app/services/ppf_val_pdc_002.py` 코드 정합성 사전 확인 (읽기 전용)
- 판정 template receipt 양식 사전 준비

---

## A-03. POST-P3 재평가 판정 (HOLD/PASS/BLOCK)

**상태**: PENDING  
**이유**: VAL-PDC-002 결과에 의존하는 파생 판정. 입력 없이 출력 불가.  
**근거**: REEVAL-PLAN-D001 §5 Hold/Pass/Block 기준. 판정은 7 criteria 전부 통과 여부로 결정.  
**현시점 대책**:
- 3가지 시나리오별 대응 계획 사전 수립:
  - **PASS + GREEN**: Paper 진입 조건 8-conjunction 즉시 점검
  - **HOLD (YELLOW)**: 추가 관측 윈도우 설계 준비
  - **BLOCK (RED)**: 원인 분석 체크리스트 + CR 발행 절차 확인
- 판정 결과와 무관하게 production_authorized = FALSE 유지 재확인

---

## A-04. Paper Trading 진입

**상태**: PENDING  
**이유**: FZ-07에 의해 `state == VAL_PDC_002_ISSUED AND tier == GREEN`일 때만 진입 가능. 현재 두 조건 모두 미충족.  
**근거**: `check_paper_entry(tier)` → HARD_BLOCK when conditions unmet.  
**현시점 대책**:
- Paper trading 인프라 사전 점검 (paper_trading_bridge.py, paper_session model 정합성)
- SOL/USDT paper rollout plan (cr046_sol_paper_rollout_plan.md) 재검토
- 진입 시 필요한 ops_state.json 변경 사항 사전 설계 (실행은 판정 후)

---

## A-05. Shadow → Paper 전환

**상태**: PENDING  
**이유**: 8-conjunction promotion prerequisites 미충족. P3 PASS가 선결 조건.  
**근거**: Promotion Prerequisites: VAL-PDC-002 GO + GREEN tier + advisory OPEN=0 + hard blockers RESOLVED + deployment readiness + governance alignment + human CR + seal integrity.  
**현시점 대책**:
- 8-conjunction 중 현재 충족 가능한 항목 사전 체크:
  - advisory OPEN=0 → **충족** (7/7 closed)
  - hard blockers RESOLVED → **충족** (A1, A7 resolved)
  - deployment readiness → **충족** (CONDITIONALLY_PREPARED)
  - seal integrity → **충족** (48915d2 baseline intact)
  - 미충족: VAL-PDC-002 GO, GREEN tier, governance alignment (P3 결과 의존), human CR
- 충족/미충족 매트릭스 유지

---

## A-06. Production Authorization

**상태**: PERMANENTLY_FALSE  
**이유**: 의도적 설계. `production_authorized = FALSE`가 코드 내 하드코딩. FZ-04: `check_live_authorized()` always returns False. 이는 버그가 아니라 안전 설계.  
**근거**: FZ-04, FZ-05, FT-02. 어떤 자동 판정도 이 값을 변경할 수 없음.  
**현시점 대책**:
- **미완성이 아니라 의도적 설계로 재분류 권고**
- 향후 production 전환 시 별도 human CR + 코드 변경(별도 branch) + 다중 승인 절차 사전 설계
- 현재는 변경 시도 자체가 금지

---

## A-07. Live Entry

**상태**: PERMANENTLY_BLOCKED  
**이유**: FZ-03: `check_live_entry()` always returns HARD_BLOCK. 조건부 분기 자체가 없음. Shadow → Paper → Live 전체 체인에서 Live는 최종 단계.  
**근거**: Live entry는 모든 사전 단계(Shadow PASS, Paper PASS, Promotion PASS, Human Authorization) 완료 후에만 가능하도록 설계.  
**현시점 대책**:
- **A-06과 동일: 의도적 설계로 재분류 권고**
- Live entry 해제를 위한 사전 조건 목록 정리 (미래 reference용):
  1. Paper trading PASS 판정
  2. 별도 Live Authorization CR 발행
  3. `check_live_entry()` 코드 변경 (별도 branch)
  4. 다중 승인 + CI PASS + squash merge
- 현재는 논의 자체 불필요

---

## A-08. Track B (SMC_MACD_1H ETH) 검증

**상태**: NOT_STARTED  
**이유**: Track B는 EXPERIMENTAL 트랙. SMC_MACD_1H 전략의 ETH/USDT 적용은 CR-046 Phase 5a에서 SOL/BTC 우선 진행 결정으로 후순위 배치.  
**근거**: `strategies/catalog.py`: `SMC_MACD_1H` validation_status = NOT_STARTED. ETH는 Phase 3 multi-asset에서 negative 결과.  
**현시점 대책**:
- P3 비간섭 기간이므로 코드 변경 불가
- **문서 수준 준비만 가능**: Track B validation plan 초안 작성 (실행은 post-P3)
- ETH 결과가 negative였던 원인 분석 문서 참조 (cr046 evidence)

---

## A-09. Track C-v2 (대체 레짐 지표)

**상태**: NOT_STARTED  
**이유**: Track C-v1 (ADX/BB/ATR)이 crypto 1H에서 FAIL 판정. 대체 지표(realized vol, choppiness index, directional efficiency)는 연구 단계.  
**근거**: CR-046 evidence: C-v1은 non-discriminative in crypto 1H. 새 지표 후보는 식별되었으나 검증 미착수.  
**현시점 대책**:
- **문서 수준 연구만 가능**: 3개 후보 지표의 학술/실무 참고 자료 수집
- P3 이후 별도 연구 트랙으로 분리 실행 계획 수립
- C-v1 FAIL 원인 분석을 C-v2 설계에 반영할 교훈 정리

---

## A-10. LNS (유동성-서사 통합 시스템) 구현

**상태**: NOT_STARTED (설계 CLOSED)  
**이유**: 7파일 분해/검증 완료되었으나 코드 매핑이 미시작. P3 기간 중 새 기능 구현은 non-interference 위반.  
**근거**: project memory: "LNS 설계 체인 CLOSED, 코드매핑=NOT STARTED".  
**현시점 대책**:
- 설계 문서와 기존 코드 간 매핑 테이블 초안 작성 (읽기 전용 분석)
- 구현 시 영향받는 모듈 목록 사전 식별 (services, models, schemas)
- 실행은 post-P3 이후 별도 feature branch에서 진행

---

## A-11. GitHub Actions Node 24 업그레이드 (PR-A)

**상태**: NOT_STARTED  
**이유**: GitHub Actions에서 Node 16/20 → 24 마이그레이션 필요. Deadline 2026-06-02이므로 아직 여유 있음.  
**근거**: GitHub 공식 deprecation notice. CI workflow의 `actions/checkout`, `actions/setup-python` 등 영향.  
**현시점 대책**:
- **P3 비간섭과 무관한 CI 인프라 변경이지만, baseline 보전 원칙에 따라 대기 권고**
- post-P3 이후 첫 번째 인프라 작업으로 일정 배치
- 영향받는 action 목록 사전 식별: checkout@v4, setup-python@v5 등 호환성 확인

---

## A-12. PR-B Phase 2 (Approvals > 0 enforcement)

**상태**: NOT_STARTED  
**이유**: Phase 1 (PR rule, conversation resolution, status checks)은 완료. Phase 2 (required approvals > 0)는 1인 개발 환경에서 자기 승인이 필요하므로 운영 부담.  
**근거**: project memory: "approvals=0 BLOCK 모드, Phase 2 대기".  
**현시점 대책**:
- 1인 개발 환경에서의 self-approval 워크플로우 검토
- CODEOWNERS 파일 도입 여부 검토
- post-P3 이후 GitHub branch protection ruleset 업데이트로 일정 배치

---

## A-13. Typecheck Tier 2 → Blocking 전환

**상태**: DEFERRED  
**이유**: 현재 Tier 1 (15 strict files, `--disallow-untyped-defs`)만 blocking. Tier 2 (전체 app/)는 advisory(continue-on-error: true). 전체 app/ 101 서비스의 타입 커버리지가 부족하여 즉시 blocking 전환 시 CI 실패.  
**근거**: `.github/workflows/ci.yml`: typecheck-advisory job. 점진적 확대 전략.  
**현시점 대책**:
- Tier 2 advisory 결과에서 현재 실패하는 파일/에러 유형 카탈로그화 (읽기 전용 분석)
- 실패 건수가 적은 디렉토리부터 Tier 1 편입 후보 선정
- 전환 로드맵 초안: Tier 1 15 → 25 → 40 → 전체 (각 단계 CI PASS 확인 후 진행)

---

## A-14. pip-audit → Blocking 전환

**상태**: DEFERRED  
**이유**: 현재 continue-on-error: true. pip-audit 결과에 false positive나 upstream 미패치 CVE가 나타날 수 있어, 즉시 blocking 전환은 CI 안정성 훼손 위험.  
**근거**: `.github/workflows/ci.yml`: dependency-audit job. A4 advisory 해소 시 non-blocking으로 설정.  
**현시점 대책**:
- 현재 pip-audit 실행 결과 확인 (known CVE 유무)
- CVE 0건 상태가 안정되면 blocking 전환 시점 판단
- allowlist 메커니즘 사전 조사 (pip-audit --ignore VULN-ID)

---

## A-15. Grafana 대시보드 배포

**상태**: NOT_DEPLOYED  
**이유**: `k8s/monitoring.yaml`에 8개 alert rule + ServiceMonitor 정의 완료. 그러나 실제 Grafana 인스턴스 배포 및 대시보드 JSON provisioning은 미완.  
**근거**: 알림 규칙은 Prometheus/AlertManager에서 동작하나, 시각화 레이어 부재.  
**현시점 대책**:
- Grafana 대시보드 JSON 템플릿 사전 설계 (문서 수준)
- 주요 패널 후보: API latency p95, request rate, celery task failures, governance violations
- K8s Grafana deployment manifest 초안 (실행은 post-P3)

---

## A-16. Secrets 관리 (db_password.txt)

**상태**: MANUAL  
**이유**: `docker-compose.prod.yml`이 `secrets/db_password.txt` 파일 의존. 수동 생성이므로 배포 시 누락 가능. 자동화된 secrets 관리 도구 미적용.  
**근거**: docker-compose.prod.yml: `secrets: db_password: file: ./secrets/db_password.txt`.  
**현시점 대책**:
- secrets 관리 옵션 비교 문서 작성: Docker secrets vs K8s Secrets vs HashiCorp Vault vs Sealed Secrets
- 배포 체크리스트에 "secrets 파일 존재 확인" 항목 추가
- K8s 배포 시에는 `k8s/configmap.yaml` 외 별도 Secret manifest 필요 → 초안 설계

---

# B. 알려진 이슈 14항목 — 이유·근거·대책

---

## B-01. A3 SQL Injection surface

**이유**: SQLAlchemy ORM 사용으로 파라미터화 쿼리가 기본 적용. 그러나 `text()` 또는 raw `execute()` 호출 시 injection 가능성 잔존.  
**근거**: Advisory A3 ACCEPTED_RISK. ORM 계층이 방어 역할, exploitability Very Low.  
**현시점 대책**:
- `text(` 또는 `execute(` 패턴에 대한 grep 기반 코드리뷰 규칙 수립
- PR 리뷰 체크리스트에 "raw SQL 사용 여부 확인" 항목 추가
- 현재 상태: 안전 (모든 쿼리가 ORM 경유)

---

## B-02. A5 Redis Auth (dev)

**이유**: dev `docker-compose.yml`의 Redis에 `--requirepass` 미적용. dev 환경은 localhost 전용이므로 외부 노출 없음.  
**근거**: Advisory A5 ACCEPTED_RISK. prod `docker-compose.prod.yml`은 `--requirepass` 적용 완료.  
**현시점 대책**:
- dev 환경 문서에 "Redis 인증 없음 — 로컬 전용" 명시
- 향후 dev 환경도 비밀번호 적용 검토 (개발 편의성과 tradeoff)
- 현재 상태: 수용 가능한 리스크

---

## B-03. Typecheck Tier 2 advisory

**이유**: 전체 app/ 디렉토리에 대한 mypy strict 검사는 기술 부채로 인해 즉시 불가. 101개 서비스 파일 중 상당수가 타입 어노테이션 불완전.  
**근거**: CI의 `typecheck-advisory` job. Tier 1: 15 files strict blocking, Tier 2: 나머지 advisory.  
**현시점 대책**:
- Tier 2 실패 현황 분석 (어떤 에러 유형이 가장 많은지)
- 자동 수정 가능한 에러(missing return type 등) 우선 식별
- post-P3 이후 점진적 Tier 1 편입 실행

---

## B-04. pip-audit advisory (non-blocking)

**이유**: pip-audit를 blocking으로 전환하면 upstream에서 미패치된 CVE가 CI를 차단할 수 있음. 프로젝트 통제 밖의 외부 의존성 문제.  
**근거**: Advisory A4 RESOLVED (CI job 추가), 단 continue-on-error: true.  
**현시점 대책**:
- pip-audit 결과를 주기적으로 확인 (CI log 점검)
- Critical/High CVE 발견 시 즉시 대응 절차 수립
- allowlist로 false positive 관리 준비

---

## B-05. Grafana 대시보드 미배포

**이유**: alert rules와 ServiceMonitor는 K8s manifest에 정의 완료. 그러나 Grafana 자체 배포(Helm chart 또는 manifest)와 대시보드 provisioning은 미완.  
**근거**: `k8s/monitoring.yaml`: 8 alert rules + 1 ServiceMonitor 존재.  
**현시점 대책**:
- Grafana Helm chart values 또는 K8s manifest 초안 설계
- 핵심 대시보드 4개 패널 정의: health, trading, infra, governance
- post-P3 인프라 작업으로 일정 배치

---

## B-06. secrets/db_password.txt 수동 생성

**이유**: docker-compose.prod.yml이 file-based secret을 사용. 자동 생성 스크립트나 secrets manager 연동이 없어 배포 시 수동 파일 생성 필요.  
**근거**: `docker-compose.prod.yml`: `secrets` 섹션.  
**현시점 대책**:
- 배포 runbook에 "Step 0: secrets/db_password.txt 생성" 명시
- `scripts/init-secrets.sh` 같은 초기화 스크립트 초안 설계
- K8s 배포 시 `kubectl create secret` 명령 포함 체크리스트

---

## B-07. CORS allow_origins=["*"] (debug mode)

**이유**: `app/main.py`에서 `debug=True`일 때만 `allow_origins=["*"]` 적용. production에서는 빈 배열 `[]`.  
**근거**: 의도적 설계. debug 모드는 개발 편의를 위한 것이며, prod에서는 비활성화.  
**현시점 대책**:
- **조치 불필요**: BY_DESIGN으로 유지
- prod 배포 시 `DEBUG=false` 확인 항목을 배포 체크리스트에 포함
- 향후 특정 origin만 허용하는 allowlist 방식 검토 가능

---

## B-08. P3 novelty events 최소 10개 미달 가능성

**이유**: novelty events는 시장 환경에 의존. 14일 간 충분한 변동성이 없으면 10개 미달 가능. 시스템이 통제할 수 없는 외부 요인.  
**근거**: VAL-PDC-002 criteria #5 MIN_NOVELTY_EVENTS. GREEN tier 조건: novelty ≥ 10.  
**현시점 대책**:
- novelty event 카운터 현재 값 모니터링 (ops_state.json 또는 DB 조회)
- 미달 시 시나리오 사전 준비:
  - 5-9개: YELLOW tier → HOLD → 추가 관측 윈도우 설계
  - <5개: RED tier → BLOCK → 원인 분석
- **절대 인위적 novelty 생성 금지** (관측 무결성 훼손)

---

## B-09. Track B (ETH SMC_MACD) 미검증

**이유**: ETH/USDT는 Phase 3 multi-asset 평가에서 negative 결과. SMC_MACD 전략은 EXPERIMENTAL 상태로 별도 validation track 필요.  
**근거**: `strategies/catalog.py`: SMC_MACD_1H, validation_status=NOT_STARTED.  
**현시점 대책**:
- ETH negative 결과 원인 문서 재검토 (학습 목적)
- Track B validation plan 요구사항 초안 정리
- post-P3 이후 독립 track으로 실행

---

## B-10. Track C-v1 FAIL (ADX/BB/ATR)

**이유**: ADX, Bollinger Bands, ATR이 crypto 1H 타임프레임에서 레짐 식별에 비효과적임이 검증됨. 이는 CLOSED 상태의 학습 결과.  
**근거**: CR-046 evidence: non-discriminative in crypto 1H.  
**현시점 대책**:
- **조치 불필요**: CLOSED 상태, 학습 완료
- C-v1 FAIL 교훈을 C-v2 설계에 명시적으로 반영
- "crypto 1H에서 전통 변동성 지표의 한계" 문서화

---

## B-11. LNS 통합 시스템 코드매핑 미시작

**이유**: LNS 설계 체인 7파일 분해/검증은 완료되었으나, 실제 코드 매핑(어떤 service/model/schema에 구현할지)은 시작하지 않음. P3 기간 중 구현은 금지.  
**근거**: project memory: "LNS 설계 CLOSED, 코드매핑 NOT STARTED".  
**현시점 대책**:
- 설계 문서 기반 코드 매핑 테이블 초안 (문서 수준, 코드 변경 없음)
- 영향받는 모듈 의존성 그래프 작성
- post-P3 이후 별도 feature branch에서 구현

---

## B-12. GitHub Actions Node 24 마이그레이션

**이유**: GitHub의 Node.js 런타임 정책에 따라 actions runner의 Node 버전 업그레이드 필요. Deadline은 2026-06-02로 아직 여유.  
**근거**: GitHub 공식 deprecation timeline.  
**현시점 대책**:
- 현재 사용 중인 actions 버전 목록 확인 (checkout, setup-python 등)
- Node 24 호환 버전 확인
- post-P3 이후 CI 인프라 정비 시 함께 처리

---

## B-13. Worker/Beat probe exec 명령 길이

**이유**: K8s exec probe에서 Python one-liner로 Celery connection check를 실행. YAML 내 명령 문자열이 길어 가독성 저하.  
**근거**: `k8s/deployment.yaml`: `command: ["python", "-c", "from workers.celery_app import app; app.connection_for_read().ensure_connection(max_retries=1)"]`.  
**현시점 대책**:
- **기능상 정상이므로 즉시 조치 불필요**
- 향후 리팩터링 시 별도 health check 스크립트(`scripts/celery_health.py`)로 분리 검토
- 현재 상태: ACCEPTED (가독성 이슈만, 동작에 영향 없음)

---

## B-14. Evidence DB 기본값 in-memory

**이유**: `EVIDENCE_DB_PATH` 환경변수 미설정 시 EvidenceStore가 InMemoryBackend를 사용. 프로세스 재시작 시 모든 증빙 소실.  
**근거**: `app/main.py` L47-57: backend 선택 로직. prod ConfigMap에는 `EVIDENCE_DB_PATH=/app/data/prod_evidence.db` 설정됨.  
**현시점 대책**:
- **prod 환경은 이미 SQLite 설정 완료** (k8s/configmap.yaml 확인)
- dev 환경에서도 SQLite 사용 권장 문서 추가
- lifespan 로그에서 "evidence_mode=IN_MEMORY" 출력 시 경고 수준 상향 검토

---

# C. 부족점 10항목 — 이유·근거·대책

---

## C-01. Live entry 영구 차단

**이유**: `check_live_entry()` always returns HARD_BLOCK. 조건부 분기가 없으므로 코드 변경 없이는 해제 불가. 이는 안전 설계이지만, 궁극적으로 실제 운영을 위해서는 해제 경로가 필요.  
**근거**: FZ-03, FZ-04. 의도적 하드코딩.  
**현시점 대책**:
- **현재 단계에서는 조치 불필요이자 조치 금지**
- 향후 Live entry 해제를 위한 사전 조건 체크리스트 설계:
  1. Paper trading N일 이상 PASS
  2. Promotion tier = GREEN
  3. Human CR 발행 + 다중 승인
  4. 별도 feature branch에서 `check_live_entry()` 조건부 분기 추가
  5. CI PASS + squash merge
  6. 별도 Live Authorization Receipt 발행

---

## C-02. Typecheck 부분 적용

**이유**: 101개 서비스 중 15개만 strict typecheck. 나머지는 타입 어노테이션 불완전. 한번에 전환하면 CI가 깨짐.  
**근거**: CI: typecheck-blocking (Tier 1, 15 files) vs typecheck-advisory (Tier 2, 전체).  
**현시점 대책**:
- Tier 2 advisory 실패 로그 분석하여 "쉽게 고칠 수 있는" 파일 우선 식별
- 점진적 확대 로드맵 설계: 15 → 25 → 40 → 60 → 전체
- 각 단계에서 CI PASS 확인 후 다음 단계 진행
- **P3 비간섭 중이므로 실제 코드 수정은 post-P3**

---

## C-03. pip-audit non-blocking

**이유**: pip-audit가 외부 CVE DB에 의존하므로, false positive나 upstream 미패치 이슈로 CI가 불필요하게 차단될 위험.  
**근거**: A4 advisory 해소 시 non-blocking으로 설정한 의도적 결정.  
**현시점 대책**:
- pip-audit 결과를 주기적으로 모니터링
- Critical CVE = 0 상태가 N회 연속 확인되면 blocking 전환 시점 판단
- `pip-audit --ignore` 기반 allowlist 준비

---

## C-04. Grafana 미배포

**이유**: alert rules + ServiceMonitor는 정의되었으나, Grafana 인스턴스 자체와 대시보드 provisioning이 미완.  
**근거**: k8s/monitoring.yaml에 규칙만 존재, 시각화 레이어 부재.  
**현시점 대책**:
- Grafana deployment manifest 초안 설계 (helm values 또는 raw yaml)
- 핵심 대시보드 JSON 4개 설계:
  1. System Health (API latency, request rate, error rate)
  2. Trading (governance violations, regime transitions, OHLCV coverage)
  3. Infrastructure (celery failures, DB slow queries)
  4. Governance (PPF gate decisions, constitution checks)
- post-P3 인프라 작업으로 배치

---

## C-05. Secrets 수동 관리

**이유**: secrets 파일을 수동으로 생성해야 하므로, 배포 시 누락 또는 잘못된 값 입력 위험. 자동화된 rotation 메커니즘 없음.  
**근거**: docker-compose.prod.yml secrets 섹션.  
**현시점 대책**:
- secrets 관리 전략 비교표 작성:

| 방식 | 복잡도 | 보안 | 자동 rotation | 적합 환경 |
|------|--------|------|--------------|-----------|
| File-based (현재) | Low | Low | 없음 | dev/단일 서버 |
| K8s Secrets | Medium | Medium | 수동 | K8s 클러스터 |
| Sealed Secrets | Medium | High | 수동 | GitOps |
| HashiCorp Vault | High | Very High | 자동 | Enterprise |

- 단기: 배포 runbook에 secrets 생성 절차 명시
- 중기: K8s Secrets manifest 추가 (post-P3)
- 장기: Vault 또는 Sealed Secrets 도입 검토

---

## C-06. Evidence DB 기본값 in-memory

**이유**: EVIDENCE_DB_PATH 미설정 시 증빙이 프로세스 메모리에만 존재. 재시작 시 모든 거버넌스 판단 기록 소실.  
**근거**: app/main.py evidence backend 선택 로직.  
**현시점 대책**:
- **prod는 이미 해결됨** (k8s/configmap.yaml: EVIDENCE_DB_PATH=/app/data/prod_evidence.db)
- dev 환경: `.env.example`에 `EVIDENCE_DB_PATH=./dev_evidence.db` 추가 권장
- lifespan 로그에서 IN_MEMORY 감지 시 WARNING → 가시성 향상

---

## C-07. Track B/C-v2 미검증

**이유**: 전략 다양성이 SMC_WaveTrend_1H 단일 OPERATIONAL에 의존. Track B (SMC_MACD)와 Track C-v2 (대체 레짐)는 미검증 상태.  
**근거**: strategies/catalog.py: EXPERIMENTAL 2개, validation NOT_STARTED.  
**현시점 대책**:
- Track B/C-v2 validation plan 문서 초안 작성
- P3 이후 독립 validation track으로 분리 실행
- 각 track에 별도 P1-P3 validation chain 적용 필요

---

## C-08. LNS 미구현

**이유**: 유동성-서사 통합 시스템 설계는 완료되었으나 코드로 전환되지 않음. 새 기능이므로 기존 시스템에 영향 없으나, 계획된 기능의 미구현 상태.  
**근거**: project memory: "설계 CLOSED, 코드매핑 NOT STARTED".  
**현시점 대책**:
- 코드 매핑 문서 (설계 ↔ module 대응표) 작성 (읽기 전용)
- 구현 우선순위: Track B/C-v2보다 후순위 (기존 전략 검증이 우선)
- post-P3 이후 별도 feature branch에서 단계적 구현

---

## C-09. P3 novelty 미달 리스크

**이유**: novelty events는 시장 변동성에 의존하는 외부 요인. 시스템이 직접 통제할 수 없음. 조용한 시장에서는 14일 간 10 events 미달 가능.  
**근거**: VAL-PDC-002 MIN_NOVELTY_EVENTS. GREEN ≥ 10, YELLOW 5-9, RED < 5.  
**현시점 대책**:
- **통제 불가 요인이므로 대비만 가능**
- 시나리오별 대응 계획 확정:
  - GREEN (≥10): 정상 진행
  - YELLOW (5-9): HOLD + 추가 관측 윈도우 설계 (연장 기간 산정)
  - RED (<5): BLOCK + 근본 원인 분석 (시장 환경 vs novelty 감지 로직)
- **인위적 novelty 생성 절대 금지** (관측 무결성은 최상위 원칙)

---

## C-10. 단일 asset 운영

**이유**: SOL/USDT만 OPERATIONAL. BTC/USDT는 guarded paper (latency guard 필수), ETH/USDT는 Phase 3에서 excluded.  
**근거**: CR-046 operational path: SOL 1순위, BTC 2순위(guarded), ETH excluded.  
**현시점 대책**:
- SOL P3 결과가 PASS일 경우 BTC guarded paper 진입 조건 재점검
- ETH는 Track B 검증 결과에 따라 재판단
- 다중 asset 운영은 단일 asset PASS 이후 순차 확장 (동시 다중 진입 금지)

---

# D. 총괄 매트릭스

---

## 분류별 요약

| 분류 | 총 수 | 즉시 조치 가능 | P3 후 조치 | 의도적 설계 | 외부 의존 |
|------|-------|---------------|-----------|------------|----------|
| **미완성 16** | 16 | 0 | 11 | 2 (A-06, A-07) | 3 (A-01, A-03, A-08~09) |
| **이슈 14** | 14 | 0 | 8 | 3 (B-07, B-10, B-13) | 3 (B-04, B-08, B-12) |
| **부족점 10** | 10 | 0 | 7 | 1 (C-01) | 2 (C-09, C-10) |
| **총합** | **40** | **0** | **26** | **6** | **8** |

## 현시점 행동 가능 범위

```
┌─────────────────────────────────────────────────────────┐
│  현시점에서 가능한 행동 = 문서 수준 준비만               │
│                                                         │
│  코드 변경:    금지 (P3 non-interference)                │
│  인프라 변경:  금지 (baseline 보전)                      │
│  문서 작성:    가능 (읽기 전용 분석, 계획 초안)           │
│  모니터링:     가능 (ops_state, CI log, P3 카운터)       │
│  시나리오 준비: 가능 (PASS/HOLD/BLOCK 대응 계획)         │
│                                                         │
│  즉시 조치 가능 항목: 0 / 40                             │
│  P3 후 조치 대상:    26 / 40                             │
│  의도적 설계(유지):   6 / 40                             │
│  외부 의존(대기):     8 / 40                             │
└─────────────────────────────────────────────────────────┘
```

## 우선순위 서열 (post-P3 실행 시)

| 순위 | 항목 | 이유 |
|------|------|------|
| P0 | A-01→A-02→A-03 (P3→VAL-PDC-002→판정) | 모든 후속 행동의 선결 조건 |
| P1 | A-04→A-05 (Paper 진입) | 판정 PASS 시 즉시 필요 |
| P2 | A-11 (Node 24 upgrade) | 외부 deadline 2026-06-02 |
| P3 | A-13, A-14 (Typecheck/pip-audit blocking 전환) | CI 강화, 기술 부채 해소 |
| P4 | A-15, C-04 (Grafana 배포) | 모니터링 가시성 향상 |
| P5 | A-16, C-05 (Secrets 관리) | 배포 안정성 |
| P6 | A-08, A-09, C-07 (Track B/C-v2) | 전략 다양성 확대 |
| P7 | A-10, C-08 (LNS 구현) | 신규 기능, 기존 검증 후 |
| P8 | A-12 (PR-B Phase 2) | 운영 프로세스 강화 |

---

*END OF DOCUMENT*
