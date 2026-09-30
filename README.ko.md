# Recon3D Cross-Cell DEG

[English](README.md) | 한국어

두 세포 유형의 DEG를 Recon3D 반응에 연결하고, 대사물질을 매개로 이어질 수 있는 경로와 근거의 한계를 검토하는 **Agent Skills 표준 스킬 + Jev/Laya API 연동 코드**입니다.

## 포함된 기능

- Recon3D 경로·GPR·환자별 짝지음·전체 검정군 통계·근거 등급을 다루는 [분석 지침](skills/recon3d-cross-cell-deg/SKILL.md)
- Codex/ChatGPT 및 Claude 플러그인 메타데이터, Claude marketplace
- Codex·Claude Code·Cursor·Gemini CLI용 설치 도구와 범용 지침 내보내기
- TypeSafe **Jev System One API** 클라이언트와 동일 규격을 사용하는 **Laya** 서버 연결
- 전체 후보를 유지하는 선택적 검토 순서 평가, 실패 상태·모델·확률·사용량 기록
- 합성 데이터로 수행하는 HTTP 계약 테스트와 Linux/macOS/Windows CI

실행 코드는 설치·패키징·지침 로딩·API 호출·검토 순서 평가를 제공합니다. Recon3D 모델, 환자 데이터, 경로 열거·GPR 계산·통계 분석 파이프라인 자체는 포함하지 않습니다. 필요한 모델과 발현 자료를 제공하고 스킬 지침에 따라 분석 도구를 실행해야 합니다.

## 제공된 테스트 파일의 실측 결과

`DEG_hits_CD4_and_HF.csv`(97행, 66개 유전자)와 Recon3D(10,600개 반응)로 **DEG→반응 매핑**을 비교했습니다. 새로 구현한 반복 전수 스캔 기준은 62.09ms, 색인 방식은 생성 비용을 포함해 13.36ms로 **4.65배 빠르고 시간이 78.5% 줄었습니다**. Darwin arm64·Python 3.14.4에서 각 방식 21회 측정한 중앙값이며, 공통 파일 로딩·검증 시간은 제외했습니다.

![매핑 단계 시간 비교](benchmarks/results/2026-09-30-mapping/mapping-runtime-db3d6fb9d341.png)

그림의 **Rule-based = 규칙 기반**, **Our system = 본 시스템**입니다. 규칙 기반은 새로 구현한 반복 전수 스캔, 본 시스템은 색인 매핑을 뜻합니다. 왼쪽은 색인 생성 비용을 포함한 첫 사용, 오른쪽은 기존 색인을 재사용할 때의 시간입니다. 이 라벨은 매핑 구현을 구분하며, Laya/Jev 추론 비교를 뜻하지 않습니다.

97행을 모두 유지했으며, **DEG 행–반응 연결 198개와 고유 반응 125개**가 동일했습니다. 행·반응 ID가 100% 일치하고 독립적으로 구현한 검사 방식과도 일치했습니다. 이는 기계적 매핑 결과를 보존했다는 의미이며, 생물학적 정확도가 향상됐다는 의미는 아닙니다.

![매핑 결과 보존 비교](benchmarks/results/2026-09-30-mapping/mapping-output-f2df6fc1058f.png)

**측정 범위:** GPR에 해당 유전자가 포함되는지 매핑하는 단계입니다. 이전 프로토타입의 코드·실행 결과를 확보하지 못해 비교 기준을 새로 구현했습니다. 전체 경로 탐색 시간, 생물학적 정확도, Laya/Jev 개선율은 아직 측정하지 않았습니다. [측정 방법·입력 해시·전체 시간 기록·재현 명령·SVG](benchmarks/README.md)를 함께 제공합니다. 원본 테스트 데이터는 공개하지 않습니다.

## 빠른 설치

Python 3.10+가 필요하며, 추가 Python 패키지는 필요하지 않습니다.

```sh
git clone https://github.com/hpend2373/recon3d-cross-cell-deg.git
cd recon3d-cross-cell-deg
python3 tools/manage.py validate
python3 tools/manage.py install --framework codex
```

사용할 프레임워크를 선택합니다:

