"""
AI 분석 및 거래 결정 모듈
"""
import json
import time
from datetime import datetime
import traceback
from config import client, OPENROUTER_MODEL, MAX_API_RETRIES, MAX_REASONING_LENGTH
from database import save_ai_analysis, get_performance_metrics, get_historical_trading_data

def process_ai_analysis(market_analysis):
    """
    시장 데이터를 기반으로 AI 분석을 수행하고 거래 결정 생성
    
    매개변수:
        market_analysis (dict): 시장 데이터 및 분석 결과
        
    반환값:
        dict: AI 분석 결과 및 거래 추천 데이터
    """
    if not market_analysis:
        print("시장 분석 데이터가 없어 AI 분석을 진행할 수 없습니다.")
        return None
    
    # 트레이딩 성과 지표 조회
    performance = get_performance_metrics()
    
    # 최근 거래 내역 가져오기
    trading_history = get_historical_trading_data(limit=5)
    
    # 현재 가격 가져오기
    current_price = market_analysis.get('current_price', 0)
    
    # ===== AI 분석 시작 =====
    try:
        # 시스템 프롬프트 구성
        system_prompt = """당신은 비트코인 트레이딩 전문가입니다. 
시장 데이터와 기술적 지표를 분석하여 최선의 거래 결정을 내려야 합니다.
다음 가이드라인에 따라 분석을 수행하세요:

1. 여러 타임프레임(15분, 1시간, 4시간)의 데이터를 종합적으로 분석하세요.
2. 기술적 지표(RSI, 볼린저 밴드, 이동평균선, MACD 등)를 검토하세요.
3. 가격 행동 패턴과 차트 형태를 분석하세요.
4. 최근 뉴스가 시장에 미치는 영향을 고려하세요.
5. 과거 거래 성과를 참고하여 전략을 조정하세요.
6. 리스크 관리를 최우선으로 하세요. 안전한 레버리지와 포지션 크기를 권장하세요.

당신은 다음 세 가지 결정 중 하나를 내려야 합니다:
- LONG: 상승 추세가 확실하고 매수 신호가 명확할 때
- SHORT: 하락 추세가 확실하고 매도 신호가 명확할 때
- NO_POSITION: 시장 방향이 불확실하거나 리스크가 높을 때

응답은 다음과 같은 JSON 형식으로 제공해 주세요:
{
  "direction": "LONG 또는 SHORT 또는 NO_POSITION",
  "recommended_position_size": 0.1-1.0 사이의 값 (자본 대비 비율),
  "recommended_leverage": 1-5 사이의 정수 (안전한 레버리지),
  "stop_loss_percentage": 스탑로스 비율 (소수점 두 자리),
  "take_profit_percentage": 테이크프로핏 비율 (소수점 두 자리),
  "reasoning": "결정에 대한 상세한 설명"
}

단순히 지표의 현재 상태만으로 결정하지 말고, 여러 시간대에 걸친 추세와 시장 심리를 종합적으로 분석하세요.
"""

        # 시장 데이터 요약 생성
        market_summary = create_market_summary(market_analysis, performance, trading_history)
        
        # AI 요청 메시지 구성
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": market_summary}
        ]
        
        # API 요청 (최대 재시도 횟수만큼)
        response = None
        error_messages = []
        
        for attempt in range(MAX_API_RETRIES):
            try:
                print(f"AI 분석 요청 중... (시도 {attempt+1}/{MAX_API_RETRIES})")
                
                # OpenRouter API 호출
                response = client.chat.completions.create(
                    model=OPENROUTER_MODEL,
                    messages=messages,
                    temperature=0.2,  # 낮은 온도로 일관된 응답 유도
                    max_tokens=100000,
                    response_format={"type": "json_object"}
                )
                
                break  # 성공 시 반복 중단
            except Exception as e:
                error_message = f"AI API 요청 오류 (시도 {attempt+1}): {str(e)}"
                print(error_message)
                error_messages.append(error_message)
                if attempt < MAX_API_RETRIES - 1:
                    time.sleep(10)  # 재시도 전 10초 대기
        
        # 응답이 없는 경우 또는 None인 경우
        if not response: # response가 None일 경우도 포함됨
            combined_errors = "; ".join(error_messages)
            print(f"최대 시도 횟수 초과 또는 유효한 API 응답 없음, AI 분석 실패: {combined_errors}")
            print(f"최종 response 객체: {response}") # response 객체 로깅 추가
            return None

        # 응답 객체가 None이 아닐 때만 아래 코드 실행
        print(f"수신된 response 객체: {response}") # 상세 로깅 추가
        try:
            # AI 응답 추출 및 처리
            ai_content = response.choices[0].message.content
            
            # AI 응답 JSON 파싱 전처리
            cleaned_json = clean_ai_response(ai_content)
            
            try:
                analysis_result = json.loads(cleaned_json)
                
                # 필수 필드 확인
                required_fields = ["direction", "recommended_position_size", "recommended_leverage", 
                                  "stop_loss_percentage", "take_profit_percentage", "reasoning"]
                
                for field in required_fields:
                    if field not in analysis_result:
                        print(f"AI 응답에 필수 필드가 누락되었습니다: {field}")
                        return None
                        
                # 값 정규화 및 유효성 검사
                analysis_result["direction"] = analysis_result["direction"].upper()
                if analysis_result["direction"] not in ["LONG", "SHORT", "NO_POSITION"]:
                    analysis_result["direction"] = "NO_POSITION"  # 기본값
                    
                # 포지션 크기 제한 (0.1 ~ 1.0)
                pos_size = float(analysis_result["recommended_position_size"])
                analysis_result["recommended_position_size"] = max(0.1, min(1.0, pos_size))
                
                # 레버리지 제한 (1 ~ 5)
                leverage = int(float(analysis_result["recommended_leverage"]))
                analysis_result["recommended_leverage"] = max(1, min(5, leverage))
                
                # 스탑로스, 테이크프로핏 백분율 (소수점으로 변환)
                sl_pct = float(analysis_result["stop_loss_percentage"])
                tp_pct = float(analysis_result["take_profit_percentage"])
                analysis_result["stop_loss_percentage"] = max(0.5, min(10.0, sl_pct))
                analysis_result["take_profit_percentage"] = max(1.0, min(20.0, tp_pct))
                
                # 추론 내용 길이 제한
                if len(analysis_result["reasoning"]) > MAX_REASONING_LENGTH:
                    analysis_result["reasoning"] = analysis_result["reasoning"][:MAX_REASONING_LENGTH] + "..."
                
                # 현재 가격 추가
                analysis_result["current_price"] = current_price
                
                return analysis_result
            except json.JSONDecodeError as e:
                print(f"AI 응답을 JSON으로 파싱할 수 없습니다: {e}")
                print(f"원본 응답: {ai_content}")
                print(f"정제된 응답: {cleaned_json}")
                return None
            except TypeError as te:
                print(f"응답 내용 접근 중 TypeError 발생: {te}")
                print(f"문제를 일으킨 response 객체: {response}") # 오류 발생 시 response 로깅
                return None
        except Exception as e:
            print(f"AI 응답 처리 중 오류 발생: {e}")
            traceback.print_exc()
            return None
    except Exception as e:
        print(f"AI 분석 과정에서 예외 발생: {e}")
        traceback.print_exc()
        return None

