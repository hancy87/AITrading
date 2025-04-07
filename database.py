"""
데이터베이스 관련 기능 모듈
"""
import sqlite3
from datetime import datetime
from config import DB_FILE

def get_db_connection():
    """
    데이터베이스 연결을 생성하고 반환
    
    반환값:
        conn: 데이터베이스 연결 객체
    """
    conn = sqlite3.connect(DB_FILE, timeout=10)
    # 외래 키 제약 활성화
    conn.execute('PRAGMA foreign_keys = ON')
    # Row 팩토리 설정 (결과를 딕셔너리로 받기)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    """
    데이터베이스 및 필요한 테이블 생성
    
    거래 기록과 AI 분석 결과를 저장하기 위한 테이블을 생성합니다.
    - trades: 모든 거래 정보 (진입가, 청산가, 손익 등)
    - ai_analysis: AI의 분석 결과 및 추천 사항
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 거래 기록 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,           -- 거래 시작 시간
        action TEXT NOT NULL,              -- long 또는 short
        entry_price REAL NOT NULL,         -- 진입 가격
        amount REAL NOT NULL,              -- 거래량 (BTC)
        leverage INTEGER NOT NULL,         -- 레버리지 배수
        sl_price REAL NOT NULL,            -- 스탑로스 가격
        tp_price REAL NOT NULL,            -- 테이크프로핏 가격
        sl_percentage REAL NOT NULL,       -- 스탑로스 백분율
        tp_percentage REAL NOT NULL,       -- 테이크프로핏 백분율
        position_size_percentage REAL NOT NULL,  -- 자본 대비 포지션 크기
        investment_amount REAL NOT NULL,   -- 투자 금액 (USDT)
        status TEXT DEFAULT 'OPEN',        -- 거래 상태 (OPEN/CLOSED)
        exit_price REAL,                   -- 청산 가격
        exit_timestamp TEXT,               -- 청산 시간
        profit_loss REAL,                  -- 손익 (USDT)
        profit_loss_percentage REAL        -- 손익 백분율
    )
    ''')
    
    # AI 분석 결과 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ai_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,               -- 분석 시간
        current_price REAL NOT NULL,           -- 분석 시점 가격
        direction TEXT NOT NULL,               -- 방향 추천 (LONG/SHORT/NO_POSITION)
        recommended_position_size REAL NOT NULL,  -- 추천 포지션 크기
        recommended_leverage INTEGER NOT NULL,    -- 추천 레버리지
        stop_loss_percentage REAL NOT NULL,       -- 추천 스탑로스 비율
        take_profit_percentage REAL NOT NULL,     -- 추천 테이크프로핏 비율
        reasoning TEXT NOT NULL,                  -- 분석 근거 설명
        trade_id INTEGER,                         -- 연결된 거래 ID
        FOREIGN KEY (trade_id) REFERENCES trades (id)  -- 외래 키 설정
    )
    ''')
    
    # 인덱스 생성 (성능 최적화)
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_analysis_timestamp ON ai_analysis(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_analysis_trade_id ON ai_analysis(trade_id)')
    
    conn.commit()
    conn.close()
    print("데이터베이스 설정 완료")

def save_ai_analysis(analysis_data, trade_id=None):
    """
    AI 분석 결과를 데이터베이스에 저장
    
    매개변수:
        analysis_data (dict): AI 분석 결과 데이터
        trade_id (int, optional): 연결된 거래 ID
        
    반환값:
        int: 생성된 분석 기록의 ID
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        INSERT INTO ai_analysis (
            timestamp, 
            current_price, 
            direction, 
            recommended_position_size, 
            recommended_leverage, 
            stop_loss_percentage, 
            take_profit_percentage, 
            reasoning,
            trade_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),  # 현재 시간
            analysis_data.get('current_price', 0),  # 현재 가격
            analysis_data.get('direction', 'NO_POSITION'),  # 추천 방향
            analysis_data.get('recommended_position_size', 0),  # 추천 포지션 크기
            analysis_data.get('recommended_leverage', 0),  # 추천 레버리지
            analysis_data.get('stop_loss_percentage', 0),  # 스탑로스 비율
            analysis_data.get('take_profit_percentage', 0),  # 테이크프로핏 비율
            analysis_data.get('reasoning', ''),  # 분석 근거
            trade_id  # 연결된 거래 ID
        ))
        
        analysis_id = cursor.lastrowid
        conn.commit()
        return analysis_id
    except Exception as e:
        conn.rollback()
        print(f"AI 분석 저장 중 오류: {e}")
        return None
    finally:
        conn.close()

def save_trade(trade_data):
    """
    거래 정보를 데이터베이스에 저장
    
    매개변수:
        trade_data (dict): 거래 정보 데이터
        
    반환값:
        int: 생성된 거래 기록의 ID
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        INSERT INTO trades (
            timestamp,
            action,
            entry_price,
            amount,
            leverage,
            sl_price,
            tp_price,
            sl_percentage,
            tp_percentage,
            position_size_percentage,
            investment_amount
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),  # 진입 시간
            trade_data.get('action', ''),  # 포지션 방향
            trade_data.get('entry_price', 0),  # 진입 가격
            trade_data.get('amount', 0),  # 거래량
            trade_data.get('leverage', 0),  # 레버리지
            trade_data.get('sl_price', 0),  # 스탑로스 가격
            trade_data.get('tp_price', 0),  # 테이크프로핏 가격
            trade_data.get('sl_percentage', 0),  # 스탑로스 비율
            trade_data.get('tp_percentage', 0),  # 테이크프로핏 비율
            trade_data.get('position_size_percentage', 0),  # 자본 대비 포지션 크기
            trade_data.get('investment_amount', 0)  # 투자 금액
        ))
        
        trade_id = cursor.lastrowid
        conn.commit()
        return trade_id
    except Exception as e:
        conn.rollback()
        print(f"거래 정보 저장 중 오류: {e}")
        return None
    finally:
        conn.close()

