# Reliable Streaming Network Transport Simulator

by Angel Hernandez (aeh5258) and David Marquette (dmm6247)

## Part 1: Chunking
Chunking is done in the `send` function. Packets are broken into segments of size 1472, appended to a staging list, and iteratively sent out via the socket connection.

## Part 2: Reordering
We maintain our order with our `buffer` and `expected` fields of the `Streamer` class. The buffer simulates a simple TCP buffer, which holds data until it is ready to be processed. We implemented this by maintaining our `self.expected` invariant. Whenever we receive a packet in the correct order, we increment `self.expected` to expect the next sequence number. Otherwise, we must retransmit the unacknowledged packet and correct `self.expected`.

## Part 3: Packet Loss (with stop and wait)
Packet loss is tolerated by adding ACKs, timeouts, and retransmissions. We accomplish this with a `listener` function; a timeout function, `timeFunc`; and a `close` function. 
### Stage A (background listener)
In stage A, we implement a background listener in the `listener` function. It runs concurrently along with the `timeFunc` time manager. Our listener receives all data from the socket, generates a hash for the the data (including ACKs and sequence numbers), and "listens" for dropped, corrupted, or out of order packets. 
### Stage B (Add ACKs)
In stage B, we implement the ability to transmit and receive acknowledgements. This is accomplished in our listener, sender, and receiver. As instructed, we added a header to our packet format in order to distinguish acknowledgements from data. Then, we added a categorizer in our listener. If the packet is an ACK, then we set the `self.ackd` flag to `True` and add the seq number to `self.inFlight`. Finally, we add code to the `close` function that waits for an ACK to consider the packet "sent."
### Stage C (Timeouts and retransmission)
Timeouts and retransmissions are handled in the `listener`, `send`, and `timeFunc` functions. A packet is said to have timed out once the timer in `close` or `timeFunc` has passed 0.25 seconds. Additionally, the `close` function closes out the connection once all acknowledgements have been received. 

## Part 4: Corruption
Our code tolerates corruption through the aforementioned hashing method. Instead of implementing checksums like real TCP/UDP, we simply add a hash of the segment data in the header and discard any received segments that do not match the hash in the header. 

## Part 5: Pipelined ACKs
Now, we implement the ability to send multiple packets at once to increase our throughput. To do so, we used additional concurrency managers. We allow the user to send consistent data, while timing the lowest in flight Un-ACK'd sequence and adding each payload to a list. Once we recieve the expected or higher ACK, we reset the timer and remove the ACK'd packets from the window. If a timeout occurs all packets in the window are reset.
