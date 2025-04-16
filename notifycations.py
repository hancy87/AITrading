import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(message):
    """
    텔레그램 봇을 통해 메시지를 보냅니다.

    매개변수:
        message (str): 보낼 메시지 내용
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("텔레그램 설정(토큰 또는 채팅 ID)이 누락되었습니다.")
        return False

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    params = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown' # 필요에 따라 'HTML' 또는 제거 가능
    }

    try:
        response = requests.post(api_url, params=params, timeout=10)
        response.raise_for_status() # HTTP 오류 발생 시 예외 발생
        print(f"텔레그램 메시지 전송 성공: {message[:50]}...") # 로그 추가
        return True
    except requests.exceptions.RequestException as e:
        print(f"텔레그램 메시지 전송 실패: {e}")
        # 여기서 실패 시 재시도 로직 등을 추가할 수 있습니다.
        return False
    except Exception as e:
        print(f"텔레그램 메시지 전송 중 예상치 못한 오류: {e}")
        return False

# 테스트용 코드 (파일을 직접 실행할 때만 동작)
if __name__ == "__main__":
    test_message = "*테스트 메시지*입니다.\n_성공적으로_ 전송되었는지 확인하세요."
    if send_telegram_message(test_message):
        print("테스트 메시지 전송 시도 완료.")
    else:
        print("테스트 메시지 전송 시도 실패.")
