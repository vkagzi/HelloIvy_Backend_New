"""
Stream & Subject Selection WebSocket Routing

The legacy ws/domain-discovery/realtime/ endpoint has been removed.
Use the unified endpoint instead: ws/voice/realtime/?feature=domain-discovery&session_id=<uuid>
"""
websocket_urlpatterns = []