def clean_ai_response(response_text):
    """
    AI 응답에서 JSON 형식만 추출하고 코드 블록 등 필요없는 부분 제거
    
    매개변수:
        response_text (str): AI 응답 원문
        
    반환값:
        str: 정제된 JSON 문자열
    """
    try:
        # 코드 블록 제거
        if "```json" in response_text:
            # JSON 블록 추출
            start_idx = response_text.find("```json") + 7
            end_idx = response_text.find("```", start_idx)
            if end_idx > start_idx:
                return response_text[start_idx:end_idx].strip()
        
        if "```" in response_text:
            # 일반 코드 블록 추출
            start_idx = response_text.find("```") + 3
            end_idx = response_text.find("```", start_idx)
            if end_idx > start_idx:
                return response_text[start_idx:end_idx].strip()
        
        # 중괄호 안의 내용만 추출
        if "{" in response_text and "}" in response_text:
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            if end_idx > start_idx:
                return response_text[start_idx:end_idx].strip()
                
        # 그대로 반환
        return response_text.strip()
    except Exception as e:
        print(f"AI 응답 정제 중 오류: {e}")
        return response_text

def create_market_summary(market_analysis, performance_metrics, trading_history):
    """
    AI 분석을 위한 시장 데이터 요약 생성
    
    매개변수:
        market_analysis (dict): 시장 분석 데이터
        performance_metrics (dict): 거래 성과 지표
        trading_history (list): 과거 거래 내역
        
    반환값:
        str: 시장 요약 문자열
    """
    # 요약 시작
    summary = "## 현재 시장 정보\n"
    
    # 현재 가격 및 기본 정보
    current_price = market_analysis.get('current_price', 0)
    summary += f"현재 BTC/USDT 가격: ${current_price:,.2f}\n"
    summary += f"분석 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    # 기술적 지표 요약
    summary += "## 기술적 지표 분석\n"
    
    # 각 타임프레임별 지표 추가
    time_descriptions = {
        '15m': '15분 차트',
        '1h': '1시간 차트',
        '4h': '4시간 차트'
    }
    
    for timeframe, indicators in market_analysis.get('technical_indicators', {}).items():
        if not indicators:
            continue
        
        summary += f"### {time_descriptions.get(timeframe, timeframe)}\n"
        
        # RSI
        rsi = indicators.get('rsi', 0)
        rsi_zone = indicators.get('rsi_zone', 'neutral')
        summary += f"- RSI: {rsi:.2f} ({rsi_zone})\n"
        
        # 이동평균선
        sma7 = indicators.get('sma7', 0)
        sma21 = indicators.get('sma21', 0)
        sma_trend = indicators.get('sma_trend', '')
        summary += f"- SMA7: ${sma7:.2f}, SMA21: ${sma21:.2f} (추세: {sma_trend})\n"
        
        # 볼린저 밴드
        bollinger = indicators.get('bollinger', {})
        bollinger_position = indicators.get('bollinger_position', 'middle')
        summary += f"- 볼린저 밴드: 상단=${bollinger.get('upper', 0):.2f}, 중간=${bollinger.get('middle', 0):.2f}, 하단=${bollinger.get('lower', 0):.2f}\n"
        summary += f"- 현재 가격 위치: {bollinger_position}\n"
        
        # MACD
        macd_data = indicators.get('macd', {})
        macd = macd_data.get('macd', 0)
        signal = macd_data.get('signal', 0)
        histogram = macd_data.get('histogram', 0)
        summary += f"- MACD: {macd:.2f}, 시그널: {signal:.2f}, 히스토그램: {histogram:.2f}\n"
        
        summary += "\n"
    
    # 가격 행동 분석
    summary += "## 가격 행동 분석\n"
    
    for timeframe, price_action in market_analysis.get('price_action', {}).items():
        if not price_action:
            continue
            
        summary += f"### {time_descriptions.get(timeframe, timeframe)}\n"
        
        trend = price_action.get('trend', 'unknown')
        volatility = price_action.get('volatility', 'unknown')
        current_direction = price_action.get('current_direction', 'unknown')
        patterns = price_action.get('patterns', [])
        
        summary += f"- 추세: {trend}\n"
        summary += f"- 변동성: {volatility}\n"
        summary += f"- 현재 방향: {current_direction}\n"
        
        if patterns:
            summary += f"- 감지된 패턴: {', '.join(patterns)}\n"
            
        summary += "\n"
    
    # 최근 뉴스 요약
    news = market_analysis.get('news', [])
    if news:
        summary += "## 최근 비트코인 뉴스\n"
        
        for i, item in enumerate(news[:5], 1):  # 최대 5개 뉴스만 표시
            title = item.get('title', '')
            date = item.get('date', '')
            source = item.get('source', '')
            
            summary += f"{i}. {title} ({source}, {date})\n"
            
        summary += "\n"
    
    # 거래 성과 요약
    if performance_metrics and performance_metrics.get('overall'):
        overall = performance_metrics.get('overall', {})
        summary += "## 거래 성과 분석\n"
        
        total_trades = overall.get('total_trades', 0)
        win_rate = overall.get('win_rate', 0)
        avg_profit = overall.get('avg_profit_loss_percentage', 0)
        
        summary += f"- 총 거래 수: {total_trades}\n"
        if total_trades > 0:
            summary += f"- 승률: {win_rate:.2f}%\n"
            summary += f"- 평균 수익률: {avg_profit:.2f}%\n"
            summary += f"- 최대 이익: {overall.get('max_profit_percentage', 0):.2f}%\n"
            summary += f"- 최대 손실: {overall.get('max_loss_percentage', 0):.2f}%\n"
        
        # 방향별 성과
        directional = performance_metrics.get('directional', {})
        if 'long' in directional:
            long_data = directional['long']
            summary += f"- 롱 포지션: {long_data.get('total_trades', 0)}건, 승률: {long_data.get('win_rate', 0):.2f}%\n"
            
        if 'short' in directional:
            short_data = directional['short']
            summary += f"- 숏 포지션: {short_data.get('total_trades', 0)}건, 승률: {short_data.get('win_rate', 0):.2f}%\n"
        
        summary += "\n"
    
    # 최근 거래 내역
    if trading_history:
        summary += "## 최근 거래 내역\n"
        
        for i, trade in enumerate(trading_history[:3], 1):  # 최대 3개 거래만 표시
            action = trade.get('action', '')
            entry_price = trade.get('entry_price', 0)
            exit_price = trade.get('exit_price', 0)
            profit_loss_pct = trade.get('profit_loss_percentage', 0)
            leverage = trade.get('leverage', 1)
            
            result = "이익" if profit_loss_pct > 0 else "손실"
            summary += f"{i}. {action.upper()} 포지션 (레버리지: {leverage}x): "
            summary += f"진입 ${entry_price:,.2f} → 청산 ${exit_price:,.2f}, "
            summary += f"결과: {result} ({profit_loss_pct:.2f}%)\n"
        
        summary += "\n"
    
    # 최종 요청
    summary += "## 분석 요청\n"
    summary += "위 데이터를 종합적으로 분석하여 현재 시장에 대한 최적의 거래 전략을 제시하세요.\n"
    summary += "LONG, SHORT, NO_POSITION 중 하나를 선택하고, 적절한 레버리지와 포지션 크기, 스탑로스 및 테이크프로핏 수준을 제안하세요.\n"
    
    return summary

