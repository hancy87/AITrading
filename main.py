"""
비트코인 트레이딩 봇 메인 모듈
"""
import sys
import time
import signal
import traceback
from datetime import datetime

from config import MAIN_LOOP_INTERVAL, PRICE_CHECK_INTERVAL, POSITION_CHECK_INTERVAL
from database import setup_database, get_latest_open_trade
from data_collector import create_exchange, get_current_price, get_full_market_analysis
from analyzer import process_ai_analysis, save_analysis_to_db, evaluate_trading_decision
from trader import Trader
from utils import setup_logging, wait_until_next_cycle, time_since

# 전역 변수
running = True
logger = None
trader = None
exchange = None

# 마지막 분석 시간 추적
last_analysis_time = 0

def signal_handler(sig, frame):
    """
    시그널 핸들러 (Ctrl+C 등)
    """
    global running
    print("\n프로그램 종료 중...")
    running = False

def setup():
    """
    프로그램 초기 설정
    """
    global logger, trader, exchange
    
    # 로깅 설정
    logger = setup_logging()
    logger.info("비트코인 트레이딩 봇 시작")
    
    # 데이터베이스 설정
    setup_database()
    
    # 거래소 객체 생성
    exchange = create_exchange()
    if not exchange:
        logger.error("거래소 객체 생성 실패, 프로그램을 종료합니다.")
        sys.exit(1)
    
    # 트레이더 객체 생성
    trader = Trader(exchange)
    
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def check_position(current_price):
    """
    현재 포지션 확인 및 스탑로스/테이크프로핏 처리
    
    매개변수:
        current_price (float): 현재 가격
        
    반환값:
        bool: 포지션 상태 변경 여부
    """
    # 현재 열린 포지션이 있는지 확인
    position = get_latest_open_trade()
    
    if not position:
        return False
    
    # 스탑로스/테이크프로핏 확인
    closed, reason = trader.check_stop_loss_take_profit(current_price)
    
    if closed:
        logger.info(f"포지션 청산됨: {reason}")
        return True
    
    return False

def run_trading_logic():
    """
    메인 트레이딩 로직 실행
    """
    global last_analysis_time
    
    # 현재 가격 조회
    current_price = get_current_price(exchange)
    if not current_price:
        logger.error("가격 조회 실패")
        return
    
    # 포지션 확인 주기
    position_check_due = time.time() - last_analysis_time >= POSITION_CHECK_INTERVAL
    
    # 현재 포지션 스탑로스/테이크프로핏 확인
    if position_check_due:
        position_changed = check_position(current_price)
        
        # 포지션이 변경된 경우 즉시 새 분석 수행
        if position_changed:
            last_analysis_time = 0
    
    # 상세 분석 주기 (마지막 분석 후 일정 시간이 지났을 때만)
    analysis_due = time.time() - last_analysis_time >= MAIN_LOOP_INTERVAL
    
    if analysis_due:
        logger.info(f"현재 BTC/USDT 가격: ${current_price:,.2f}")
        
        try:
            # 상세 시장 분석 수행
            logger.info("시장 분석 수행 중...")
            market_analysis = get_full_market_analysis(exchange)
            
            if market_analysis:
                # AI 분석 수행
                logger.info("AI 분석 요청 중...")
                analysis_result = process_ai_analysis(market_analysis)
                
                if analysis_result:
                    # 분석 결과 데이터베이스에 저장
                    analysis_id = save_analysis_to_db(analysis_result)
                    
                    # 거래 결정 평가 및 표시
                    decision_summary = evaluate_trading_decision(analysis_result)
                    logger.info(f"AI 거래 결정: {decision_summary}")
                    
                    # 거래 실행
                    trade_result = trader.execute_trade_decision(analysis_result, current_price)
                    
                    if trade_result:
                        action = trade_result.get('action')
                        result = trade_result.get('result')
                        logger.info(f"거래 실행 결과: {action} - {result}")
                else:
                    logger.warning("AI 분석을 완료할 수 없습니다.")
            else:
                logger.warning("시장 분석을 완료할 수 없습니다.")
        except Exception as e:
            logger.error(f"트레이딩 로직 실행 중 오류: {e}")
            traceback.print_exc()
        finally:
            # 분석 시간 업데이트
            last_analysis_time = time.time()
    else:
        # 단순 가격 체크만 수행 (상세 분석 없이)
        open_position = get_latest_open_trade()
        if open_position:
            action = open_position.get('action', '').upper()
            entry_price = open_position.get('entry_price', 0)
            pct_change = ((current_price - entry_price) / entry_price) * 100
            direction = '+' if pct_change > 0 else ''
            
            logger.info(f"현재 가격: ${current_price:,.2f} ({direction}{pct_change:.2f}% from entry)")
            
            # 스탑로스/테이크프로핏 확인
            check_position(current_price)

def main():
    """
    메인 실행 함수
    """
    setup()
    
    # 메인 루프
    while running:
        cycle_start_time = time.time()
        
        try:
            run_trading_logic()
        except Exception as e:
            logger.error(f"메인 루프 실행 중 오류: {e}")
            traceback.print_exc()
        
        # 다음 사이클까지 대기
        if running:
            wait_until_next_cycle(PRICE_CHECK_INTERVAL, cycle_start_time)
    
    logger.info("프로그램 종료")

if __name__ == "__main__":
    main() 