# FIXversion: 4.2
# Language: Python 3.9

import quickfix as fix
from quickfix import Application, SessionID, Message

class Application(_Object):
    def onCreate(self, sessionID):
        return
    
    def onLogon(self, sessionID):
        return
    
    def onLogout(self, sessionID):
        return
    
    def toAdmin(self, message, sessionID):
        return
    
    def fromAdmin(self, message, sessionID):
        return
    
    def toApp(self, message, sessionID):
        return
    
    def fromApp(self, message, sessionID):
        return
    