def update_trade_status(trade_id, status, exit_price=None, exit_timestamp=None, profit_loss=None, profit_loss_percentage=None):
    """
    거래 상태를 업데이트합니다
    
    매개변수:
        trade_id (int): 업데이트할 거래의 ID
        status (str): 새 상태 ('OPEN' 또는 'CLOSED')
        exit_price (float, optional): 청산 가격
        exit_timestamp (str, optional): 청산 시간
        profit_loss (float, optional): 손익 금액
        profit_loss_percentage (float, optional): 손익 비율
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 동적으로 SQL 업데이트 쿼리 구성
        update_fields = ["status = ?"]
        update_values = [status]
        
        # 제공된 필드만 업데이트에 포함
        if exit_price is not None:
            update_fields.append("exit_price = ?")
            update_values.append(exit_price)
        
        if exit_timestamp is not None:
            update_fields.append("exit_timestamp = ?")
            update_values.append(exit_timestamp)
        
        if profit_loss is not None:
            update_fields.append("profit_loss = ?")
            update_values.append(profit_loss)
        
        if profit_loss_percentage is not None:
            update_fields.append("profit_loss_percentage = ?")
            update_values.append(profit_loss_percentage)
        
        update_sql = f"UPDATE trades SET {', '.join(update_fields)} WHERE id = ?"
        update_values.append(trade_id)
        
        cursor.execute(update_sql, update_values)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"거래 상태 업데이트 중 오류: {e}")
    finally:
        conn.close()

def get_latest_open_trade():
    """
    가장 최근의 열린 거래 정보를 가져옵니다
    
    반환값:
        dict: 거래 정보 또는 None (열린 거래가 없는 경우)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT id, action, entry_price, amount, leverage, sl_price, tp_price
    FROM trades
    WHERE status = 'OPEN'
    ORDER BY timestamp DESC  -- 가장 최근 거래 먼저
    LIMIT 1
    ''')
    
    result = cursor.fetchone()
    conn.close()
    
    # 결과가 있을 경우 사전 형태로 변환하여 반환
    if result:
        return dict(result)
    return None  # 열린 거래가 없음

def get_trade_summary(days=7):
    """
    지정된 일수 동안의 거래 요약 정보를 가져옵니다
    
    매개변수:
        days (int): 요약할 기간(일)
        
    반환값:
        dict: 거래 요약 정보 또는 None
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        SELECT 
            COUNT(*) as total_trades,                            -- 총 거래 수
            SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,  -- 이익 거래 수
            SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losing_trades,   -- 손실 거래 수
            SUM(profit_loss) as total_profit_loss,               -- 총 손익
            AVG(profit_loss_percentage) as avg_profit_loss_percentage  -- 평균 손익률
        FROM trades
        WHERE exit_timestamp IS NOT NULL  -- 청산된 거래만
        AND timestamp >= datetime('now', ?)  -- 지정된 일수 내 거래만
        ''', (f'-{days} days',))
        
        result = cursor.fetchone()
        
        # 결과가 있을 경우 사전 형태로 변환하여 반환
        if result:
            return {
                'total_trades': result['total_trades'] or 0,
                'winning_trades': result['winning_trades'] or 0,
                'losing_trades': result['losing_trades'] or 0,
                'total_profit_loss': result['total_profit_loss'] or 0,
                'avg_profit_loss_percentage': result['avg_profit_loss_percentage'] or 0
            }
        return None
    except Exception as e:
        print(f"거래 요약 조회 중 오류: {e}")
        return None
    finally:
        conn.close()

