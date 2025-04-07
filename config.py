"""
설정 및 환경 변수
"""
import os
import requests
import time
import logging
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
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")  # OpenRouter 모델
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

# AI API 비용 설정 (폴백 값 및 동적 로딩)
# 폴백 값 (모델 정보 로딩 실패 시 사용)
FALLBACK_COST_INPUT_PER_MILLION_TOKENS = 0.15 # 예시: gpt-4o-mini 가격
FALLBACK_COST_OUTPUT_PER_MILLION_TOKENS = 0.6 # 예시: gpt-4o-mini 가격

# 모델 가격 정보 캐시
_model_pricing_cache = {
    "data": None,
    "timestamp": 0,
    "ttl": 3600 # 1시간 캐시
}

def get_model_pricing(model_id):
    """
    OpenRouter API에서 특정 모델의 가격 정보를 가져옵니다.
    결과는 캐시되어 사용됩니다.

    매개변수:
        model_id (str): 가격 정보를 가져올 모델 ID

    반환값:
        dict: {'input': cost_input_mill, 'output': cost_output_mill} 형식의 가격 정보. 실패 시 None.
    """
    global _model_pricing_cache
    now = time.time()
    
    # 캐시 확인
    if _model_pricing_cache["data"] and (now - _model_pricing_cache["timestamp"] < _model_pricing_cache["ttl"]):
        if model_id in _model_pricing_cache["data"]:
            return _model_pricing_cache["data"][model_id]
        # 캐시에 특정 모델 정보가 없는 경우 아래 로직 실행

    # 캐시가 없거나 만료된 경우 API 호출
    print(f"OpenRouter에서 모델 가격 정보 로딩 중 ({model_id})...")
    try:
        response = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        response.raise_for_status() # HTTP 오류 발생 시 예외 발생
        models_data = response.json()

        pricing_data = {}
        for model in models_data.get("data", []):
            current_model_id = model.get("id")
            if not current_model_id:
                continue

            price_info = model.get("pricing", {})
            # 가격 정보는 보통 토큰 1개당 비용으로 제공됨
            cost_input_per_token = float(price_info.get("prompt", 0))
            cost_output_per_token = float(price_info.get("completion", 0))
            
            # 백만 토큰당 비용으로 변환
            cost_input_mill = cost_input_per_token * 1_000_000
            cost_output_mill = cost_output_per_token * 1_000_000
            
            pricing_data[current_model_id] = {
                'input': cost_input_mill,
                'output': cost_output_mill
            }

        # 캐시 업데이트
        _model_pricing_cache["data"] = pricing_data
        _model_pricing_cache["timestamp"] = now

        if model_id in pricing_data:
            print(f"{model_id} 가격 로딩 완료: 입력 ${pricing_data[model_id]['input']:.4f}/M, 출력 ${pricing_data[model_id]['output']:.4f}/M")
            return pricing_data[model_id]
        else:
            print(f"경고: OpenRouter 응답에서 모델 '{model_id}'의 가격 정보를 찾을 수 없습니다.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"오류: OpenRouter 모델 정보 API 호출 실패: {e}")
        return None
    except Exception as e:
        print(f"오류: 모델 가격 정보 처리 중 예외 발생: {e}")
        return None

# 동적 모델 비용 로드 시도
print(f"사용 설정된 모델: {OPENROUTER_MODEL}")
dynamic_pricing = get_model_pricing(OPENROUTER_MODEL)

if dynamic_pricing:
    MODEL_COST_INPUT_PER_MILLION_TOKENS = dynamic_pricing['input']
    MODEL_COST_OUTPUT_PER_MILLION_TOKENS = dynamic_pricing['output']
else:
    print(f"경고: '{OPENROUTER_MODEL}' 모델의 동적 가격 로딩 실패. 설정된 폴백 가격 사용: 입력 ${FALLBACK_COST_INPUT_PER_MILLION_TOKENS}/M, 출력 ${FALLBACK_COST_OUTPUT_PER_MILLION_TOKENS}/M")
    MODEL_COST_INPUT_PER_MILLION_TOKENS = FALLBACK_COST_INPUT_PER_MILLION_TOKENS
    MODEL_COST_OUTPUT_PER_MILLION_TOKENS = FALLBACK_COST_OUTPUT_PER_MILLION_TOKENS

# 타이밍 관련 설정
MAIN_LOOP_INTERVAL = 60             # 메인 루프 간격 (초)
PRICE_CHECK_INTERVAL = 60           # 가격 체크 간격 (초)
MIN_DATA_REFRESH_INTERVAL = 5 * 60  # 데이터 갱신 최소 간격 (초)
POSITION_CHECK_INTERVAL = 5 * 60         # 포지션 체크 간격 (초)

# 캐시 타임아웃 설정 (초)
CACHE_TIMEFRAMES = {
    "15m": 15 * 60,   # 15분 데이터는 10분마다 갱신
    "1h": 60 * 60,    # 1시간 데이터는 30분마다 갱신
    "4h": 120 * 60     # 4시간 데이터는 1시간마다 갱신
}
NEWS_CACHE_TTL = 3600  # 뉴스 캐시 유효 시간 (1시간)

# 시뮬레이션 모드 설정
SIM_CAPITAL = 10000    # 시뮬레이션 모드에서 사용할 가상 자본 (USDT)
MIN_ORDER_AMOUNT = 100 # 최소 주문 금액 (USDT)

# OpenAI 클라이언트 초기화 (OpenRouter용)
if not OPENROUTER_API_KEY:
    print("오류: OPENROUTER_API_KEY 환경 변수가 설정되지 않았습니다. 프로그램 실행 불가.")
    # 또는 적절한 에러 처리 / sys.exit()
    client = None
else:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        default_headers={
            "HTTP-Referer": OPENROUTER_REFERER,
            "X-Title": OPENROUTER_TITLE
        },
        timeout=30.0 # API 호출 타임아웃 설정 (초)
    )

# 상태 메시지 출력
print(f"Dry Run Mode: {'활성화됨 (실제 거래 없음)' if DRY_RUN else '비활성화됨 (실제 거래 실행)'}") 