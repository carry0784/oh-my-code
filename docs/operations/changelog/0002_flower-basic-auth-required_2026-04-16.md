# 0002 — Flower Basic Auth 환경변수 필수화

**Date**: 2026-04-16
**Author**: claude-code (autonomous)
**Gate classification**: autonomous (config hardening, reversible, no deployment trigger)
**Scope**: infra (docker-compose.yml)

## What

`docker-compose.yml`의 `flower` 서비스에 다음 환경변수를 필수로 추가:

```yaml
FLOWER_BASIC_AUTH: "${FLOWER_BASIC_AUTH:?operator_manual_injection_required}"
```

`:?` 구문으로 인해 `FLOWER_BASIC_AUTH` 환경변수가 주입되지 않으면 `docker compose up` 시 컨테이너가 기동되지 않고 명확한 에러 메시지를 반환한다.

## Why

- 이전 상태: Flower UI (5555 포트)가 인증 없이 브로커 상태·태스크 이력·실행 중 큐를 노출
- Advisory A5 (Redis auth) 대응과 동질의 표면 축소
- `k_v3_residual_items_countermeasures.md` 내 명시된 "PROBE_FLOWER_API_AUTH_REQUIRED" deferred 항목의 인프라측 사전 조치
- 운영자가 명시적으로 auth string을 주입해야 기동 가능 → fail-closed 보장

## Evidence

- 원본 diff: `docker-compose.yml`에 `FLOWER_BASIC_AUTH` 한 줄 추가
- 관련 구조 선언: `docs/operations/evidence/cr_new_p3_structural_resolved_declaration_2026-04-15.md` 에서 PROBE_FLOWER_API_AUTH deferred 범위 명시
- secrets 수동 주입 패턴: `docker-compose.prod.yml` `secrets` 섹션과 동일 사상

## Reversibility

- `git revert` 로 즉시 되돌릴 수 있는 단일 라인 변경
- 기동 중인 컨테이너에는 영향 없음 (다음 `up` 시점부터 적용)

## Operator Action Required (배포 시)

`.env` 또는 shell 환경에 다음을 주입해야 함:

```bash
# 예: htpasswd 형식 또는 username:password
export FLOWER_BASIC_AUTH="admin:$(openssl rand -hex 16)"
```

해당 값이 없으면 flower 서비스는 기동되지 않는다.