def get_historical_trading_data(limit=10):
    """
    과거 거래 내역과 관련 AI 분석 결과를 가져옵니다
    
    매개변수:
        limit (int): 가져올 최대 거래 기록 수
        
    반환값:
        list: 거래 및 분석 데이터 사전 목록
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 완료된 거래 내역과 관련 AI 분석 함께 조회 (LEFT JOIN 사용)
        cursor.execute('''
        SELECT 
            t.id as trade_id,
            t.timestamp as trade_timestamp,
            t.action,
            t.entry_price,
            t.exit_price,
            t.amount,
            t.leverage,
            t.sl_price,
            t.tp_price,
            t.sl_percentage,
            t.tp_percentage,
            t.position_size_percentage,
            t.status,
            t.profit_loss,
            t.profit_loss_percentage,
            a.id as analysis_id,
            a.reasoning,
            a.direction,
            a.recommended_leverage,
            a.recommended_position_size,
            a.stop_loss_percentage,
            a.take_profit_percentage
        FROM 
            trades t
        LEFT JOIN 
            ai_analysis a ON t.id = a.trade_id
        WHERE 
            t.status = 'CLOSED'  -- 완료된 거래만
        ORDER BY 
            t.timestamp DESC  -- 최신 거래 먼저
        LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        
        # 결과를 사전 목록으로 변환
        historical_data = []
        for row in results:
            historical_data.append(dict(row))
        
        return historical_data
    except Exception as e:
        print(f"과거 거래 내역 조회 중 오류: {e}")
        return []
    finally:
        conn.close()

def get_performance_metrics():
    """
    거래 성과 메트릭스를 계산합니다
    
    이 함수는 다음을 포함한 전체 및 방향별(롱/숏) 성과 지표를 계산합니다:
    - 총 거래 수
    - 승률
    - 평균 수익률
    - 최대 이익/손실
    - 방향별 성과
    
    반환값:
        dict: 성과 메트릭스 데이터
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 전체 거래 성과 쿼리
        cursor.execute('''
        SELECT 
            COUNT(*) as total_trades,
            SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
            SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
            SUM(profit_loss) as total_profit_loss,
            AVG(profit_loss_percentage) as avg_profit_loss_percentage,
            MAX(profit_loss_percentage) as max_profit_percentage,
            MIN(profit_loss_percentage) as max_loss_percentage,
            AVG(CASE WHEN profit_loss > 0 THEN profit_loss_percentage ELSE NULL END) as avg_win_percentage,
            AVG(CASE WHEN profit_loss < 0 THEN profit_loss_percentage ELSE NULL END) as avg_loss_percentage
        FROM trades
        WHERE status = 'CLOSED'
        ''')
        
        overall_metrics = cursor.fetchone()
        
        # 방향별(롱/숏) 성과 쿼리
        cursor.execute('''
        SELECT 
            action,
            COUNT(*) as total_trades,
            SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
            SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
            SUM(profit_loss) as total_profit_loss,
            AVG(profit_loss_percentage) as avg_profit_loss_percentage
        FROM trades
        WHERE status = 'CLOSED'
        GROUP BY action
        ''')
        
        directional_metrics = cursor.fetchall()
        
        # 결과 구성
        metrics = {
            "overall": {
                "total_trades": overall_metrics['total_trades'] or 0,
                "winning_trades": overall_metrics['winning_trades'] or 0,
                "losing_trades": overall_metrics['losing_trades'] or 0,
                "total_profit_loss": overall_metrics['total_profit_loss'] or 0,
                "avg_profit_loss_percentage": overall_metrics['avg_profit_loss_percentage'] or 0,
                "max_profit_percentage": overall_metrics['max_profit_percentage'] or 0,
                "max_loss_percentage": overall_metrics['max_loss_percentage'] or 0,
                "avg_win_percentage": overall_metrics['avg_win_percentage'] or 0,
                "avg_loss_percentage": overall_metrics['avg_loss_percentage'] or 0
            },
            "directional": {}
        }
        
        # 승률 계산
        if metrics["overall"]["total_trades"] > 0:
            metrics["overall"]["win_rate"] = (metrics["overall"]["winning_trades"] / metrics["overall"]["total_trades"]) * 100
        else:
            metrics["overall"]["win_rate"] = 0
        
        # 방향별 메트릭스 추가
        for row in directional_metrics:
            action = row['action']  # 'long' 또는 'short'
            total = row['total_trades'] or 0
            winning = row['winning_trades'] or 0
            
            direction_metrics = {
                "total_trades": total,
                "winning_trades": winning,
                "losing_trades": row['losing_trades'] or 0,
                "total_profit_loss": row['total_profit_loss'] or 0,
                "avg_profit_loss_percentage": row['avg_profit_loss_percentage'] or 0,
                "win_rate": (winning / total * 100) if total > 0 else 0
            }
            
            metrics["directional"][action] = direction_metrics
        
        return metrics
    except Exception as e:
        print(f"성과 메트릭스 계산 중 오류: {e}")
        return {"overall": {}, "directional": {}}
    finally:
        conn.close() 