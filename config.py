"""
설정 및 환경 변수
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

# .env 파일에서 환경 변수 로드
load_dotenv()

# 거래 설정
SYMBOL = "BTC/USDT"  # 거래 페어 설정

# 바이낸스 API 설정
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")  # 바이낸스 API 키
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")  # 바이낸스 시크릿 키

# OpenRouter API 설정
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")  # OpenRouter API 키
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")  # OpenRouter 모델
OPENROUTER_REFERER = "https://github.com/hancy87/autotrade"  # 필요한 경우 수정
OPENROUTER_TITLE = "AI-Trading-Bot"

# SERP API 설정 (뉴스 데이터 수집용)
SERP_API_KEY = os.getenv("SERP_API_KEY")  # 서프 API 키

# SQLite 데이터베이스 설정
DB_FILE = "bitcoin_trading.db"  # 데이터베이스 파일명

# Dry Run 모드 설정 (True인 경우 실제 거래 없이 시뮬레이션만 실행)
DRY_RUN = os.getenv("DRY_RUN", "False").lower() in ["true", "t", "1", "yes", "y"]

# API 및 요청 관련 설정
MAX_API_RETRIES = 3                 # API 호출 재시도 최대 횟수
MAX_REASONING_LENGTH = 1000         # 분석 내용 저장 시 최대 길이 제한

# 타이밍 관련 설정
MAIN_LOOP_INTERVAL = 60             # 메인 루프 간격 (초)
PRICE_CHECK_INTERVAL = 10           # 가격 체크 간격 (초)
MIN_DATA_REFRESH_INTERVAL = 5 * 60  # 데이터 갱신 최소 간격 (초)
POSITION_CHECK_INTERVAL = 5         # 포지션 체크 간격 (초)

# 캐시 타임아웃 설정 (초)
CACHE_TIMEFRAMES = {
    "15m": 10 * 60,   # 15분 데이터는 10분마다 갱신
    "1h": 30 * 60,    # 1시간 데이터는 30분마다 갱신
    "4h": 60 * 60     # 4시간 데이터는 1시간마다 갱신
}
NEWS_CACHE_TTL = 3600  # 뉴스 캐시 유효 시간 (1시간)

# 시뮬레이션 모드 설정
SIM_CAPITAL = 10000    # 시뮬레이션 모드에서 사용할 가상 자본 (USDT)
MIN_ORDER_AMOUNT = 100 # 최소 주문 금액 (USDT)

# OpenAI 클라이언트 초기화 (OpenRouter용)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "HTTP-Referer": OPENROUTER_REFERER,
        "X-Title": OPENROUTER_TITLE
    }
)

# 상태 메시지 출력
print(f"Dry Run Mode: {'활성화됨 (실제 거래 없음)' if DRY_RUN else '비활성화됨 (실제 거래 실행)'}") 