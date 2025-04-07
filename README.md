# AI 비트코인 트레이딩 봇

AI를 활용한 비트코인 자동 거래 봇입니다. 기술적 지표 분석과 AI의 시장 상황 분석을 기반으로 거래 결정을 내리고 실행합니다.

## 주요 기능

- 여러 타임프레임(15분, 1시간, 4시간)의 시장 데이터 분석
- 기술적 지표(RSI, MACD, 볼린저 밴드, 이동평균선) 계산
- 대규모 언어 모델을 활용한 시장 분석
- 자동 거래 실행 (롱/숏 포지션)
- 스탑로스 및 테이크프로핏 자동 관리
- 거래 기록 및 성과 추적
- Dry Run 모드 지원 (실제 거래 없이 시뮬레이션)

## 모듈 구조

- **main.py**: 메인 프로그램 및 실행 루프
- **config.py**: 설정 및 환경 변수
- **database.py**: 데이터베이스 관련 기능
- **data_collector.py**: 시장 데이터 수집
- **analyzer.py**: AI 분석 및 거래 결정
- **trader.py**: 거래 실행 및 포지션 관리
- **utils.py**: 유틸리티 함수

## 설치 방법

1. 저장소 클론

```bash
git clone https://github.com/yourusername/ai-bitcoin-trading-bot.git
cd ai-bitcoin-trading-bot
```

2. 필요한 패키지 설치

```bash
pip install -r requirements.txt
```

3. `.env` 파일 생성 및 API 키 설정

```
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET_KEY=your_binance_secret_key
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=your_preferred_model
SERP_API_KEY=your_serp_api_key
DRY_RUN=True
```

## 실행 방법

```bash
python main.py
```

## Dry Run 모드

실제 거래 없이 시뮬레이션만 실행하려면 `.env` 파일에서 `DRY_RUN=True`로 설정하세요.

## Docker로 실행하기

Docker와 Docker Compose를 사용하여 봇과 대시보드를 컨테이너 환경에서 실행할 수 있습니다.

1.  **Docker 및 Docker Compose 설치:** 시스템에 Docker와 Docker Compose가 설치되어 있는지 확인하세요.
2.  **`.env` 파일 준비:** 프로젝트 루트 디렉토리에 필요한 API 키와 설정을 포함하는 `.env` 파일을 생성합니다. `.env.example` 파일을 참조하세요.
3.  **Docker 이미지 빌드 및 컨테이너 실행:** 터미널에서 다음 명령어를 실행합니다.

    ```bash
    docker-compose up --build -d
    ```

    - `--build`: 이미지를 새로 빌드합니다 (처음 실행 시 또는 코드 변경 시).
    - `-d`: 컨테이너를 백그라운드에서 실행합니다.

4.  **대시보드 접속:** 웹 브라우저를 열고 `http://localhost:8501` 로 접속하여 Streamlit 대시보드를 확인합니다.
5.  **로그 확인:** 트레이딩 봇의 로그는 다음 명령어로 확인할 수 있습니다.

    ```bash
    docker-compose logs -f trading_bot
    ```

6.  **컨테이너 중지:** 컨테이너를 중지하려면 다음 명령어를 실행합니다.

    ```bash
    docker-compose down
    ```

## 주의사항

- 암호화폐 거래에는 상당한 위험이 따릅니다. 이 봇을 사용한 거래는 사용자 책임입니다.
- API 키는 항상 안전하게 보관하세요.
- 실제 자금을 투자하기 전에 충분한 Dry Run 테스트를 수행하세요.

## 설정 옵션

`config.py` 파일에서 다음 설정을 조정할 수 있습니다:

- 거래 페어 (기본값: BTC/USDT)
- AI 모델
- 레버리지 및 포지션 크기 한도
- 주기 간격 (메인 루프, 가격 체크, 포지션 체크)
- 캐시 타임아웃

## 라이센스

MIT License 