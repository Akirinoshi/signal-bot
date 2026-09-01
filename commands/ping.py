from signalbot import DataMessageContext, DataMessageHandler, SendMessage, text_triggered


class PingCommand(DataMessageHandler):
    @text_triggered("ping")
    async def handle_data_message(self, c: DataMessageContext):
        await c.send(SendMessage(text="pong"))