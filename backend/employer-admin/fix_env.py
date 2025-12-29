content = """MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=yuvasetu
FIREBASE_SERVICE_ACCOUNT_PATH=yuvasetu-employer-firebase-adminsdk-fbsvc-f7399ddf87.json
FIREBASE_ADMIN_SERVICE_ACCOUNT_PATH=yuvasetu-admin-firebase-adminsdk.json
"""
with open('.env', 'w', encoding='utf-8') as f:
    f.write(content)
print("Rewrote .env with utf-8 encoding (no BOM)")
