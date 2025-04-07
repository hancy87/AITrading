"""
시장 데이터 수집 모듈
"""
import os
import requests
import json
import time
import ccxt
from datetime import datetime, timedelta
from config import SYMBOL, BINANCE_API_KEY, BINANCE_SECRET_KEY, SERP_API_KEY
from config import CACHE_TIMEFRAMES, NEWS_CACHE_TTL

# 캐시 데이터 저장소
_cache = {
    "charts": {},      # 차트 데이터 캐시
    "news": {          # 뉴스 데이터 캐시
        "data": None,
        "timestamp": 0
    },
    "price": {         # 가격 데이터 캐시
        "data": None,
        "timestamp": 0
    }
}

def create_exchange():
    """
    CCXT를 사용하여 바이낸스 거래소 객체 생성
    
    반환값:
        exchange: 초기화된 바이낸스 거래소 객체
    """
    try:
        exchange = ccxt.binance({
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_SECRET_KEY,
            'enableRateLimit': True,  # API 속도 제한 준수
            'options': {
                'defaultType': 'future',  # 선물 거래 사용
            }
        })
        return exchange
    except Exception as e:
        print(f"거래소 객체 생성 중 오류: {e}")
        return None

def get_current_price(exchange):
    """
    현재 가격 조회
    
    매개변수:
        exchange: 초기화된 거래소 객체
        
    반환값:
        float: 현재 가격
    """
    # 캐시 확인 (5초 이내 데이터는 재사용)
    cache_age = time.time() - _cache["price"]["timestamp"]
    if _cache["price"]["data"] and cache_age < 5:
        return _cache["price"]["data"]
        
    try:
        ticker = exchange.fetch_ticker(SYMBOL)
        current_price = ticker['last']
        
        # 캐시 업데이트
        _cache["price"]["data"] = current_price
        _cache["price"]["timestamp"] = time.time()
        
        return current_price
    except Exception as e:
        print(f"가격 조회 중 오류: {e}")
        # 캐시된 데이터라도 반환
        if _cache["price"]["data"]:
            print("이전 캐시 데이터를 사용합니다.")
            return _cache["price"]["data"]
        return None

