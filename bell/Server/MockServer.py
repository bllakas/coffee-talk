import socket
import datetime
import sys
import json
import queue
import select
import selectors
from DB import Database

class ClientConnection():
    def __init__(self, clientSocket:socket, database : Database) -> None:
        self.clientSocket = clientSocket;
        self.database : Database = database
        self.isLogged = False;
        self.clientID = None;
        self.OutputQueue = [];
    def acceptPacket(self)->bool:
        try:
            recv_msg = self.clientSocket.recv(1024).decode('utf-8');
        except:
            return False;
        if(recv_msg == ''):
            return
        recv_msg = json.loads(recv_msg);
        print(recv_msg)
        match recv_msg['mode']:
            case 'login':
                self.trylogin(recv_msg['id'])
            case 'register':
                self.tryRegister(recv_msg['id'],recv_msg['userName'])
            case 'send':
                self.sendMSG(recv_msg['sender_id'],recv_msg['receiver_id'],recv_msg['message'], recv_msg['date'])
            case 'request':
                self.receiveMSG(recv_msg['client_id'], recv_msg['date']);
            case 'check':
                isIdExist = self.database.isIDExist(recv_msg["check_id"]);
                recv_msg["checked"] = isIdExist
                send_msg = json.dumps(recv_msg)
                self.OutputQueue.append(send_msg);
        return True
    def receiveMSG(self, clientID, date):
        if self.isValidClient(clientID):
            data = self.database.getMessageFor(clientID, date);
            for letter in data:
                senderID = letter[0]
                message = letter[2]
                date = letter[3]#need to fix magic number problem.
                send_msg = json.dumps({'mode':'request','requested' : True ,'receiver_id' : clientID,'sender_id' : senderID, 'message' : message, 'date' : date})
                self.OutputQueue.append(send_msg);
        else:
            send_msg = json.dumps({'mode' : 'request', 'requested' : False, 'receiver_id' : clientID, 'date' : date});
            self.OutputQueue.append(send_msg);
        
            
    def sendMSG(self, senderID, receiverID, msg, date):
        isSent = False;
        if self.isValidClient(senderID) and self.database.isIDExist(receiverID):
            self.database.addMessage(senderID, receiverID, msg, date)
            isSent = True;
        else:
            pass
        send_msg = json.dumps({'mode':'send', 'sender_id': senderID, 'receiver_id' : receiverID, 'sent' : isSent, "message" : msg , 'date' : date})
        self.OutputQueue.append(send_msg);
            
    def tryRegister(self,ID,userName):
        registered=False
        if not self.database.isIDExist(ID):
            self.database.addID(ID,userName);
            registered = True;
        send_msg = json.dumps({'mode':"register","userName" : userName, "id":ID, 'registered': registered});
        self.OutputQueue.append(send_msg);
    def trylogin(self, ID):
        if self.database.isIDExist(ID):
            self.isLogged = True;
            self.clientID = ID;
        send_msg = json.dumps({'mode':'login','id': ID, 'logined' : self.isLogged})
        self.OutputQueue.append(send_msg);
    def FlushOutput(self):
        for output in self.OutputQueue:
            print(output);
            self.clientSocket.sendall(output.encode());
            self.OutputQueue.remove(output);
            
    def isValidClient(self, clientID)->bool:
        return self.isLogged and self.clientID == clientID;
def getMasterSocket():
    portNumber = 1111;
    hostname = '172.17.0.144'
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.bind((hostname, portNumber))
    serverSocket.listen(5);
    serverSocket.setblocking(False);
    return serverSocket

    
def main():
    masterSocket = getMasterSocket();
    connectionPair = {};
    inputs = [masterSocket];
    outputs = [];
    db = Database();
    def accept(sock):
        print("Accept Client.")
        conn, addr = sock.accept()
        conn.setblocking(False);
        inputs.append(conn);
        outputs.append(conn);
        clientConnection = ClientConnection(conn, db);
        connectionPair[conn] = clientConnection;
    print('Listening to host.')
    while inputs:
        readable, writable, exceptional = select.select(inputs, outputs, inputs)
        for s in readable:
            if s is masterSocket:
                accept(s);
            else:
                isAccept = connectionPair[s].acceptPacket();
                if not isAccept:
                    print("socket has problem. disconnecting socket");
                    inputs.remove(s);
                    outputs.remove(s);
                    if s in writable:
                        writable.remove(s);
                    disconnected = connectionPair.pop(s);
                    del disconnected
                    s.close();
                    
        for s in writable:
            connectionPair[s].FlushOutput()
    

if __name__ == "__main__":
    main();