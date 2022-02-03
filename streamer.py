# do not import anything else from loss_socket besides LossyUDP
import struct
import sys
from concurrent.futures import ThreadPoolExecutor
import time

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
        self.finRecieved = False
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(self.listener)

    def listener(self):
        while not self.closed:  # a later hint will explain self.closed
            try:
                data, addr = self.socket.recvfrom()
                ack = data[:4]
                print(ack)
                ack = int.from_bytes(ack, sys.byteorder)
                seq = data[4:8]
                seq = int.from_bytes(seq, sys.byteorder)
                fin = data[8:12]
                fin = int.from_bytes(fin, sys.byteorder)
                print(str(ack) + " and " + str(seq))
                if ack in self.inFlight:
                    self.ackd = True
                    self.inFlight.remove(ack)
                    continue
                if fin == 1:
                    self.finRecieved = True
                payload = data[12:]
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
        seq = self.seqA
        for p in packets:
            seqNum = struct.pack('i', seq)
            ack = struct.pack('i',0)
            fin = struct.pack('i',0)
            seq = seq + 1
            p = ack + seqNum + fin + p
            self.inFlight.append(seq-1) 
            self.socket.sendto(p, (self.dst_ip, self.dst_port))
            start = time.time()
            while not self.ackd:
                if (time.time()-start) >= 0.25:
                    self.socket.sendto(p, (self.dst_ip, self.dst_port))
                time.sleep(0.01)
            self.ackd = False
        self.seqA = seq

    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        # your code goes here!  The code below should be changed!

        # this sample code just calls the recvfrom method on the LossySocket
        while len(self.buffer) == 0:
            pass
        while len(self.buffer) != 0:
            if self.expected in self.buffer:
                    cnt = self.expected + 1
                    totData = self.buffer[self.expected]
                    seqNum = struct.pack('i', 1)
                    ack = struct.pack('i',cnt-1)
                    p = ack + seqNum
                    self.socket.sendto(p, (self.dst_ip, self.dst_port))
                    print('sent back ack of: ' + str(cnt-1))
                    del(self.buffer[self.expected])
                    while cnt in self.buffer:
                        print("count: " + str(cnt))
                        totData += self.buffer[cnt]
                        totData = self.buffer[self.expected]
                        seqNum = struct.pack('i', 1)
                        ack = struct.pack('i',cnt)
                        p = ack + seqNum
                        self.socket.sendto(p, (self.dst_ip, self.dst_port))
                        print('sent2')
                        del(self.buffer[cnt])
                        cnt += 1
                    self.expected = cnt
                    return totData
            if self.finRecieved:
                seqNum = struct.pack('i', 1)
                ack = struct.pack('i',self.expected)
                fin = struct.pack('i', 1)
                p = ack + seqNum + fin
                self.socket.sendto(p, (self.dst_ip, self.dst_port))
                print('sent back ack of: ' + str(self.expected))





    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        # your code goes here, especially after you add ACKs and retransmissions.
        print("WE IN THE END GAME")
        while len(self.inFlight) != 0:
            print(self.inFlight)
            time.sleep(0.01)
            print()
        seqNum = struct.pack('i', self.seqA)
        ack = struct.pack('i',0)
        fin = struct.pack('i',1)
        p = ack + seqNum + fin
        self.socket.sendto(p, (self.dst_ip, self.dst_port))
        self.inFlight.append(self.seqA)
        start = time.time()
        while not self.finRecieved:
            if time.time()-start > 0.25:
                self.socket.sendto(p, (self.dst_ip, self.dst_port))
            time.sleep(0.1)
        start = time.time()
        while time.time()-start < 2:
            pass

        self.closed = True
        self.socket.stoprecv()
        return