def fetch_ohlcv_data(exchange, timeframe, limit=100):
    """
    특정 타임프레임의 OHLCV(Open, High, Low, Close, Volume) 데이터 조회
    
    매개변수:
        exchange: 초기화된 거래소 객체
        timeframe: 타임프레임(예: '15m', '1h', '4h', '1d')
        limit: 요청할 캔들 수
        
    반환값:
        list: OHLCV 데이터 리스트
    """
    cache_key = f"{timeframe}_{limit}"
    
    # 캐시 확인
    if cache_key in _cache["charts"]:
        cache_entry = _cache["charts"][cache_key]
        cache_age = time.time() - cache_entry["timestamp"]
        ttl = CACHE_TIMEFRAMES.get(timeframe, 5 * 60)  # 기본 TTL은 5분
        
        if cache_age < ttl:
            return cache_entry["data"]
    
    try:
        # OHLCV 데이터 조회
        ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe, limit=limit)
        
        # 데이터 정리 및 가공
        processed_data = []
        for candle in ohlcv:
            timestamp, open_price, high, low, close, volume = candle
            processed_data.append({
                'timestamp': timestamp,
                'datetime': datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S'),
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
        
        # 캐시 업데이트
        _cache["charts"][cache_key] = {
            "data": processed_data,
            "timestamp": time.time()
        }
        
        return processed_data
    except Exception as e:
        print(f"{timeframe} 차트 데이터 조회 중 오류: {e}")
        
        # 캐시된 데이터가 있으면 반환
        if cache_key in _cache["charts"]:
            print(f"이전 {timeframe} 캐시 데이터를 사용합니다.")
            return _cache["charts"][cache_key]["data"]
        return []

def get_market_data(exchange):
    """
    거래 분석에 필요한 전체 시장 데이터 조회
    
    매개변수:
        exchange: 초기화된 거래소 객체
        
    반환값:
        dict: 다양한 타임프레임을 포함한 시장 데이터
    """
    try:
        # 현재 가격 조회
        current_price = get_current_price(exchange)
        
        # 다양한 타임프레임의 데이터 조회
        ohlcv_15m = fetch_ohlcv_data(exchange, '15m', 96)   # 24시간치 (15분 * 96)
        ohlcv_1h = fetch_ohlcv_data(exchange, '1h', 72)     # 3일치 (1시간 * 72)
        ohlcv_4h = fetch_ohlcv_data(exchange, '4h', 42)     # 1주일치 (4시간 * 42)
        
        # 뉴스 데이터 조회
        news_data = get_crypto_news()
        
        # 시장 데이터 종합
        market_data = {
            'current_price': current_price,
            'timeframes': {
                '15m': ohlcv_15m,
                '1h': ohlcv_1h,
                '4h': ohlcv_4h
            },
            'news': news_data
        }
        
        return market_data
    except Exception as e:
        print(f"시장 데이터 조회 중 오류: {e}")
        return None

def get_crypto_news(max_results=10):
    """
    암호화폐 관련 최신 뉴스 조회
    
    매개변수:
        max_results: 조회할 최대 뉴스 수
        
    반환값:
        list: 뉴스 기사 목록
    """
    # 캐시 확인
    cache_age = time.time() - _cache["news"]["timestamp"]
    if _cache["news"]["data"] and cache_age < NEWS_CACHE_TTL:
        return _cache["news"]["data"][:max_results]
    
    # API 키가 없으면 빈 리스트 반환
    if not SERP_API_KEY:
        print("SERP API 키가 설정되지 않아 뉴스 데이터를 가져올 수 없습니다.")
        return []
    
    try:
        # API 호출 파라미터 설정
        params = {
            'engine': 'google_news',
            'q': 'Bitcoin cryptocurrency market',
            'tbm': 'nws',
            'api_key': SERP_API_KEY,
            'num': max_results
        }
        
        # API 호출
        api_result = requests.get('https://serpapi.com/search', params=params)
        
        if api_result.status_code != 200:
            print(f"뉴스 API 오류: {api_result.status_code}")
            # 캐시된 데이터가 있으면 반환
            if _cache["news"]["data"]:
                return _cache["news"]["data"][:max_results]
            return []
        
        search_results = api_result.json()
        news_results = []
        
        # 뉴스 결과 파싱
        if 'news_results' in search_results:
            for item in search_results['news_results'][:max_results]:
                news_results.append({
                    'title': item.get('title', ''),
                    'link': item.get('link', ''),
                    'source': item.get('source', ''),
                    'date': item.get('date', ''),
                    'snippet': item.get('snippet', '')
                })
        
        # 캐시 업데이트
        _cache["news"]["data"] = news_results
        _cache["news"]["timestamp"] = time.time()
        
        return news_results
    except Exception as e:
        print(f"뉴스 데이터 조회 중 오류: {e}")
        # 캐시된 데이터가 있으면 반환
        if _cache["news"]["data"]:
            return _cache["news"]["data"][:max_results]
        return []

def calculate_technical_indicators(price_data):
    """
    기술적 지표 계산
    
    매개변수:
        price_data: 가격 데이터 목록
        
    반환값:
        dict: 계산된 기술적 지표
    """
    if not price_data or len(price_data) < 21:
        return {}
    
    # 종가 추출
    closes = [candle['close'] for candle in price_data]
    
    # 간단한 이동평균(SMA) 계산
    sma7 = sum(closes[-7:]) / 7
    sma21 = sum(closes[-21:]) / 21
    
    # 볼린저 밴드 계산 (20일 기준)
    sma20 = sum(closes[-20:]) / 20
    variance = sum((close - sma20) ** 2 for close in closes[-20:]) / 20
    std_dev = variance ** 0.5
    upper_band = sma20 + (2 * std_dev)
    lower_band = sma20 - (2 * std_dev)
    
    # RSI 계산 (14일 기준)
    rsi = calculate_rsi(closes, 14)
    
    # MACD 계산
    ema12 = calculate_ema(closes, 12)
    ema26 = calculate_ema(closes, 26)
    macd = ema12 - ema26
    signal_line = calculate_ema([macd] if isinstance(macd, (int, float)) else macd, 9)
    
    # 현재 가격
    current_price = closes[-1]
    
    return {
        'current_price': current_price,
        'sma7': sma7,
        'sma21': sma21,
        'bollinger': {
            'upper': upper_band,
            'middle': sma20,
            'lower': lower_band
        },
        'rsi': rsi,
        'macd': {
            'macd': macd,
            'signal': signal_line,
            'histogram': macd - signal_line
        },
        'sma_trend': 'bullish' if sma7 > sma21 else 'bearish',
        'price_to_sma': {
            'above_sma7': current_price > sma7,
            'above_sma21': current_price > sma21,
        },
        'bollinger_position': 'upper' if current_price > upper_band else ('lower' if current_price < lower_band else 'middle'),
        'rsi_zone': 'overbought' if rsi > 70 else ('oversold' if rsi < 30 else 'neutral')
    }

def calculate_rsi(closes, period=14):
    """
    RSI(Relative Strength Index) 계산
    
    매개변수:
        closes: 종가 목록
        period: RSI 계산 기간
        
    반환값:
        float: RSI 값
    """
    if len(closes) <= period:
        return 50  # 데이터 부족 시 중립값 반환
    
    # 가격 변화량 계산
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    
    # 상승 및 하락 구분
    gains = [delta if delta > 0 else 0 for delta in deltas]
    losses = [-delta if delta < 0 else 0 for delta in deltas]
    
    # 첫 평균 게인과 평균 로스 계산
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100  # 손실이 없으면 RSI = 100
    
    # RS(Relative Strength) 및 RSI 계산
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def calculate_ema(prices, period):
    """
    EMA(Exponential Moving Average) 계산
    
    매개변수:
        prices: 가격 목록
        period: EMA 계산 기간
        
    반환값:
        float: EMA 값
    """
    if not prices or len(prices) < period:
        return prices[-1] if prices else 0
    
    # 가중치 계산
    multiplier = 2 / (period + 1)
    
    # 첫 SMA 계산
    ema = sum(prices[-period:]) / period
    
    # EMA 계산
    for price in reversed(prices[:-period]):
        ema = (price * multiplier) + (ema * (1 - multiplier))
    
    return ema

def analyze_price_action(price_data):
    """
    가격 행동 분석
    
    매개변수:
        price_data: 가격 데이터 목록
        
    반환값:
        dict: 가격 행동 분석 결과
    """
    if not price_data or len(price_data) < 3:
        return {'trend': 'unknown', 'volatility': 'unknown'}
    
    # 최근 캔들 추출
    recent_candles = price_data[-10:]
    current_candle = price_data[-1]
    previous_candle = price_data[-2]
    
    # 캔들 바디 크기 계산
    body_sizes = []
    for candle in recent_candles:
        body_size = abs(candle['close'] - candle['open']) / candle['open'] * 100
        body_sizes.append(body_size)
    
    avg_body_size = sum(body_sizes) / len(body_sizes)
    
    # 현재 캔들 방향
    current_direction = 'bullish' if current_candle['close'] > current_candle['open'] else 'bearish'
    
    # 가격 변동성 계산
    highs = [candle['high'] for candle in recent_candles]
    lows = [candle['low'] for candle in recent_candles]
    volatility = (max(highs) - min(lows)) / min(lows) * 100
    
    # 추세 판단
    closes = [candle['close'] for candle in recent_candles]
    trend = 'sideways'
    
    if closes[-1] > closes[0] and min(closes) > closes[0] * 0.98:
        trend = 'uptrend'
    elif closes[-1] < closes[0] and max(closes) < closes[0] * 1.02:
        trend = 'downtrend'
    
    # 특수 캔들 패턴 확인
    patterns = []
    
    # 도지 패턴 (몸통이 매우 작음)
    current_body_size = body_sizes[-1]
    if current_body_size < avg_body_size * 0.3:
        patterns.append('doji')
    
    # 망치/역망치 패턴
    body = abs(current_candle['close'] - current_candle['open'])
    if current_direction == 'bullish':
        upper_shadow = current_candle['high'] - current_candle['close']
        lower_shadow = current_candle['open'] - current_candle['low']
    else:
        upper_shadow = current_candle['high'] - current_candle['open']
        lower_shadow = current_candle['close'] - current_candle['low']
    
    if lower_shadow > body * 2 and upper_shadow < body * 0.5:
        patterns.append('hammer')
    elif upper_shadow > body * 2 and lower_shadow < body * 0.5:
        patterns.append('inverted_hammer')
    
    # 결과 반환
    return {
        'trend': trend,
        'volatility': 'high' if volatility > 5 else ('medium' if volatility > 2 else 'low'),
        'current_direction': current_direction,
        'patterns': patterns,
        'avg_body_size': avg_body_size,
        'volatility_percentage': volatility
    }

def get_full_market_analysis(exchange):
    """
    시장 데이터를 가져와 종합적인 분석 수행
    
    매개변수:
        exchange: 초기화된 거래소 객체
        
    반환값:
        dict: 시장 데이터와 분석 결과
    """
    try:
        # 기본 시장 데이터 조회
        market_data = get_market_data(exchange)
        if not market_data:
            return None
        
        # 여러 타임프레임에 대한 기술적 지표 분석
        technical_indicators = {}
        price_action = {}
        
        for timeframe, data in market_data['timeframes'].items():
            if data:
                technical_indicators[timeframe] = calculate_technical_indicators(data)
                price_action[timeframe] = analyze_price_action(data)
        
        # 분석 결과 종합
        analysis_result = {
            'timestamp': datetime.now().isoformat(),
            'current_price': market_data['current_price'],
            'technical_indicators': technical_indicators,
            'price_action': price_action,
            'news': market_data['news'],
            'raw_data': {
                'timeframes': market_data['timeframes']
            }
        }
        
        return analysis_result
    except Exception as e:
        print(f"시장 분석 중 오류 발생: {e}")
        return None 