import json
from collections import namedtuple

def decodeJson(data):
    return json.loads(data, object_hook=_json_object_hook)
def _json_object_hook(d): return namedtuple('X', d.keys())(*d.values())

def encode(object):
    return json.dumps(object, default=lambda o: o.__dict__, 
        sort_keys=False, indent=4)

class Request:
    requestNumber = 1

    def __init__(self, date, time, minimum, listParticipant, topic, requestClientName):
        self.type = "Request"
        self.requestNumber = Request.requestNumber
        Request.requestNumber = Request.requestNumber + 1
        self.date = date
        self.time = time
        self.minimum = minimum
        self.participant = listParticipant
        self.topic = topic
        self.requestClientName = requestClientName


class Response:
    def __init__(self, requestNumber, clientName, reason):
        self.type = "Response"
        self.requestNumber = requestNumber
        self.requesterName = clientName
        self.reason = reason

class Invite:
    meetingNumber = 1

    def __init__(self, date,time, topic, requesterIP, requesterName, clientName="defaultUser"):
        self.type = "Invite"
        self.meetingNumber = Invite.meetingNumber
        Invite.meetingNumber = Invite.meetingNumber + 1
        self.date = date
        self.time = time
        self.topic = topic
        self.requesterIP = requesterIP
        self.requesterName = requesterName
        self.targetName = clientName

class Accept:
    def __init__(self, meetingNumber, clientName):
        self.type = "Accept"
        self.meetingNumber = meetingNumber
        self.clientName = clientName

class Reject:
    def __init__(self, meetingNumber, clientName):
        self.type = "Reject"
        self.meetingNumber = meetingNumber
        self.clientName = clientName

class Withdraw:
    def __init__(self, meetingNumber):
        self.type = "Withdraw"
        self.meetingNumber = meetingNumber

class Confirm:
    def __init__(self, room):
        self.type = "Confirm"
        self.room = room

class Scheduled:
    def __init__(self, requestNumber, meetingNumber, room, listConfirmedParticipant):
        self.type = "Scheduled"
        self.requestNumber = requestNumber
        self.meetingNumber = meetingNumber
        self.room = room
        self.listConfirmedParticipant = listConfirmedParticipant

class Cancel:
    def __init__(self, room, reason = ''):
        self.type = "Cancel"
        self.room = room
        self.reason = reason

class Non_Scheduled:
    def __init__(self, requestNumber, meetingNumber, room, listConfirmedParticipant):
        self.type = "Non_Scheduled"
        self.requestNumber = requestNumber
        self.meetingNumber = meetingNumber
        self.room = room
        self.listConfirmedParticipant = listConfirmedParticipant

'''
#r = Request("test","test","test","test","test")
#print(r.requestNumber)
r2 = Request("test","test","test",["test", "test2"],"test")
print(r2.requestNumber)

print(encode(r2))
t = encode(r2)

print(decodeJson(t))
t2 = decodeJson(t)
print(t2.participant)
'''