| 옵션 | 로컬 사용자 설치 위치 | 호환 방식 |
|---|---|---|
| `codex` | `~/.agents/skills/` | Codex 네이티브 Agent Skills |
| `claude` | `~/.claude/skills/` | Claude Code 네이티브 스킬 |
| `cursor` | `~/.cursor/skills/` | Cursor 네이티브 Agent Skills |
| `gemini` | `~/.gemini/skills/` | Agent Skills를 지원하는 Gemini CLI |
| `agents` | `~/.agents/skills/` | 이 공통 경로를 읽는 다른 호스트 |

예를 들어 `python3 tools/manage.py install --framework claude`로 설치합니다. 프로젝트 설치는 `--project /path/to/project`, 다른 스킬 경로는 `--destination /path/to/skills`를 사용합니다. 기존 스킬과 내용이 다르면 자동으로 덮어쓰지 않습니다. `--replace`를 지정하면 기존 폴더를 `skill-backups/`로 이동한 뒤 교체합니다.

Codex에서는 `$recon3d-cross-cell-deg`, Claude Code의 직접 설치에서는 `/recon3d-cross-cell-deg`로 호출합니다. 각 호스트가 스킬을 재탐색한 뒤 사용하세요. 설치 경로를 복사하는 작업은 해당 기기의 로컬 설치이며, 계정 전역 클라우드 설치와 별개입니다.

### Claude Code 플러그인으로 설치

```sh
claude plugin marketplace add hpend2373/recon3d-cross-cell-deg
claude plugin install recon3d-cross-cell-deg@recon3d-skills
```

플러그인 호출 이름은 `/recon3d-cross-cell-deg:recon3d-cross-cell-deg`입니다. 직접 설치와 플러그인 설치 중 하나를 선택하세요.

### ChatGPT 계정용 플러그인

```sh
python3 tools/manage.py pack --kind plugin --output dist/recon3d-plugin.zip
```

생성된 ZIP을 ChatGPT 플러그인 추가 화면에 업로드하고 계정에 설치합니다. 기존 계정 플러그인은 GitHub 업로드만으로 갱신되지 않습니다. GitHub 저장소는 기기 간 공유·설치할 수 있는 공개 배포 원본을 제공합니다.

단일 스킬 ZIP은 `python3 tools/manage.py pack --kind skill --output dist/recon3d-skill.zip`로 만들 수 있습니다.

## 다른 에이전트 프레임워크에서 사용

네이티브 스킬 탐색을 제공하지 않는 프레임워크에서는 지침을 읽어 에이전트의 instruction/system 입력으로 전달합니다. 다음 인터페이스는 특정 모델 SDK에 의존하지 않습니다.

```sh
python3 skills/recon3d-cross-cell-deg/scripts/recon3d.py prompt --json
```

```python
import sys
from pathlib import Path

scripts = Path("skills/recon3d-cross-cell-deg/scripts").resolve()
sys.path.insert(0, str(scripts))
from recon3d_bridge import load_instructions, JevClient, prioritize

instructions = load_instructions()  # 프레임워크의 instruction/system 입력에 전달
client = JevClient()               # TYPESAFE_API_KEY 환경변수 사용
```

이 방식으로 지침을 불러오고 API 클라이언트를 도구 함수로 감쌀 수 있습니다. 임의의 프레임워크의 모든 버전에서 자동 설치·실행된다는 보장은 하지 않습니다. 호스트의 컨텍스트 크기, Python 실행 도구, 모델·입력 자료는 따로 준비해야 합니다.

## Jev API 사용

