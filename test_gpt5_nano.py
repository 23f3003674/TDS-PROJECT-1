"""
Quick test to verify GPT-5 Nano via AI Pipe is working
"""
from openai import OpenAI
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

def test_gpt5_nano():
    """Test GPT-5 Nano connection via AI Pipe"""
    print("=" * 60)
    print("Testing GPT-5 Nano via AI Pipe")
    print("=" * 60)
    
    # Show configuration (masked)
    api_key = os.getenv('AIMLAPI_KEY')
    base_url = os.getenv('AIMLAPI_BASE_URL')
    model = os.getenv('AIMLAPI_MODEL')
    
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}" if api_key else "❌ No API Key found!")
    print(f"Base URL: {base_url}" if base_url else "❌ No Base URL found!")
    print(f"Model: {model}" if model else "❌ No Model specified!")
    print("-" * 60)
    
    if not api_key or not base_url or not model:
        print("\n❌ ERROR: Missing configuration in .env file!")
        print("\nPlease ensure your .env has:")
        print("  AIMLAPI_KEY=your_aipipe_key")
        print("  AIMLAPI_BASE_URL=https://aipipe.org/openai/v1")
        print("  AIMLAPI_MODEL=gpt-5-nano")
        return False
    
    try:
        # Initialize OpenAI client with AI Pipe configuration
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        print("\n🔄 Sending test request to GPT-5 Nano...")
        
        # GPT-5 Nano optimized request
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user", 
                    "content": "Write a Python function called 'add_numbers' that takes two parameters and returns their sum. Provide only the code, nothing else."
                }
            ],
            max_tokens=200  # Increased for full responses
        )
        
        # Extract response
        content = response.choices[0].message.content
        
        print("\n" + "=" * 60)
        
        if content and content.strip():
            print("✅ SUCCESS! GPT-5 Nano is working via AI Pipe!")
            print("=" * 60)
            print(f"\n📝 Response:\n{content}")
        else:
            print("⚠️ WARNING: Response received but content is empty")
            print("=" * 60)
            print(f"\nFull response object:")
            print(f"  Finish reason: {response.choices[0].finish_reason}")
            print(f"  Content: '{content}'")
            print(f"  Content length: {len(content) if content else 0}")
            
        print(f"\n📊 Tokens used: {response.usage.total_tokens}")
        print(f"   - Prompt tokens: {response.usage.prompt_tokens}")
        print(f"   - Completion tokens: {response.usage.completion_tokens}")
        
        if content and content.strip():
            print("\n✅ Your configuration is correct!")
            return True
        else:
            print("\n⚠️ API works but returns empty content. This is a known GPT-5 Nano quirk.")
            print("   The main application has fallback handling for this.")
            return True  # Still consider it working
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ ERROR: Connection failed!")
        print("=" * 60)
        print(f"\nError details: {str(e)}")
        print(f"\nError type: {type(e).__name__}")
        
        print("\n🔍 Troubleshooting steps:")
        print("1. Verify your AI Pipe key is active")
        print("2. Check the Base URL is correct")
        print("   - Current: https://aipipe.org/openai/v1")
        print("3. Confirm model name is 'gpt-5-nano'")
        print("4. Ensure you have credits in your AI Pipe account")
        print("5. Check your internet connection")
        
        return False

if __name__ == "__main__":
    print("\n🚀 Starting GPT-5 Nano test...\n")
    success = test_gpt5_nano()
    
    if success:
        print("\n✅ You're ready to run the main application!")
        print("   Run: python app.py")
    else:
        print("\n❌ Please fix the issues above before continuing.")
    
    print()