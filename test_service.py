# test_service_integration.py
import sys
import os
sys.path.append(os.getcwd())

from app.services.chat_service import chat_service
import asyncio

async def test_chat_service():
    print("Testing ChatService integration...")
    
    try:
        response = await chat_service.process_chat_message(
            message="Hello",
            tenant_id="6875f3afc8337606d54a7f37",
            session_id=None
        )
        print(f"✓ ChatService response: {response}")
        
    except Exception as e:
        print(f"✗ ChatService failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chat_service())