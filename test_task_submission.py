"""
Test task submission to local API
"""
import requests
import json
import time

def test_task_submission():
    """Submit a test task to the API"""
    
    # Your API endpoint
    url = "http://localhost:7860/task"
    
    # Test task payload
    payload = {
        "email": "test@example.com",
        "task": "test-hello-world",
        "round": 1,
        "nonce": f"test-{int(time.time())}",
        "brief": "Create a simple HTML page with Bootstrap 5. Add a heading with id='main-heading' that says 'Hello World from TDS'. Include a blue button with id='test-button' that shows an alert when clicked.",
        "attachments": [],
        "checks": [
            {"js": "document.getElementById('main-heading').textContent.includes('Hello World')"},
            {"js": "document.getElementById('test-button') !== null"},
            {"js": "document.querySelector('link[href*=\"bootstrap\"]') !== null"}
        ],
        "evaluation_url": "https://httpbin.org/post",
        "endpoint": "http://localhost:7860/task",
        "secret": "krishna@tds_project_1"  # REPLACE with your actual SECRET from .env
    }
    
    print("=" * 60)
    print("Testing Task Submission")
    print("=" * 60)
    print(f"\nSubmitting task: {payload['task']}")
    print(f"Nonce: {payload['nonce']}")
    
    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        
        print(f"\n✅ Response Status: {response.status_code}")
        print(f"\n📝 Response Body:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            print("\n✅ Task accepted! Processing in background...")
            print("\nCheck the app.py terminal to see processing logs.")
            
            # Wait a bit and check status
            nonce = payload['nonce']
            time.sleep(5)
            
            print(f"\n🔍 Checking task status...")
            status_response = requests.get(f"http://localhost:7860/status/{nonce}")
            if status_response.status_code == 200:
                print(f"\n📊 Task Status:")
                print(json.dumps(status_response.json(), indent=2))
            
            return True
        else:
            print(f"\n❌ Task submission failed!")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("\n🚀 Starting task submission test...\n")
    success = test_task_submission()
    
    if success:
        print("\n✅ Test completed!")
        print("\nNext steps:")
        print("1. Check the app.py terminal for processing logs")
        print("2. Check your GitHub account for a new repository")
        print("3. The repo should be named: tds-test-hello-world-round1-...")
    else:
        print("\n❌ Test failed. Check the logs above.")
    
    print()