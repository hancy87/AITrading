"""
유틸리티 함수 모듈
"""
import os
import json
import time
import logging
from datetime import datetime, timedelta
import traceback

def setup_logging(log_file='bitcoin_trading.log'):
    """
    로깅 설정
    
    매개변수:
        log_file (str): 로그 파일 경로
    """
    # 로깅 포맷 설정
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # 로거 설정
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 파일 핸들러 설정
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    logger.addHandler(file_handler)
    
    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    logger.addHandler(console_handler)
    
    return logger

def log_exception(e, context=''):
    """
    예외 로깅 헬퍼 함수
    
    매개변수:
        e (Exception): 발생한 예외
        context (str): 예외 발생 컨텍스트
    """
    error_msg = f"{context}: {str(e)}" if context else str(e)
    logging.error(error_msg)
    logging.debug(traceback.format_exc())

def format_price(price, decimal_places=2):
    """
    가격 형식화 함수
    
    매개변수:
        price (float): 형식화할 가격
        decimal_places (int): 소수점 자릿수
        
    반환값:
        str: 형식화된 가격 문자열
    """
    if price is None:
        return "N/A"
    return f"${price:,.{decimal_places}f}"

def calculate_percentage_change(old_value, new_value):
    """
    백분율 변화 계산
    
    매개변수:
        old_value (float): 이전 값
        new_value (float): 새 값
        
    반환값:
        float: 백분율 변화
    """
    if old_value == 0:
        return 0
    return ((new_value - old_value) / abs(old_value)) * 100

def time_since(timestamp):
    """
    주어진 타임스탬프로부터 경과 시간 계산
    
    매개변수:
        timestamp (float): 유닉스 타임스탬프 또는 ISO 형식 문자열
        
    반환값:
        str: 경과 시간 문자열
    """
    if isinstance(timestamp, str):
        # ISO 형식 문자열을 datetime으로 변환
        try:
            dt = datetime.fromisoformat(timestamp)
        except ValueError:
            return "Invalid timestamp format"
    else:
        # 유닉스 타임스탬프를 datetime으로 변환
        dt = datetime.fromtimestamp(timestamp)
    
    # 현재 시간과의 차이 계산
    delta = datetime.now() - dt
    
    # 경과 시간 형식화
    if delta.days > 0:
        return f"{delta.days}일 전"
    elif delta.seconds >= 3600:
        return f"{delta.seconds // 3600}시간 전"
    elif delta.seconds >= 60:
        return f"{delta.seconds // 60}분 전"
    else:
        return f"{delta.seconds}초 전"

