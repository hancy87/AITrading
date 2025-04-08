"""
AI 분석 및 거래 결정 모듈
"""
import json
import time
import logging
from datetime import datetime
import traceback
from config import (
    client, OPENROUTER_MODEL, MAX_API_RETRIES, MAX_REASONING_LENGTH,
    MODEL_COST_INPUT_PER_MILLION_TOKENS, MODEL_COST_OUTPUT_PER_MILLION_TOKENS
)
from database import save_ai_analysis, get_performance_metrics, get_historical_trading_data, update_daily_api_cost

logger = logging.getLogger(__name__)

def process_ai_analysis(market_analysis):
    """
    시장 데이터를 기반으로 AI 분석을 수행하고 거래 결정 생성
    
    매개변수:
        market_analysis (dict): 시장 데이터 및 분석 결과
        
    반환값:
        dict: AI 분석 결과 및 거래 추천 데이터 (토큰 사용량, 비용 포함)
    """
    if not market_analysis:
        logger.warning("시장 분석 데이터가 없어 AI 분석을 진행할 수 없습니다.")
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
        system_prompt = """        
          You are a crypto trading expert specializing in multi-timeframe analysis and news sentiment analysis applying Kelly criterion to determine optimal position sizing, leverage, and risk management.
You adhere strictly to Warren Buffett's investment principles:

**Rule No.1: Never lose money.**
**Rule No.2: Never forget rule No.1.**

Analyze the market data across different timeframes (15m, 1h, 4h), recent news headlines, and historical trading performance to provide your trading decision.

Follow this process:
1. Review historical trading performance:
   - Examine the outcomes of recent trades (profit/loss)
   - Review your previous analysis and trading decisions
   - Identify what worked well and what didn't
   - Learn from past mistakes and successful patterns
   - Compare the performance of LONG vs SHORT positions
   - Evaluate the effectiveness of your stop-loss and take-profit levels
   - Assess which leverage settings performed best

2. Assess the current market condition across all timeframes:
   - Short-term trend (15m): Recent price action and momentum
   - Medium-term trend (1h): Intermediate market direction
   - Long-term trend (4h): Overall market bias
   - Volatility across timeframes
   - Key support/resistance levels
   - News sentiment: Analyze recent news article titles for bullish or bearish sentiment

3. Based on your analysis, determine:
   - Direction: Whether to go LONG or SHORT
   - Conviction: Probability of success (as a percentage between 51-95%)

4. Calculate Kelly position sizing:
   - Use the Kelly formula: f* = (p - q/b)
   - Where:
     * f* = fraction of capital to risk
     * p = probability of success (your conviction level)
     * q = probability of failure (1 - p)
     * b = win/loss ratio (based on stop loss and take profit distances)
   - Adjust based on historical win rates and profit/loss ratios

5. Determine optimal leverage:
   - Based on market volatility across timeframes
   - Consider higher leverage (up to 20x) in low volatility trending markets
   - Use lower leverage (1-3x) in high volatility or uncertain markets
   - Never exceed what is prudent based on your conviction level
   - Learn from past leverage decisions and their outcomes
   - Be more conservative if recent high-leverage trades resulted in losses

6. Set optimal Stop Loss (SL) and Take Profit (TP) levels:
   - Analyze recent price action, support/resistance levels
   - Consider volatility to prevent premature stop-outs
   - Set SL at a technical level that would invalidate your trade thesis
   - Set TP at a realistic target based on technical analysis
   - Both levels should be expressed as percentages from entry price
   - Adapt based on historical SL/TP performance and premature stop-outs
   - Learn from trades that hit SL vs TP and adjust accordingly

7. Apply risk management:
   - Never recommend betting more than 50% of the Kelly criterion (half-Kelly) to reduce volatility
   - If expected direction has less than 55% conviction, recommend not taking the trade (use "NO_POSITION")
   - Adjust leverage to prevent high risk exposure
   - Be more conservative if recent trades showed losses
   - If overall win rate is below 50%, be more selective with your entries

8. Provide reasoning:
   - Explain the rationale behind your trading direction, leverage, and SL/TP recommendations
   - Highlight key factors from your analysis that influenced your decision
   - Discuss how historical performance informed your current decision
   - If applicable, explain how you're adapting based on recent trade outcomes
   - Mention specific patterns you've observed in successful vs unsuccessful trades

Your response must contain ONLY a valid JSON object with exactly these 6 fields:
{
  "direction": "LONG" or "SHORT" or "NO_POSITION",
  "recommended_position_size": [final recommended position size as decimal between 0.1-1.0],
  "recommended_leverage": [an integer between 1-20],
  "stop_loss_percentage": [percentage distance from entry as decimal, e.g., 0.005 for 0.5%],
  "take_profit_percentage": [percentage distance from entry as decimal, e.g., 0.005 for 0.5%],
  "reasoning": "Your detailed explanation for all recommendations"
}

IMPORTANT: Do not format your response as a code block. Do not include ```json, ```, or any other markdown formatting. Return ONLY the raw JSON object.
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
                logger.info(f"AI 분석 요청 중... (시도 {attempt+1}/{MAX_API_RETRIES})")
                
                if client is None:
                    logger.error("OpenAI 클라이언트가 초기화되지 않았습니다. API 호출 불가.")
                    return None
                    
                # OpenRouter API 호출
                response = client.chat.completions.create(
                    model=OPENROUTER_MODEL,
                    messages=messages,
                    temperature=0.2,  # 낮은 온도로 일관된 응답 유도
                    max_tokens=5000,  # 이전 오류 기반으로 토큰 증가
                    response_format={"type": "json_object"}
                )
                
                break  # 성공 시 반복 중단
            except Exception as e:
                error_message = f"AI API 요청 오류 (시도 {attempt+1}): {str(e)}"
                logger.warning(error_message)
                error_messages.append(error_message)
                if attempt < MAX_API_RETRIES - 1:
                    time.sleep(10)  # 재시도 전 10초 대기
        
        # 응답이 없는 경우 또는 None인 경우
        if not response:
            combined_errors = "; ".join(error_messages)
            logger.error(f"최대 시도 횟수 초과 또는 유효한 API 응답 없음, AI 분석 실패: {combined_errors}")
            logger.debug(f"최종 response 객체: {response}")
            return None
            
        logger.debug(f"수신된 response 객체: {response}")
        try:
            # 토큰 사용량 추출
            usage = response.usage
            usage_data = {
                'completion_tokens': usage.completion_tokens if usage else 0,
                'prompt_tokens': usage.prompt_tokens if usage else 0,
                'total_tokens': usage.total_tokens if usage else 0
            }
            logger.info(f"API 사용량: 입력 {usage_data['prompt_tokens']}, 출력 {usage_data['completion_tokens']}, 총 {usage_data['total_tokens']} 토큰")

            # API 비용 계산
            input_cost = (usage_data['prompt_tokens'] / 1_000_000) * MODEL_COST_INPUT_PER_MILLION_TOKENS
            output_cost = (usage_data['completion_tokens'] / 1_000_000) * MODEL_COST_OUTPUT_PER_MILLION_TOKENS
            total_cost = input_cost + output_cost
            logger.info(f"해당 API 호출 비용: ${total_cost:.6f}")
            logging.debug(f"response: {response}")
            # AI 응답 추출 및 처리
            ai_content = response.choices[0].message.content
            cleaned_json = clean_ai_response(ai_content)
            # --- 추가된 디버깅 로그 ---
            logger.debug(f"--- AI 원본 내용 (ai_content): {ai_content} ---")
            logger.debug(f"--- 정제된 내용 (cleaned_json): {cleaned_json} ---")
            # -------------------------


            
            try:
                analysis_result = json.loads(cleaned_json)
                
                # 필수 필드 확인
                required_fields = ["direction", "recommended_position_size", "recommended_leverage", 
                                  "stop_loss_percentage", "take_profit_percentage", "reasoning"]
                
                for field in required_fields:
                    if field not in analysis_result:
                        logger.error(f"AI 응답에 필수 필드가 누락되었습니다: {field}")
                        return None
                        
                # 값 정규화 및 유효성 검사
                analysis_result["direction"] = analysis_result["direction"].upper()
                if analysis_result["direction"] not in ["LONG", "SHORT", "NO_POSITION"]:
                    analysis_result["direction"] = "NO_POSITION"  # 기본값
                    
                pos_size = float(analysis_result["recommended_position_size"])
                analysis_result["recommended_position_size"] = max(0.1, min(1.0, pos_size))
                
                leverage = int(float(analysis_result["recommended_leverage"]))
                analysis_result["recommended_leverage"] = max(1, min(5, leverage))
                
                sl_pct = float(analysis_result["stop_loss_percentage"])
                tp_pct = float(analysis_result["take_profit_percentage"])
                analysis_result["stop_loss_percentage"] = max(0.5, min(10.0, sl_pct))
                analysis_result["take_profit_percentage"] = max(1.0, min(20.0, tp_pct))
                
                if len(analysis_result["reasoning"]) > MAX_REASONING_LENGTH:
                    analysis_result["reasoning"] = analysis_result["reasoning"][:MAX_REASONING_LENGTH] + "..."
                
                # 분석 결과에 사용량 및 비용 정보 추가
                analysis_result["current_price"] = current_price
                analysis_result["usage_data"] = usage_data
                analysis_result["api_cost"] = total_cost
                
                return analysis_result
                
            except json.JSONDecodeError as e:
                logger.error(f"AI 응답을 JSON으로 파싱할 수 없습니다: {e}")
                logger.debug(f"원본 응답: {ai_content}")
                logger.debug(f"정제된 응답: {cleaned_json}")
                return None
            except Exception as e:
                logger.error(f"AI 응답 내용 처리 중 오류 발생: {e}")
                logger.debug(traceback.format_exc())
                return None

        except TypeError as te:
             logger.error(f"응답 내용 접근 중 TypeError 발생: {te}")
             logger.error(f"문제를 일으킨 response 객체: {response}")
             return None
        except AttributeError as ae:
             logger.error(f"응답 객체 속성 접근 중 오류 발생: {ae}")
             logger.error(f"문제를 일으킨 response 객체: {response}")
             return None
        except Exception as e:
            logger.error(f"API 응답 처리 중 예상치 못한 오류: {e}")
            logger.debug(traceback.format_exc())
            return None
            
    except Exception as e:
        logger.error(f"AI 분석 과정에서 예외 발생: {e}")
        logger.debug(traceback.format_exc())
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
        logger.warning(f"AI 응답 정제 중 오류: {e}")
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
    
    # 기술적 지표, 가격 행동, 거래량 분석 요약
    summary += "## 시장 분석 (타임프레임별)\n"
    
    # 각 타임프레임별 데이터 추가
    time_descriptions = {
        '15m': '15분 차트',
        '1h': '1시간 차트',
        '4h': '4시간 차트'
    }
    
    for timeframe in time_descriptions.keys():
        indicators = market_analysis.get('technical_indicators', {}).get(timeframe)
        price_act = market_analysis.get('price_action', {}).get(timeframe)
        vol_analysis = market_analysis.get('volume_analysis', {}).get(timeframe)

        if not indicators and not price_act and not vol_analysis:
            continue

        summary += f"### {time_descriptions.get(timeframe, timeframe)}\n"

        # 기술적 지표 요약
        if indicators:
            summary += "**기술 지표:**\n"
            rsi = indicators.get('rsi', 0)
            rsi_zone = indicators.get('rsi_zone', 'neutral')
            summary += f"- RSI: {rsi:.2f} ({rsi_zone})\n"
            sma7 = indicators.get('sma7', 0)
            sma21 = indicators.get('sma21', 0)
            sma_trend = indicators.get('sma_trend', '')
            summary += f"- SMA7: ${sma7:.2f}, SMA21: ${sma21:.2f} (추세: {sma_trend})\n"
            bollinger = indicators.get('bollinger', {})
            bollinger_position = indicators.get('bollinger_position', 'middle')
            summary += f"- 볼린저 밴드: 상단=${bollinger.get('upper', 0):.2f}, 중간=${bollinger.get('middle', 0):.2f}, 하단=${bollinger.get('lower', 0):.2f} (위치: {bollinger_position})\n"
            macd_data = indicators.get('macd', {})
            macd = macd_data.get('macd', 0)
            signal = macd_data.get('signal', 0)
            histogram = macd_data.get('histogram', 0)
            summary += f"- MACD: {macd:.2f}, 시그널: {signal:.2f}, 히스토그램: {histogram:.2f}\n"

        # 가격 행동 분석 요약
        if price_act:
            summary += "**가격 행동:**\n"
            trend = price_act.get('trend', 'unknown')
            volatility = price_act.get('volatility', 'unknown')
            current_direction = price_act.get('current_direction', 'unknown')
            patterns = price_act.get('patterns', [])
            summary += f"- 추세: {trend}, 변동성: {volatility}, 현재 방향: {current_direction}\n"
            if patterns:
                summary += f"- 감지된 패턴: {', '.join(patterns)}\n"

        # 거래량 분석 요약
        if vol_analysis:
            summary += "**거래량 분석:**\n"
            current_vol = vol_analysis.get('current_volume', 0)
            avg_vol = vol_analysis.get('average_volume', 0)
            vol_ratio = vol_analysis.get('volume_ratio', 0)
            vol_spike = vol_analysis.get('volume_spike', False)
            trend_confirm = vol_analysis.get('trend_confirmation', 'neutral')
            summary += f"- 현재 거래량: {current_vol:.2f} (평균 대비 {vol_ratio:.2f}배)\n"
            summary += f"- 거래량 급증: {'예' if vol_spike else '아니오'}\n"
            summary += f"- 추세 지지: {trend_confirm}\n"
            
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
    AI 분석 결과를 데이터베이스에 저장하고 일일 비용 업데이트
    
    매개변수:
        analysis_data (dict): 저장할 AI 분석 결과 (usage_data, api_cost 포함)
        
    반환값:
        int: 생성된 분석 기록의 ID 또는 None (실패 시)
    """
    try:
        if not analysis_data:
            logger.warning("저장할 분석 데이터가 없습니다.")
            return None
            
        usage_data = analysis_data.get('usage_data')
        api_cost = analysis_data.get('api_cost', 0.0)
        total_tokens = usage_data.get('total_tokens', 0) if usage_data else 0
            
        # 데이터베이스에 저장
        analysis_id = save_ai_analysis(analysis_data, usage_data=usage_data, api_cost=api_cost)
        
        if analysis_id:
            logger.info(f"AI 분석 결과가 데이터베이스에 저장되었습니다. (ID: {analysis_id})")
            
            # 일일 API 비용 업데이트
            today_date_str = datetime.now().strftime('%Y-%m-%d')
            update_daily_api_cost(today_date_str, api_cost, total_tokens)
            logger.info(f"{today_date_str} API 비용 업데이트: +${api_cost:.6f}, +{total_tokens} 토큰")
        else:
            logger.error("AI 분석 결과 저장에 실패했습니다.")
            
        return analysis_id
    except Exception as e:
        logger.error(f"분석 데이터 저장 중 오류: {e}")
        logger.debug(traceback.format_exc())
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
    api_cost = analysis_result.get('api_cost', 0.0)
    total_tokens = analysis_result.get('usage_data', {}).get('total_tokens', 0)
    
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
    
    # 비용 정보 추가
    summary += f"\n(비용: ${api_cost:.6f}, 토큰: {total_tokens})"
    
    return summary 