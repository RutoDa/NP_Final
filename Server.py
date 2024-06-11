import pickle
import random
import socket
import struct
import threading
import time
import select


# 將老師傳送過來的影音群播給所有在教室中的學生
def classroom(classroom_info):
    global HOST, BUFF_SIZE, MULTICAST_GROUP, USED_PORT
    recv_sock = dict()
    send_sock = dict()
    for stream_type in ['screenshot', 'camera', 'audio', 'message']:
        # the socket recv teacher stream
        recv_sock[stream_type] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        recv_sock[stream_type].setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        recv_sock[stream_type].setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
        #recv_sock[stream_type].setblocking(False)
        recv_sock[stream_type].bind((HOST, classroom_info[f'{stream_type}_port']))
        # the socket multicast to student
        send_sock[stream_type] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        send_sock[stream_type].setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ttl = struct.pack('b', 1)  # 设置TTL（生存时间）
        send_sock[stream_type].setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        send_sock[stream_type].setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
        #send_sock[type].setblocking(False)
        #print(recv_sock[stream_type], send_sock[stream_type])
    try:
        while True:
            time.sleep(0.001)
            # for stream_type in ['screenshot', 'camera', 'audio', 'message']:
            #     packet, _ = recv_sock[stream_type].recvfrom(BUFF_SIZE)
            #     if len(packet) > 0:
            #         print("ok")
            #         send_sock[stream_type].sendto(b'hi', (MULTICAST_GROUP, classroom_info[f'{stream_type}_port']))

            readable, _, _ = select.select(list(recv_sock.values()), [], [], 0.1)
            for sock in readable:
                for stream_type, r_sock in recv_sock.items():
                    if sock is r_sock:

                        packet, _ = r_sock.recvfrom(BUFF_SIZE)
                        if len(packet) > 0:
                            #print("ok")
                            send_sock[stream_type].sendto(packet,
                                                          (MULTICAST_GROUP, classroom_info[f'{stream_type}_port']))

    except Exception as e:
        print(e)
    finally:
        for sock in list(recv_sock.values()) + list(send_sock.values()):
            sock.close()
        for stream_type in ['screenshot', 'camera', 'audio', 'message']:
            USED_PORT.remove(classroom_info[f'{stream_type}_port'])


HOST = '127.0.0.1'
MULTICAST_GROUP = '224.1.1.1'
PORT = 7777
BUFF_SIZE = 65536

CLASSROOMS = dict()
threads = dict()
USED_PORT = [7777]


# 負責老師建立教室和學生加入教室的功能
# 回應上線名單和文字傳遞
if __name__ == '__main__':
    # 開啟一個 TCP socket 用來監聽服務
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)

    # 將 Socket 綁定到指定的 IP 跟 PORT 上
    s.bind((HOST, PORT))
    # 等待client連入，等待區空間為5，超過時則拒絕
    s.listen(10)

    while True:
        conn, addr = s.accept()
        data = conn.recv(BUFF_SIZE)
        client_request = pickle.loads(data)
        print(client_request)

        if client_request.get('action', 0) == 'create_room':
            classroom_info = client_request
            while True:
                room_number = random.randint(1000, 9000)
                for num in [room_number + i for i in range(4)]:
                    if num in USED_PORT:
                        continue
                break
            classroom_info['screenshot_port'] = room_number
            classroom_info['camera_port'] = room_number + 1
            classroom_info['audio_port'] = room_number + 2
            classroom_info['message_port'] = room_number + 3
            classroom_info['room_num'] = str(room_number)
            classroom_info['students'] = dict()
            USED_PORT += [room_number + i for i in range(4)]
            CLASSROOMS[str(room_number)] = classroom_info
            conn.send(pickle.dumps(classroom_info))
            threads[room_number] = threading.Thread(target=classroom, args=(classroom_info,))
            threads[room_number].start()
            #print(CLASSROOMS)
        elif client_request.get('action', 0) == 'join_room':
            room_number = client_request.get('room_num', 0)
            if CLASSROOMS.get(room_number, 0):
                CLASSROOMS[room_number]['students'][client_request.get('student_id')] = \
                    {'name': client_request.get('student_name'),
                     'join_time': time.localtime()}
                conn.send(pickle.dumps(CLASSROOMS[room_number]))
            else:
                conn.send(pickle.dumps({'msg': 'room not found'}))
        elif client_request.get('action', 0) == 'send_message':
            room_number = client_request.get('room_num', 0)
            msg_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            msg_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            ttl = struct.pack('b', 1)
            msg_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
            msg_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
            msg_sock.sendto(pickle.dumps(client_request)
                            , (MULTICAST_GROUP, CLASSROOMS[room_number][f'message_port']))
            msg_sock.close()
            pass
        elif client_request.get('action', 0) == 'leave_room':
            room_number = client_request.get('room_num')
            student_id = client_request.get('student_id')
            del CLASSROOMS[room_number]['students'][student_id]
        elif client_request.get('action', 0) == 'request_student_list':
            room_number = client_request.get('room_num', 0)
            conn.send(pickle.dumps(CLASSROOMS[room_number]['students']))

        conn.close()