def save_json(data, file_path):
    """
    데이터를 JSON 파일로 저장
    
    매개변수:
        data: 저장할 데이터
        file_path (str): 저장할 파일 경로
        
    반환값:
        bool: 성공 여부
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log_exception(e, f"JSON 저장 중 오류 ({file_path})")
        return False

def load_json(file_path):
    """
    JSON 파일에서 데이터 로드
    
    매개변수:
        file_path (str): 로드할 파일 경로
        
    반환값:
        dict/list: 로드된 데이터 또는 None (실패 시)
    """
    try:
        if not os.path.exists(file_path):
            return None
            
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log_exception(e, f"JSON 로드 중 오류 ({file_path})")
        return None

def retry_function(func, max_retries=3, retry_delay=5, *args, **kwargs):
    """
    함수 실행을 재시도하는 유틸리티
    
    매개변수:
        func: 실행할 함수
        max_retries (int): 최대 재시도 횟수
        retry_delay (int): 재시도 간 대기 시간(초)
        *args, **kwargs: 함수에 전달할 인자
        
    반환값:
        함수의 반환값 또는 None (모든 시도 실패 시)
    """
    retries = 0
    while retries < max_retries:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            retries += 1
            log_exception(e, f"함수 실행 실패 ({func.__name__}) - 시도 {retries}/{max_retries}")
            
            if retries < max_retries:
                # 재시도 전 대기
                time.sleep(retry_delay)
            else:
                # 모든 시도 실패
                logging.error(f"최대 재시도 횟수 초과: {func.__name__}")
                return None

def format_trade_summary(trade_data):
    """
    거래 데이터를 읽기 쉬운 요약으로 형식화
    
    매개변수:
        trade_data (dict): 거래 데이터
        
    반환값:
        str: 형식화된 거래 요약
    """
    if not trade_data:
        return "거래 데이터 없음"
    
    action = trade_data.get('action', '').upper()
    entry_price = trade_data.get('entry_price', 0)
    exit_price = trade_data.get('exit_price')
    leverage = trade_data.get('leverage', 1)
    status = trade_data.get('status', 'UNKNOWN')
    profit_loss_pct = trade_data.get('profit_loss_percentage')
    
    summary = f"{action} 포지션 (레버리지: {leverage}x)\n"
    summary += f"진입: {format_price(entry_price)}"
    
    if exit_price and status == 'CLOSED':
        summary += f" → 청산: {format_price(exit_price)}\n"
        
        if profit_loss_pct is not None:
            result = "이익" if profit_loss_pct > 0 else "손실"
            summary += f"결과: {result} ({profit_loss_pct:.2f}%)"
    else:
        summary += f"\n상태: {status}"
        
        # 스탑로스/테이크프로핏 정보 추가
        sl_price = trade_data.get('sl_price')
        tp_price = trade_data.get('tp_price')
        
        if sl_price:
            summary += f"\n스탑로스: {format_price(sl_price)}"
        if tp_price:
            summary += f"\n테이크프로핏: {format_price(tp_price)}"
    
    return summary

def parse_timeframe(timeframe_str):
    """
    타임프레임 문자열 파싱
    
    매개변수:
        timeframe_str (str): 타임프레임 문자열 (예: '15m', '1h', '4h', '1d')
        
    반환값:
        timedelta: 해당 타임프레임의 timedelta 객체
    """
    if not timeframe_str:
        return timedelta(minutes=15)  # 기본값
    
    # 숫자 부분과 단위 부분 분리
    amount = ""
    unit = ""
    
    for char in timeframe_str:
        if char.isdigit():
            amount += char
        else:
            unit += char
    
    if not amount:
        amount = '1'
    
    amount = int(amount)
    
    # 단위별 timedelta 반환
    if unit == 'm':
        return timedelta(minutes=amount)
    elif unit == 'h':
        return timedelta(hours=amount)
    elif unit == 'd':
        return timedelta(days=amount)
    elif unit == 'w':
        return timedelta(weeks=amount)
    else:
        # 기본값
        return timedelta(minutes=15)

def wait_until_next_cycle(cycle_time_seconds, start_time=None, max_sleep=None):
    """
    다음 사이클 시작 시간까지 대기
    
    매개변수:
        cycle_time_seconds (int): 사이클 시간(초)
        start_time (float, optional): 사이클 시작 시간 (None이면 현재 시간 사용)
        max_sleep (int, optional): 최대 대기 시간(초) (None이면 제한 없음)
    """
    if start_time is None:
        start_time = time.time()
    
    elapsed = time.time() - start_time
    wait_time = cycle_time_seconds - (elapsed % cycle_time_seconds)
    
    # 최대 대기 시간 제한 적용
    if max_sleep is not None:
        wait_time = min(wait_time, max_sleep)
    
    if wait_time > 0:
        print(f"다음 사이클까지 {wait_time:.1f}초 대기")
        time.sleep(wait_time)
        
def print_status_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█'):
    """
    진행 상태 표시줄 출력
    
    매개변수:
        iteration (int): 현재 반복 인덱스
        total (int): 전체 반복 횟수
        prefix (str): 접두사 문자열
        suffix (str): 접미사 문자열
        decimals (int): 백분율 소수점 자릿수
        length (int): 진행 표시줄 길이
        fill (str): 진행 표시줄 채우기 문자
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='\r')
    
    # 완료 시 줄바꿈
    if iteration == total:
        print()

def human_readable_size(size_bytes):
    """
    바이트 크기를 사람이 읽기 쉬운 형식으로 변환
    
    매개변수:
        size_bytes (int): 바이트 단위 크기
        
    반환값:
        str: 사람이 읽기 쉬운 형식의 크기
    """
    if size_bytes == 0:
        return "0B"
    
    size_names = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
        
    return f"{size_bytes:.2f} {size_names[i]}" 