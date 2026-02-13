import asyncio
import aiohttp
from pathlib import Path

# Load .env file manually
def load_env():
    """Load environment variables from .env file"""
    env_path = Path('.env')
    
    if not env_path.exists():
        print("❌ .env file not found!")
        return {}
    
    env_vars = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    print(f"✅ Loaded {len(env_vars)} variables from .env")
    return env_vars


async def test_groq(api_key, test_message="What is Python? Answer in one sentence."):
    """Test Groq API"""
    if not api_key:
        print("❌ GROQ_API_KEY_1 not found in .env!")
        return False
    
    print(f"\n✅ GROQ_API_KEY_1: {api_key[:20]}...")
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": test_message}
        ],
        "temperature": 0.7,
        "max_tokens": 200
    }
    
    print(f"🚀 Testing Groq API...")
    print(f"📝 Question: {test_message}")
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            print("📤 Sending request...")
            async with session.post(url, headers=headers, json=data) as response:
                print(f"📥 Status: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    content = result['choices'][0]['message']['content']
                    tokens = result.get('usage', {}).get('total_tokens', 0)
                    print(f"✅ Response ({tokens} tokens):")
                    print(f"   {content}")
                    return True
                else:
                    error = await response.text()
                    print(f"❌ Error: {error[:300]}")
                    return False
    
    except asyncio.TimeoutError:
        print("❌ Timeout! Request took too long")
        return False
    except Exception as e:
        print(f"❌ Exception: {type(e).__name__}: {e}")
        return False


async def test_multiple_messages(api_key):
    """Test conversation with multiple messages"""
    print(f"\n{'='*60}")
    print("🔁 TESTING CONVERSATION (Multiple Messages)")
    print('='*60)
    
    if not api_key:
        print("❌ GROQ_API_KEY_1 not found!")
        return False
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    conversation = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello! What's your name?"},
        {"role": "assistant", "content": "Hello! I'm an AI assistant. How can I help you?"},
        {"role": "user", "content": "Tell me a joke about programming"}
    ]
    
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": conversation,
        "temperature": 0.8,
        "max_tokens": 150
    }
    
    print("📝 Conversation history:")
    for msg in conversation:
        print(f"   [{msg['role']}]: {msg['content']}")
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            print("\n📤 Sending request...")
            async with session.post(url, headers=headers, json=data) as response:
                print(f"📥 Status: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    content = result['choices'][0]['message']['content']
                    print(f"✅ AI Response:")
                    print(f"   {content}")
                    return True
                else:
                    error = await response.text()
                    print(f"❌ Error: {error[:300]}")
                    return False
    
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


async def main():
    print("="*60)
    print("🔍 GROQ API FULL TEST")
    print("="*60)
    
    # Load .env file
    env_vars = load_env()
    
    if not env_vars:
        print("\n⚠️  Create a .env file with:")
        print("     GROQ_API_KEY_1=gsk_your_key_here")
        return
    
    groq_key = env_vars.get('GROQ_API_KEY_1')
    
    # Test 1: Simple question
    print("\n" + "="*60)
    print("TEST 1: Simple Question")
    print("="*60)
    test1 = await test_groq(groq_key, "What is Python?")
    
    # Test 2: Different question
    print("\n" + "="*60)
    print("TEST 2: Different Question")
    print("="*60)
    test2 = await test_groq(groq_key, "Explain AI in simple terms")
    
    # Test 3: Conversation
    test3 = await test_multiple_messages(groq_key)
    
    # Summary
    print("\n" + "="*60)
    print("📊 FINAL RESULTS:")
    print(f"  Test 1 (Simple):       {'✅ Pass' if test1 else '❌ Fail'}")
    print(f"  Test 2 (Different):    {'✅ Pass' if test2 else '❌ Fail'}")
    print(f"  Test 3 (Conversation): {'✅ Pass' if test3 else '❌ Fail'}")
    print("="*60)
    
    if test1 and test2 and test3:
        print("\n🎉 ALL TESTS PASSED! Bot ready to use!")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())
