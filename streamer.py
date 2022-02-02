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
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(self.listener)

    def listener(self):
        while not self.closed:  # a later hint will explain self.closed
            try:
                data, addr = self.socket.recvfrom()
                ack = data[:4]
                ack = int.from_bytes(ack, sys.byteorder)
                seq = data[4:8]
                seq = int.from_bytes(seq, sys.byteorder)
                payload = data[8:]
                self.buffer[seq] = payload
                if ack == 1:
                    self.ackd = True
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
            ack = struct.pack('i',1)
            seq = seq + 1
            p = ack + seqNum + p
            while not self.ackd: 
                time.sleep(0.01)
            self.ackd = False
            self.socket.sendto(p, (self.dst_ip, self.dst_port))
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
                    del(self.buffer[self.expected])
                    while cnt in self.buffer:
                        print("count: " + str(cnt))
                        totData += self.buffer[cnt]
                        del(self.buffer[cnt])
                        cnt += 1
                    self.expected = cnt
                    return totData





    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        # your code goes here, especially after you add ACKs and retransmissions.
        self.closed = True
        self.socket.stoprecv()