[TypeSafe 공식 HTTP 규격](https://docs.typesafe.ai/api)에 맞춰 `noul`, `choice`, `score`를 지원합니다. API 키를 환경변수 `TYPESAFE_API_KEY` 또는 `JEV_API_KEY`에 설정한 뒤 실행합니다.

```sh
python3 skills/recon3d-cross-cell-deg/scripts/recon3d.py models --provider jev
python3 skills/recon3d-cross-cell-deg/scripts/recon3d.py evaluate \
  --input examples/decision.json --output outputs/decision.json
python3 skills/recon3d-cross-cell-deg/scripts/recon3d.py prioritize \
  --input examples/candidates.json --output outputs/priorities.json
```

키 없이 요청 형식만 확인하려면 `evaluate`에 `--dry-run`을 추가합니다. 전체 후보 목록을 유지하면서 API 없이 실행하려면 `prioritize`에 `--no-model`을 추가합니다. 예제는 모두 합성 자료입니다.

### Laya 연결

Jev 호환 HTTP 서버를 먼저 실행한 뒤 실제 제공되는 모델 이름을 지정합니다:

```sh
python3 skills/recon3d-cross-cell-deg/scripts/recon3d.py models --provider laya
python3 skills/recon3d-cross-cell-deg/scripts/recon3d.py prioritize \
  --provider laya --model laya --base-url http://127.0.0.1:8000/v1 \
  --input examples/candidates.json --output outputs/laya-priorities.json
```

인증을 사용하는 Laya 서버는 `LAYA_API_KEY`를 설정합니다. 전체 요청 형식, 실패 처리, 재시도 및 해석은 [연동 문서](skills/recon3d-cross-cell-deg/references/decision-api.md)를 참조하세요.

## 검증 및 호환 범위

```sh
python3 tools/manage.py validate
python3 -m unittest discover -s tests -v
claude plugin validate .claude-plugin/plugin.json --strict
claude plugin validate .claude-plugin/marketplace.json --strict
```

테스트는 실제 loopback HTTP 서버를 사용하므로 로컬 소켓을 허용해야 합니다. API 키나 모델 가중치 없이 실행합니다.

| 항목 | 확인 범위 |
|---|---|
| 스킬/플러그인 | 이름·버전·경로·원본 본문 무결성, Claude 공식 validator |
| 설치 코드 | 각 대상 경로 복사, 설치된 CLI 실행, 기존 내용 보존·백업 |
| Jev/Laya API | 합성 서버에서 요청·응답, 세 질문 유형, 인증, 오류·확률 검증, 재시도 |
| 후보 처리 | 성공·실패 후보 모두 보존, 과학적 검토는 `pending` 유지 |
| CI | Python 3.10/3.13, Linux/macOS/Windows에서 계약·배포 테스트 |
| 실제 호스팅 Jev 추론 | API 키가 있는 환경에서 별도 검증 필요 |
| 실제 Laya 추론 | 실행 중인 서버·모델 가중치가 있는 환경에서 별도 검증 필요 |

공식 호환 근거: [Agent Skills 표준](https://agentskills.io/specification), [Codex 스킬](https://learn.chatgpt.com/docs/build-skills), [Claude Code 스킬](https://code.claude.com/docs/en/skills), [Claude 플러그인](https://code.claude.com/docs/en/plugins-reference), [Cursor 스킬](https://cursor.com/docs/skills), [Gemini CLI 스킬](https://geminicli.com/docs/cli/skills/), [Jev API](https://docs.typesafe.ai/api), [Laya 소스](https://github.com/NandhaKishorM/laya).

## 입력·근거의 한계

Recon3D 모델에는 반응 ID, 전체 화학양론, 경계값, GPR, 구획, 유전자 매핑이 필요합니다. DEG 요약표와 모델만 있으면 끝점 매핑과 모델상 가능한 경로를 검토할 수 있습니다. 경로 전체의 RNA 근거에는 환자별 전후 발현·검출 세포 수·정규화·짝지음·전체 검정군 통계가 필요합니다.

RNA 대리값이나 Jev/Laya 점수는 효소 활성·대사물질 농도·세포 간 전달·flux·인과관계를 입증하지 않습니다. API 평가는 검토 순서를 제안하며, 후보를 제거하거나 근거 등급을 결정하지 않습니다. 전체 후보의 과학적 검토가 끝나기 전에는 완료로 표시하지 않습니다.

## 출처

제공된 원본 `SKILL.md` 본문 17,107바이트를 그대로 보존하고, 마지막에 선택적 API 연동 안내를 추가했습니다. 원본 SHA-256: `8c940dbced24938533ce69dc0260fa88159d6b49e4a33812bb871840ad76fdd8`. 원본의 Rinvoq 경로는 해당 프로젝트가 접근 가능한 경우만 사용하는 선택적 안내입니다.
