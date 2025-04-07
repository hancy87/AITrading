"""
거래 실행 및 포지션 관리 모듈
"""
import time
import math
from datetime import datetime
import traceback
from config import SYMBOL, DRY_RUN, SIM_CAPITAL, MIN_ORDER_AMOUNT
from database import save_trade, update_trade_status, get_latest_open_trade

class Trader:
    """
    거래 실행 및 포지션 관리 기능을 제공하는 클래스
    """
    def __init__(self, exchange):
        """
        Trader 클래스 초기화
        
        매개변수:
            exchange: 초기화된 거래소 객체
        """
        self.exchange = exchange
        self.dry_run = DRY_RUN
        self.sim_balance = SIM_CAPITAL  # 시뮬레이션 모드에서 사용할 가상 자본
        self.min_order_amount = MIN_ORDER_AMOUNT
    
    def get_account_balance(self):
        """
        계좌 잔액 조회
        
        반환값:
            float: 현재 USDT 잔액
        """
        if self.dry_run:
            return self.sim_balance
        
        try:
            # 바이낸스 선물 계좌 잔액 조회
            balance = self.exchange.fetch_balance()
            return balance['USDT']['free']
        except Exception as e:
            print(f"계좌 잔액 조회 중 오류: {e}")
            return 0
    
    def open_position(self, direction, entry_price, position_size_percentage, leverage, sl_percentage, tp_percentage):
        """
        새로운 포지션 생성
        
        매개변수:
            direction (str): 포지션 방향 ('LONG' 또는 'SHORT')
            entry_price (float): 진입 가격
            position_size_percentage (float): 자본 대비 포지션 크기 비율 (0.1-1.0)
            leverage (int): 레버리지 (1-5)
            sl_percentage (float): 스탑로스 비율
            tp_percentage (float): 테이크프로핏 비율
            
        반환값:
            dict: 생성된 거래 정보
        """
        try:
            # 현재 열린 포지션이 있는지 확인
            current_position = get_latest_open_trade()
            if current_position:
                print(f"이미 열린 포지션이 있습니다: {current_position['action']} (ID: {current_position['id']})")
                return None
            
            # 계좌 잔액 조회
            account_balance = self.get_account_balance()
            
            if account_balance < self.min_order_amount:
                print(f"잔액이 부족합니다. 최소 주문 금액: {self.min_order_amount} USDT, 현재 잔액: {account_balance} USDT")
                return None
            
            # 주문 금액 계산
            investment_amount = account_balance * position_size_percentage
            investment_amount = max(self.min_order_amount, min(investment_amount, account_balance * 0.95))
            
            # 주문 수량 계산 (BTC)
            amount = investment_amount / entry_price
            
            # 주문 방향 설정
            side = 'buy' if direction == 'LONG' else 'sell'
            
            # 스탑로스 및 테이크프로핏 가격 계산
            if direction == 'LONG':
                sl_price = entry_price * (1 - sl_percentage / 100)
                tp_price = entry_price * (1 + tp_percentage / 100)
            else:
                sl_price = entry_price * (1 + sl_percentage / 100)
                tp_price = entry_price * (1 - tp_percentage / 100)
            
            # 실제 주문 실행 (Dry Run 모드가 아닌 경우)
            order_id = None
            if not self.dry_run:
                # 레버리지 설정
                self.exchange.fapiPrivate_post_leverage({
                    'symbol': SYMBOL.replace('/', ''),
                    'leverage': leverage
                })
                
                # 주문 실행
                order = self.exchange.create_order(
                    symbol=SYMBOL,
                    type='market',
                    side=side,
                    amount=amount,
                    params={}
                )
                
                order_id = order['id']
                print(f"주문 실행 완료: {side.upper()} {amount} BTC 가격: ${entry_price}")
            else:
                print(f"[DRY RUN] {side.upper()} {amount:.8f} BTC 가격: ${entry_price:.2f} " +
                      f"(레버리지: {leverage}x, 투자금: ${investment_amount:.2f})")
            
            # 거래 정보 저장
            trade_data = {
                'action': direction.lower(),  # 'long' 또는 'short'
                'entry_price': entry_price,
                'amount': amount,
                'leverage': leverage,
                'sl_price': sl_price,
                'tp_price': tp_price,
                'sl_percentage': sl_percentage,
                'tp_percentage': tp_percentage,
                'position_size_percentage': position_size_percentage,
                'investment_amount': investment_amount
            }
            
            # 데이터베이스에 저장
            trade_id = save_trade(trade_data)
            
            if trade_id:
                trade_data['id'] = trade_id
                print(f"새 포지션이 생성되었습니다. ID: {trade_id}")
                
                # Dry Run 모드에서는 시뮬레이션 잔액 업데이트
                if self.dry_run:
                    self.sim_balance -= investment_amount
                
                return trade_data
            else:
                print("포지션 정보 저장에 실패했습니다.")
                return None
        except Exception as e:
            print(f"포지션 생성 중 오류: {e}")
            traceback.print_exc()
            return None
    
    def close_position(self, trade_id, exit_price):
        """
        기존 포지션 청산
        
        매개변수:
            trade_id (int): 청산할 거래 ID
            exit_price (float): 청산 가격
            
        반환값:
            bool: 성공 여부
        """
        try:
            # 현재 포지션 정보 가져오기
            position = get_latest_open_trade()
            
            if not position or position['id'] != trade_id:
                print(f"청산할 포지션을 찾을 수 없습니다: {trade_id}")
                return False
            
            action = position['action']  # 'long' 또는 'short'
            entry_price = position['entry_price']
            amount = position['amount']
            leverage = position['leverage']
            
            # 청산 방향 설정 (진입 방향의 반대)
            side = 'sell' if action == 'long' else 'buy'
            
            # 수익률 계산
            if action == 'long':
                profit_percentage = (exit_price - entry_price) / entry_price * 100 * leverage
            else:
                profit_percentage = (entry_price - exit_price) / entry_price * 100 * leverage
            
            # 실제 수익금 계산
            investment_amount = entry_price * amount
            profit_loss = investment_amount * profit_percentage / 100
            
            # 실제 청산 실행 (Dry Run 모드가 아닌 경우)
            if not self.dry_run:
                try:
                    order = self.exchange.create_order(
                        symbol=SYMBOL,
                        type='market',
                        side=side,
                        amount=amount,
                        params={}
                    )
                    
                    print(f"포지션 청산 완료: {side.upper()} {amount} BTC 가격: ${exit_price}")
                except Exception as e:
                    print(f"포지션 청산 중 오류: {e}")
                    return False
            else:
                print(f"[DRY RUN] 포지션 청산: {side.upper()} {amount:.8f} BTC 가격: ${exit_price:.2f}")
                print(f"[DRY RUN] 결과: {'이익' if profit_percentage > 0 else '손실'} " +
                      f"({profit_percentage:.2f}%, ${profit_loss:.2f})")
                
                # 시뮬레이션 잔액 업데이트
                self.sim_balance += investment_amount + profit_loss
            
            # 거래 상태 업데이트
            update_trade_status(
                trade_id=trade_id,
                status='CLOSED',
                exit_price=exit_price,
                exit_timestamp=datetime.now().isoformat(),
                profit_loss=profit_loss,
                profit_loss_percentage=profit_percentage
            )
            
            print(f"포지션이 청산되었습니다. ID: {trade_id}")
            print(f"손익: {'이익' if profit_percentage > 0 else '손실'} ({profit_percentage:.2f}%)")
            
            return True
        except Exception as e:
            print(f"포지션 청산 중 오류: {e}")
            traceback.print_exc()
            return False
    
    def check_stop_loss_take_profit(self, current_price):
        """
        현재 포지션의 스탑로스 및 테이크프로핏 조건 확인
        
        매개변수:
            current_price (float): 현재 가격
            
        반환값:
            tuple: (bool, str) - (청산 여부, 청산 이유)
        """
        try:
            # 현재 열린 포지션 확인
            position = get_latest_open_trade()
            
            if not position:
                return False, "열린 포지션 없음"
            
            trade_id = position['id']
            action = position['action']
            entry_price = position['entry_price']
            sl_price = position['sl_price']
            tp_price = position['tp_price']
            
            # 스탑로스 확인
            sl_triggered = False
            if action == 'long' and current_price <= sl_price:
                sl_triggered = True
            elif action == 'short' and current_price >= sl_price:
                sl_triggered = True
                
            if sl_triggered:
                print(f"스탑로스 발동: {current_price} (설정: {sl_price})")
                if self.close_position(trade_id, current_price):
                    return True, "스탑로스"
            
            # 테이크프로핏 확인
            tp_triggered = False
            if action == 'long' and current_price >= tp_price:
                tp_triggered = True
            elif action == 'short' and current_price <= tp_price:
                tp_triggered = True
                
            if tp_triggered:
                print(f"테이크프로핏 발동: {current_price} (설정: {tp_price})")
                if self.close_position(trade_id, current_price):
                    return True, "테이크프로핏"
            
            return False, "조건 미충족"
        except Exception as e:
            print(f"스탑로스/테이크프로핏 확인 중 오류: {e}")
            return False, f"오류: {str(e)}"
    
    def execute_trade_decision(self, analysis_result, current_price):
        """
        AI 분석 결과를 바탕으로 거래 실행
        
        매개변수:
            analysis_result (dict): AI 분석 결과
            current_price (float): 현재 가격
            
        반환값:
            dict: 거래 실행 결과
        """
        if not analysis_result:
            print("거래 결정을 위한 분석 결과가 없습니다.")
            return None
        
        try:
            direction = analysis_result.get('direction', 'NO_POSITION')
            
            # 현재 열린 포지션 확인
            current_position = get_latest_open_trade()
            
            # 포지션 진입 결정 (NO_POSITION이 아니고 열린 포지션이 없는 경우)
            if direction != 'NO_POSITION' and not current_position:
                print(f"새 {direction} 포지션 진입 결정")
                
                # 거래 실행
                position_size = analysis_result.get('recommended_position_size', 0.1)
                leverage = analysis_result.get('recommended_leverage', 1)
                sl_percentage = analysis_result.get('stop_loss_percentage', 1.0)
                tp_percentage = analysis_result.get('take_profit_percentage', 2.0)
                
                trade_result = self.open_position(
                    direction=direction,
                    entry_price=current_price,
                    position_size_percentage=position_size,
                    leverage=leverage,
                    sl_percentage=sl_percentage,
                    tp_percentage=tp_percentage
                )
                
                return {
                    'action': 'OPEN',
                    'direction': direction,
                    'price': current_price,
                    'trade_id': trade_result.get('id') if trade_result else None,
                    'result': 'SUCCESS' if trade_result else 'FAILED'
                }
            
            # 포지션 청산 결정 (NO_POSITION이고 열린 포지션이 있는 경우)
            elif direction == 'NO_POSITION' and current_position:
                print("기존 포지션 청산 결정")
                
                # 청산 실행
                close_successful = self.close_position(current_position['id'], current_price)
                
                return {
                    'action': 'CLOSE',
                    'trade_id': current_position['id'],
                    'price': current_price,
                    'result': 'SUCCESS' if close_successful else 'FAILED'
                }
            
            # 그 외 경우 (포지션 유지)
            else:
                if current_position:
                    action_str = "기존 포지션 유지"
                else:
                    action_str = "포지션 진입 없음"
                    
                print(f"{action_str} (추천: {direction})")
                
                return {
                    'action': 'HOLD',
                    'direction': direction,
                    'price': current_price,
                    'result': 'SUCCESS'
                }
        except Exception as e:
            print(f"거래 실행 중 오류: {e}")
            traceback.print_exc()
            return {
                'action': 'ERROR',
                'error': str(e),
                'result': 'FAILED'
            } 