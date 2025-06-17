# test_openai.py - 간단한 API 테스트

import os
from dotenv import load_dotenv
import openai

def test_openai_api():
    """OpenAI API 직접 테스트"""
    print("🧪 OpenAI API 직접 테스트...")
    
    # 환경변수 로드
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ OPENAI_API_KEY가 설정되지 않았습니다.")
        return False
    
    print(f"🔑 테스트할 API 키: {api_key[:15]}...")
    
    # OpenAI 클라이언트 설정
    openai.api_key = api_key
    
    try:
        # 간단한 API 호출 테스트
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "안녕하세요. 간단히 인사만 해주세요."}
            ],
            max_tokens=50
        )
        
        result = response.choices[0].message.content
        print(f"✅ API 호출 성공!")
        print(f"📝 응답: {result}")
        return True
        
    except openai.AuthenticationError as e:
        print(f"❌ 인증 오류: {e}")
        print("💡 API 키를 다시 확인해주세요.")
        return False
        
    except openai.RateLimitError as e:
        print(f"⚠️ 사용량 초과: {e}")
        print("💡 OpenAI 계정의 사용량과 결제 상태를 확인해주세요.")
        return False
        
    except Exception as e:
        print(f"❌ 기타 오류: {e}")
        return False

if __name__ == "__main__":
    success = test_openai_api()
    if success:
        print("\n🎉 API 테스트 성공! 사주 서비스에서도 정상 작동할 것입니다.")
    else:
        print("\n🔧 API 설정을 다시 확인해주세요.")