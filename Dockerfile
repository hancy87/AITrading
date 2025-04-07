# Python 3.11 슬림 버전을 기반 이미지로 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 빌드 도구 설치 (필요시)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#    build-essential \
#    # 필요한 다른 시스템 라이브러리 추가
#    && rm -rf /var/lib/apt/lists/*

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# requirements.txt 복사 및 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 기본적으로 실행할 명령 (docker-compose에서 오버라이드 가능)
# CMD ["python", "main.py"] 