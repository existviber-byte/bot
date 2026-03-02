import asyncio
import json
import logging
import websockets
from typing import Optional

log = logging.getLogger("rcon")

class RCONClient:
    def __init__(self, host, port, password):
        self.host = host
        self.port = port
        self.password = password
        self.ws_url = f"ws://{host}:{port}/{password}"
        self.connection: Optional[websockets.WebSocketClientProtocol] = None
        self.lock = asyncio.Lock()
        
    async def connect(self):
        """Установить WebSocket соединение"""
        try:
            self.connection = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10
            )
            log.info(f"✅ Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            log.error(f"❌ Connection error: {e}")
            return False
    
    async def send_command(self, command):
        """Отправить команду через WebSocket"""
        async with self.lock:
            try:
                if not self.connection:
                    success = await self.connect()
                    if not success:
                        return None
                
                payload = {
                    "Identifier": 1,
                    "Message": command,
                    "Name": "WebRcon"
                }
                
                await self.connection.send(json.dumps(payload))
                
                try:
                    response = await asyncio.wait_for(
                        self.connection.recv(), 
                        timeout=5.0
                    )
                    data = json.loads(response)
                    return data.get("Message", "")
                    
                except asyncio.TimeoutError:
                    log.warning(f"⏳ Timeout: {command[:30]}...")
                    await self.close()
                    return None
                
            except websockets.exceptions.ConnectionClosed:
                log.warning("🔌 Connection closed")
                await self.close()
                return None
                
            except Exception as e:
                log.error(f"❌ Command error: {e}")
                await self.close()
                return None
    
    async def close(self):
        """Закрыть соединение"""
        if self.connection:
            try:
                await self.connection.close()
            except:
                pass
            finally:
                self.connection = None
    
    async def is_player_online(self, steam_id):
        """Проверка, онлайн ли игрок"""
        try:
            result = await self.send_command(f"find {steam_id}")
            return result and "not found" not in result.lower()
        except:
            return False
    
    async def send_private_message(self, steam_id, player_name, message):
        """Отправить приватное сообщение с именем игрока"""
        message = message.replace('"', '\\"')
        command = f'telegram.reply "{steam_id}" "{player_name}" "{message}"'
        
        for attempt in range(2):
            result = await self.send_command(command)
            if result and "OK" in result:
                return result
            await asyncio.sleep(0.5)
        
        return None

# Конфигурация серверов
SERVERS = {
    "x5": {
        "host": "37.230.137.6",
        "rcon_port": 20602,
        "rcon_password": "Derso250499",
    },
    "x100": {
        "host": "46.174.50.248",
        "rcon_port": 20642,
        "rcon_password": "Derso250499",
    }
}

# Кэш клиентов
_rcon_clients = {}

async def get_rcon_client(server_name):
    """Получить RCON клиент"""
    if server_name not in SERVERS:
        return None
    
    if server_name in _rcon_clients:
        return _rcon_clients[server_name]
    
    cfg = SERVERS[server_name]
    client = RCONClient(cfg["host"], cfg["rcon_port"], cfg["rcon_password"])
    _rcon_clients[server_name] = client
    return client

async def close_all_connections():
    """Закрыть все соединения"""
    for client in _rcon_clients.values():
        await client.close()
    _rcon_clients.clear()