import quickfix as fix

class Application(fix.Application):
    def onCreate(self, sessionID): pass
    def onLogon(self, sessionID): print(f"Logon: {sessionID}")
    def onLogout(self, sessionID): print(f"Logout: {sessionID}")
    def toAdmin(self, message, sessionID): pass
    def fromAdmin(self, message, sessionID): pass
    def toApp(self, message, sessionID): pass
    def fromApp(self, message, sessionID): pass

if __name__ == "__main__":
    settings = fix.SessionSettings("server.cfg")
    application = Application()
    storeFactory = fix.FileStoreFactory(settings)
    logFactory = fix.FileLogFactory(settings)
    acceptor = fix.SocketAcceptor(application, storeFactory, settings, logFactory)

    acceptor.start()
    print("FIX server started")
    input("Press <Enter> to stop...\n")
    acceptor.stop()