def save_analysis_to_db(analysis_data):
    """
    AI 분석 결과를 데이터베이스에 저장
    
    매개변수:
        analysis_data (dict): 저장할 AI 분석 결과
        
    반환값:
        int: 생성된 분석 기록의 ID 또는 None (실패 시)
    """
    try:
        if not analysis_data:
            print("저장할 분석 데이터가 없습니다.")
            return None
            
        # 데이터베이스에 저장
        analysis_id = save_ai_analysis(analysis_data)
        
        if analysis_id:
            print(f"AI 분석 결과가 데이터베이스에 저장되었습니다. (ID: {analysis_id})")
        else:
            print("AI 분석 결과 저장에 실패했습니다.")
            
        return analysis_id
    except Exception as e:
        print(f"분석 데이터 저장 중 오류: {e}")
        return None

def evaluate_trading_decision(analysis_result):
    """
    AI의 거래 결정에 대한 평가 및 요약
    
    매개변수:
        analysis_result (dict): AI 분석 결과
        
    반환값:
        str: 거래 결정에 대한 설명
    """
    if not analysis_result:
        return "분석 결과가 없습니다."
        
    direction = analysis_result.get('direction', 'NO_POSITION')
    pos_size = analysis_result.get('recommended_position_size', 0)
    leverage = analysis_result.get('recommended_leverage', 0)
    sl_pct = analysis_result.get('stop_loss_percentage', 0)
    tp_pct = analysis_result.get('take_profit_percentage', 0)
    reasoning = analysis_result.get('reasoning', '')
    
    # 요약 구성
    if direction == 'NO_POSITION':
        summary = "현재 시장 상황에서는 포지션 진입을 권장하지 않습니다."
    else:
        action = "매수" if direction == 'LONG' else "매도"
        summary = f"{direction} 포지션 {action} 권장 (자본의 {pos_size*100:.1f}%, {leverage}x 레버리지)"
        summary += f"\n스탑로스: {sl_pct:.2f}%, 테이크프로핏: {tp_pct:.2f}%"
    
    # 간략한 이유 추가 (200자 제한)
    reason_summary = reasoning[:200] + "..." if len(reasoning) > 200 else reasoning
    summary += f"\n\n근거: {reason_summary}"
    
    return summary 