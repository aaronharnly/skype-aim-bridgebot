from collections import namedtuple
import sys
import HTMLParser

from twisted.words.protocols import oscar
from twisted.internet import protocol, reactor
import Skype4Py as skypeapi

class SkypeBot(object):
    def __init__(self, topic, message_callback):
        self._topic = topic
        self._chat = None  # will be set once we know it
        self._message_callback = message_callback
        self._skype = skypeapi.Skype()
        self._skype.OnAttachmentStatus = self._handle_attach
        self._skype.OnMessageStatus = self._handle_message_status
        self._skype.Attach()
        
    def send_message(self, text):
        if self._chat:
            self._chat.SendMessage(text)
        else:
            print "WARNING: Connection to chat room not yet established."

    def _handle_attach(self, status):
        """
        Fired on attachment status change, used to reattach in case we lose attachment.
        """
        print "Attachment status: %s" % self._skype.Convert.AttachmentStatusToText(status)
        if status == skypeapi.apiAttachAvailable:
            self._skype.Attach()
        elif status == skypeapi.apiAttachSuccess:
            print "***** Attached *****"

    def _handle_message_status(self, message, status):
        if message.Chat.Topic == self._topic and status == "RECEIVED":
            if not self._chat:
                self._chat = message.Chat
                print "Identified the chat room as: %s" % self._chat
            print "Received message: %s" % message.Body
            self._message_callback(message.FromDisplayName, message.Body)

class MLStripper(HTMLParser.HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_fed_data(self):
        return ''.join(self.fed)
        
class Cleaner(object):
    @classmethod
    def clean(cls, html):
        stripper = MLStripper()
        stripper.feed(html)
        text = stripper.get_fed_data()
        return text

class AimCredentials(namedtuple('AimCredentials', ['name', 'password'])):
    pass

def create_aim_bot(credentials, buddy, message_callback, identity_callback):
    host = 'login.oscar.aol.com'
    port = 5190

    class AimBot(oscar.BOSConnection):
        capabilities = [oscar.CAP_CHAT]

        def initDone(self):
            self.requestSelfInfo().addCallback(self._got_self_info)
            self.requestSSI().addCallback(self._got_buddy_list)
            identity_callback(self)

        def _got_self_info(self, user):
            self._name = user.name

        def _got_buddy_list(self, buddylist):
            self.activateSSI()
            self.setProfile("""I'm a bot.""")
            self.setIdleTime(0)
            self.clientReady()

        def receiveMessage(self, user, multiparts, flags):
            if user.name == buddy:
                first_part = multiparts[0][0]
                cleaned_message = Cleaner.clean(first_part).strip()
                message_callback(user.name, cleaned_message)
            
        def send_message(self, text):
            self.sendMessage(buddy, text)

        def createdRoom(self, (exchange, fullName, instance)):
            print 'created room',exchange, fullName, instance
            self.joinChat(exchange, fullName, instance).addCallback(self.chatJoined)

        def updateBuddy(self, user):
            pass

        def offlineBuddy(self, user):
            pass

        def messageAck(self, (username, message)):
            pass

        def gotAway(self, away, user):
            pass

        def receiveWarning(self, newLevel, user):
            pass

        def receiveChatInvite(self, user, message, exchange, fullName, instance, shortName, inviteTime):
            pass

        def chatJoined(self, chat):
            pass

        def chatReceiveMessage(self, chat, user, message):
            pass

        def chatMemberJoined(self, chat, member):
            pass

        def chatMemberLeft(self, chat, member):
            pass

    class AimAuthenticator(oscar.OscarAuthenticator):
        BOSClass = AimBot
       
    client = protocol.ClientCreator(reactor, AimAuthenticator, credentials.name, credentials.password, icq=0)
    client.connectTCP(host, port)
    return client

class BridgeBot(object):
    def __init__(self, aim_credentials, aim_buddy, skype_topic):
        create_aim_bot(aim_credentials, aim_buddy, self._handle_aim, self._identify_aim)
        self._aim_bot = None
        self._skype_bot = SkypeBot(skype_topic, self._handle_skype)
        reactor.run()

    def _handle_skype(self, sender, message):
        self._aim_bot.send_message("%s: %s" % (sender, message))
        
    def _identify_aim(self, bot):
        self._aim_bot = bot
        
    def _handle_aim(self, sender, message):
        self._skype_bot.send_message(message)
    
if __name__ == '__main__':
    import sys
    if len(sys.argv) != 5:
        print "Usage: <aim-username> <aim-password> <aim-buddy> <skype-chatname>"
    else:
        bot = BridgeBot(
            AimCredentials(sys.argv[1], sys.argv[2]),
            sys.argv[3],
            sys.argv[4]
        )
