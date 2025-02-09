# FIXversion: 4.2
# Language: Python 3.9

import sys
import os
import argparse
import quickfix as fix
import quickfix42 as fix42
import logging, random
import time
from datetime import datetime
import asyncio

# Set up logging
logging.basicConfig(
    filename="log/fix_client.log",  # Check if this is pointing to the right file
    level=logging.DEBUG,  # Make sure logging captures DEBUG messages
    format="%(asctime)s - %(levelname)s - %(message)s"
    )

logger = logging.getLogger(__name__)

class Application(fix.Application):
    def __init__(self, settings):
        super().__init__()
        self.sessionID = None
        self.session_settings = settings
        self._client_str = "CLIENT"
        self._server_str = "SERVER"

    def onCreate(self, sessionID):
        self.sessionID = sessionID
        self.logger = logging.getLogger(f"{self.__class__.__name__}.{sessionID.toString()}")
    
    def onLogon(self, sessionID):
        self.logger.info(f"Logon: {sessionID}")
        self.connected = True
        self.sessionID = sessionID
    
    def onLogout(self, sessionID):
        self.logger.info(f"Logout: {sessionID}")
        print(f"Logout: {sessionID}")
        if sessionID == self.sessionID:
            self.connected = False
            self.sessionID = None
    
    def toAdmin(self, message, sessionID):
        self.logger.info(f"{self._client_str} {sessionID} {message}")
        msgType = fix.MsgType()
        message.getHeader().getField(msgType)
    
    def fromAdmin(self, message, sessionID):
        self.logger.info(f"{self._server_str} {sessionID} {message}")
        print(f"{self._server_str} {sessionID} {message}")

    def toApp(self, message, sessionID):
        self.logger.info(f"{self._client_str} {sessionID} {message}")
        print(f"{self._client_str} {sessionID} {message}")
        fix_str = message.toString().replace("\x01", "|")
        print(f"Sending message: {fix_str}")
    
    def fromApp(self, message, sessionID):
        self.logger.info(f"{self._server_str} {sessionID} {message}")
        
        msgType = fix.MsgType()
        message.getHeader().getField(msgType)
        message_type_value = msgType.getValue()

        raw_fix_msg = message.toString().replace("\x01", "|")
        logger.info(f"Received Message: {raw_fix_msg}")

        if message_type_value == fix.MsgType_Heartbeat:
            logger.info("Heartbeat received.")

        if msgType.getValue() == fix.MsgType_ExecutionReport:
            logger.info(f"Execution Report received: {message}")
            
            if message.isSetField(fix.AvgPx()):
                avg_px = message.getField(fix.AvgPx())
                logger.info(f"Average price: {avg_px}")
            else:
                logger.error("Average price not found in execution report")

        elif msgType.getValue() == fix.MsgType_OrderCancelReject:
            logger.error(f"Order Cancel Reject received: {message}")
        elif msgType.getValue() == fix.MsgType_Reject:
            logger.warning(f"Reject received: {message}")
        else:
            logger.debug(f"Received message: {message_type_value} {message}")

    def orderGeneratorandSender(self):
        if self.sessionID is None:
            print("No session ID found")
            return
        
        SIDE_MAP = {
            fix.Side_BUY: "BUY",
            fix.Side_SELL: "SELL",
            fix.Side_SELL_SHORT: "SELL SHORT",
            }
        
        tickers = ["MSFT", "AAPL", "BAC"]
        sides = [fix.Side_BUY, fix.Side_SELL, fix.Side_SELL_SHORT]

        ticker = random.choice(tickers)
        side = random.choice(sides)
        order_type = random.choice([fix.OrdType_LIMIT, fix.OrdType_MARKET])
        price = random.uniform(100, 200) if order_type == fix.OrdType_LIMIT else None
        quantity = random.randint(1, 100)

        order_id = str(random.randint(1, 100000))

        # Creating new order single message
        message = fix42.NewOrderSingle()
        header = message.getHeader()
        header.setField(fix.BeginString("FIX.4.2"))

        sender_comp_id = self.session_settings.get(self.sessionID).getString("SenderCompID")
        target_comp_id = self.session_settings.get(self.sessionID).getString("TargetCompID")
        
        header.setField(fix.SenderCompID(sender_comp_id))
        header.setField(fix.TargetCompID(target_comp_id))
        header.setField(fix.MsgType(fix.MsgType_NewOrderSingle))

        # Set order fields
        message.setField(fix.ClOrdID(order_id))
        message.setField(fix.Symbol(ticker))
        message.setField(fix.Side(side))
        message.setField(fix.OrderQty(quantity))
        message.setField(fix.OrdType(order_type))
        message.setField(fix.TimeInForce(fix.TimeInForce_DAY))
        message.setField(fix.HandlInst("1")) # Automated execution order
        message.setField(fix.TransactTime())
        message.setField(fix.ExecInst("0"))  # Default execution instruction

        if price:
            message.setField(fix.Price(price))

        try:
            fix.Session.sendToTarget(message, self.sessionID)
            logger.info(f"Sent {SIDE_MAP.get(side, side)} order for {quantity} {ticker} at {price if price else 'market'})")
            return order_id
        except fix.SessionNotFound:
            logger.error("Session not found")
            return

    def cancelOrder(self, order_id):
        if self.sessionID is None:
            logger.error("No session ID found")
            return
        
        message = fix42.OrderCancelRequest()
        header = message.getHeader()
        header.setField(fix.BeginString("FIX.4.2"))

        sender_comp_id = self.session_settings.get(self.sessionID).getString("SenderCompID")
        target_comp_id = self.session_settings.get(self.sessionID).getString("TargetCompID")

        header.setField(fix.SenderCompID(sender_comp_id))
        header.setField(fix.TargetCompID(target_comp_id))
        header.setField(fix.MsgType(fix.MsgType_OrderCancelRequest))

        ticker = random.choice(["MSFT", "AAPL", "BAC"])
        side = random.choice([fix.Side_BUY, fix.Side_SELL, fix.Side_SELL_SHORT])

        message.setField(fix.ClOrdID(str(random.randint(1, 100000))))
        message.setField(fix.OrigClOrdID(order_id))
        message.setField(fix.Symbol(ticker))
        message.setField(fix.Side(side))
        message.setField(fix.TransactTime())

        try:
            fix.Session.sendToTarget(message, self.sessionID)
            logger.info(f"Cancel order sent for {order_id}")
            
        except fix.SessionNotFound:
            logger.error("Session not found")

    def sendOrderWindow(self):
        start_time = time.time()
        orders = []
        order_count = 0

        try:
            while time.time() - start_time < 300: # 5-minute window
                if order_count >= 25:
                    logger.info(f"Order limit reached: {order_count}")
                    break

                order_id = self.orderGeneratorandSender()
                if order_id:
                    orders.append(order_id) # track order IDs
                    order_count += 1

                if random.random() < 0.1 and orders and order_count < 25: 
                    cancel_id = random.choice(orders)
                    self.cancelOrder(order_id=cancel_id)
                    orders.remove(cancel_id)

                time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error: {e}")

    # async methods for sending orders and cancelling orders concurrently
    """async def asyncOrderSender(self, orders):
        tasks = [asyncio.to_thread(self.orderGeneratorandSender) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        for order_id in results:
            if order_id:
                orders.append(order_id)

    async def asyncCancelOrder(self, orders):
        if orders:
            cancel_id = random.choice(orders)
            self.cancelOrder(order_id=cancel_id)
            orders.remove(cancel_id)

    async def sendOrderWindow(self):
        start_time = time.time()
        orders = []

        try:
            while time.time() - start_time < 300:  # 5-minute window
                tasks = []

                if len(orders) < 1000:
                    tasks.append(asyncio.create_task(self.asyncOrderSender(orders)))

                if random.random() < 0.1 and orders:
                    tasks.append(asyncio.create_task(self.asyncCancelOrder(orders)))

                if tasks:
                    await asyncio.gather(*tasks)  # Run multiple tasks concurrently

                await asyncio.sleep(0.1)  # Small delay for efficiency
        except Exception as e:
            print(f"Error: {e}")"""

if __name__ == "__main__":
    if len(sys.argv) < 2: 
        print("Usage: client.py <config_file>")
        sys.exit(1)

    configFileName = sys.argv[1]

    if not os.path.exists(configFileName):
            print(f"Configuration File {configFileName} not found")
            sys.exit(1)

    try:
        settings = fix.SessionSettings(configFileName)
        application = Application(settings)
        storeFactory = fix.FileStoreFactory(settings)
        logFactory = fix.FileLogFactory(settings)
        initiator = fix.SocketInitiator(application, storeFactory, settings, logFactory)
        
        initiator.start()
        
        print("FIX client started")    
        start = time.time()
        # asyncio.run(application.sendOrderWindow())
        application.sendOrderWindow()
        end = time.time()
        print(f"Orders sent in {end - start} seconds")
    except KeyboardInterrupt:
        print("Shutting down FIX client")
        initiator.stop()
    except fix.ConfigError as e:
        print(f"ConfigError: {e}")
        sys.exit()