# do not import anything else from loss_socket besides LossyUDP
import struct
import sys
from concurrent.futures import ThreadPoolExecutor
from tabnanny import check
import time
import hashlib

from numpy import real

from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY


class Streamer:
    def __init__(self, dst_ip, dst_port,
                 src_ip=INADDR_ANY, src_port=0):
        """Default values listen on all network interfaces, chooses a random source port,
           and does not introduce any simulated packet loss."""
        self.socket = LossyUDP()
        self.socket.bind((src_ip, src_port))
        self.dst_ip = dst_ip
        self.dst_port = dst_port
        self.buffer = {}
        self.expected = 1
        self.seqA = 1
        self.closed = False
        self.ackd = False
        self.inFlight = []
        self.window = []
        self.finRecieved = False
        self.timer = time.time()
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(self.listener)

    def listener(self):
        while not self.closed:  # a later hint will explain self.closed
            try:
                
                data, addr = self.socket.recvfrom()
                realHash = data[12:28]
                payload = data[28:]
                
                
                ack = data[:4]
                seq = data[4:8]
                fin = data[8:12]

                m = hashlib.md5()
                m.update(ack)
                m.update(seq)
                m.update(fin)
                m.update(payload)
                recvHash = m.digest()
                print("SIZE: " + str(m.digest_size))
                print("RECIEVED HASH: " + str(recvHash))
                print("REAL HASH: " + str(realHash))
                ack = int.from_bytes(ack, sys.byteorder)
                
                seq = int.from_bytes(seq, sys.byteorder)
                
                fin = int.from_bytes(fin, sys.byteorder)
                if str(recvHash) != str(realHash):
                    print("ERROR DETECTED, DISCARDING PACKET")
                    continue
                print(str(ack) + " and " + str(seq))
                #takes care of ACKs that are dropped, if packets seq is lower than the lowest un-ACK'd value the sender never got our ack and is asking again
                if seq < self.expected and ack == 0 and fin == 0:
                    print("was expecting " + str(self.expected) + " and got " + str(seq))
                    seqNum = struct.pack('i', 1)
                    ack = struct.pack('i', seq)
                    fin = struct.pack('i',0)
                    m = hashlib.md5()
                    m.update(ack)
                    m.update(seqNum)
                    m.update(fin)
                    checkHash = m.digest()
                    p = ack + seqNum + fin + checkHash
                    self.socket.sendto(p, (self.dst_ip, self.dst_port))
                    print('sent back ack of: ' + str(seq))
                    continue
                #Checks if this ack is for one of our packets that have been sent but not ack'd, if so sets ackd to true and removes it from the inflight packets
                if ack in self.inFlight:
                    self.ackd = True
                    self.inFlight.remove(ack)
                    continue
                #Checks fin flag, only triggered when close called
                if fin == 1:
                    self.finRecieved = True
                #Only want to add packets that aren't ack's to our buffer
                if ack == 0:
                    print("Adding "+str(seq) + " to the payload")
                    self.buffer[seq] = payload
                    
            except Exception as e:
                print("listener died!")
                print(e)

    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""
        # Your code goes here!  The code below should be changed!
        packets = []
        #print(data_bytes)
        while sys.getsizeof(data_bytes) > 1472:
            new_seg = list()
            for i, item in enumerate(data_bytes):
                if sys.getsizeof(bytes(new_seg)) + sys.getsizeof(item) > 1472:
                    #print("New seg size: " + str(sys.getsizeof(bytes(new_seg))))
                    #print("Item pushed over: " + str(item) + " Size: " + str(bytes(sys.getsizeof(item))))
                    data_bytes = data_bytes[i:]
                    break
                new_seg.append(item)
            new_seg = bytes(new_seg)
            packets.append(new_seg)

        if sys.getsizeof(data_bytes) != 0:
            packets.append(data_bytes)


        # for now I'm just sending the raw application-level data in one UDP payload
        #Loop though all packets, set current seq to our selfs tracker of the lowest unused seq number
        seq = self.seqA
        for p in packets:
            seqNum = struct.pack('i', seq)
            ack = struct.pack('i',0)
            fin = struct.pack('i',0)
            m = hashlib.md5()
            m.update(ack)
            m.update(seqNum)
            m.update(fin)
            m.update(p)
            checkHash = m.digest()
            seq = seq + 1
            #m = hashlib.md5()
            #m.update(p)
            #hashe = struct.pack('s',m.digest())
            p = ack + seqNum + fin + checkHash + p
            self.inFlight.append(seq-1) 
            self.socket.sendto(p, (self.dst_ip, self.dst_port))
            self.timer = time.time()
            if time.time() - self.timer >= 0.60:
                for item in self.window:
                    self.socket.sendto(item, (self.dst_ip, self.dst_port))
            else:
                self.window.append(p)
                
            #Wait for the listener to recieve an ACK, if .60 seconds pass then retransmit
            while not self.ackd:
                print("yes im stuck in this loop")
                print(self.inFlight)
                if (time.time()-start) >= 0.60:
                    self.socket.sendto(p, (self.dst_ip, self.dst_port))
                    start = time.time()
                time.sleep(0.01)
            self.ackd = False
        #Update seqA to be where we left off
        self.seqA = seq

    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        # your code goes here!  The code below should be changed!

        # this sample code just calls the recvfrom method on the LossySocket
        #wait till data is available
        while len(self.buffer) == 0:
            pass
        #continue as long as data is available
        while not self.finRecieved:
            print("CURRENT BUFFER: " + str(self.buffer))
            #print("CURRENT EXPECTED: " + str(self.expected))
            if self.expected in self.buffer:
                    self.timer = time.time()
                    cnt = self.expected + 1
                    print("CURRENT SEQ IT FOUND IN BUFFER: " + str(cnt))
                    
                    totData = self.buffer[self.expected]
                    seqNum = struct.pack('i', 1)
                    ack = struct.pack('i',cnt-1)
                    fin = struct.pack('i', 0)
                    m = hashlib.md5()
                    m.update(ack)
                    m.update(seqNum)
                    m.update(fin)
                    checkHash = m.digest()
                    p = ack + seqNum + fin + checkHash
                    self.socket.sendto(p, (self.dst_ip, self.dst_port))
                    print('sent back ack of: ' + str(cnt-1))
                    del(self.buffer[self.expected])
                    while cnt in self.buffer:
                        print("count: " + str(cnt))
                        totData += self.buffer[cnt]
                        seqNum = struct.pack('i', 1)
                        ack = struct.pack('i',cnt)
                        fin = struct.pack('i', 0)
                        m = hashlib.md5()
                        m.update(ack)
                        m.update(seqNum)
                        m.update(fin)
                        checkHash = m.digest()
                        p = ack + seqNum + fin + checkHash
                        self.socket.sendto(p, (self.dst_ip, self.dst_port))
                        print('sent2')
                        del(self.buffer[cnt])
                        cnt += 1
                    self.expected = cnt
                    return totData
        #Need to be able to send a fin ACK back once weve recived it
        if self.finRecieved:
            print("FIN HAS BEEN RECIEVED")
            seqNum = struct.pack('i', 1)
            ack = struct.pack('i',self.expected)
            fin = struct.pack('i', 1)
            m = hashlib.md5()
            m.update(ack)
            m.update(seqNum)
            m.update(fin)
            checkHash = m.digest()
            p = ack + seqNum + fin + checkHash
            self.socket.sendto(p, (self.dst_ip, self.dst_port))
            print('sent back ack of: ' + str(self.expected))





    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        # your code goes here, especially after you add ACKs and retransmissions.
        while len(self.inFlight) != 0:
            print(self.inFlight)
            time.sleep(0.01)
        seqNum = struct.pack('i', self.seqA)
        ack = struct.pack('i',0)
        fin = struct.pack('i',1)
        p = ack + seqNum + fin
        self.socket.sendto(p, (self.dst_ip, self.dst_port))
        self.inFlight.append(self.seqA)
        start = time.time()
        #After we've sent the fin we have to wait for our listener to get an ACK FIN back
        while not self.finRecieved:
            if time.time()-start > 0.25:
                self.socket.sendto(p, (self.dst_ip, self.dst_port))
                start = time.time()
            time.sleep(0.1)
        start = time.time()
        while time.time()-start < 2:
            pass

        self.closed = True
        self.socket.stoprecv()
        return
