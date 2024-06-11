import base64
import cv2
import socket
import struct
import pickle
import sys
import numpy as np
import pyaudio
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5 import uic
import time
from ui.Style import *

BUFF_SIZE = 65536
STUDENT_ID = ''
STUDENT_NAME = ''
SERVER_IP = '127.0.0.1'
MULTICAST_GROUP = '224.1.1.1'
CLASSROOM_INFO = dict()
SERVER_ADDRESS = (SERVER_IP, 7777)


class ScreenshotReceiveThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)

    def run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
        ttl = struct.pack('b', 1)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        self.sock.bind(('', CLASSROOM_INFO['screenshot_port']))
        group = socket.inet_aton(MULTICAST_GROUP)
        mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        while True:
            time.sleep(0.001)
            packet, _ = self.sock.recvfrom(BUFF_SIZE)
            data = base64.b64decode(packet, " /")
            npdata = np.fromstring(data, dtype=np.uint8)
            frame = cv2.imdecode(npdata, 1)
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.change_pixmap_signal.emit(qt_image)

        self.sock.close()
        #conn.close()

class CameraReceiveThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)

    def run(self):

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
        ttl = struct.pack('b', 1)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        self.sock.bind(('', CLASSROOM_INFO['camera_port']))
        group = socket.inet_aton(MULTICAST_GROUP)
        mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)


        while True:
            time.sleep(0.001)
            packet, _ = self.sock.recvfrom(BUFF_SIZE)
            data = base64.b64decode(packet, " /")
            npdata = np.fromstring(data, dtype=np.uint8)
            frame = cv2.imdecode(npdata, 1)
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.change_pixmap_signal.emit(qt_image)

        self.sock.close()
        #conn.close()

class AudioReceiveThread(QThread):
    def run(self):
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 20000

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
        ttl = struct.pack('b', 1)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        self.sock.bind(('', CLASSROOM_INFO['audio_port']))
        group = socket.inet_aton(MULTICAST_GROUP)
        mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        audio = pyaudio.PyAudio()
        stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)
        print("Audio streaming started...")

        while True:
            time.sleep(0.001)
            data, _ = self.sock.recvfrom(BUFF_SIZE)
            stream.write(data)

        stream.stop_stream()
        stream.close()
        audio.terminate()


class RequestStudentListThread(QThread):
    change_student_list_signal = pyqtSignal(dict)
    def run(self):
        global CLASSROOM_INFO
        while True:
            time.sleep(5)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(SERVER_ADDRESS)
            data = pickle.dumps({
                'action': 'request_student_list',
                'room_num': str(CLASSROOM_INFO['room_num']),
            })
            sock.sendall(data)
            recv_data = sock.recv(BUFF_SIZE)
            sock.close()
            student_list = pickle.loads(recv_data)
            print(student_list)
            self.change_student_list_signal.emit(student_list)


class RecvMsgThread(QThread):
    update_chatroom_signal = pyqtSignal(dict)
    def run(self):
        global CLASSROOM_INFO
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
        ttl = struct.pack('b', 1)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        self.sock.bind(('', CLASSROOM_INFO['message_port']))
        group = socket.inet_aton(MULTICAST_GROUP)
        mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        while True:
            time.sleep(0.001)
            data, _ = self.sock.recvfrom(BUFF_SIZE)
            data = pickle.loads(data)
            self.update_chatroom_signal.emit(data)

        self.sock.close()


class JoinRoomWindow(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi('ui/join_room.ui', self)
        self.setWindowTitle("加入教室")
        self.join_room_button.clicked.connect(self.join_room)
        self.setStyleSheet(JOIN_ROOM_WIDGET_STYLE)
        self.join_room_button.setStyleSheet(JOIN_ROOM_BUTTON_STYLE)
        self.label_title.setStyleSheet(ROOM_TITLE_LABEL_STYLE)
        self.room_number_label.setStyleSheet(JOIN_ROOM_NUMBER_LABEL_STYLE)
        self.room_number_input.setStyleSheet(JOIN_ROOM_NUMBER_INPUT_STYLE)
        self.student_id_label.setStyleSheet(JOIN_ROOM_STUDENT_ID_LABEL_STYLE)
        self.student_id_input.setStyleSheet(JOIN_ROOM_STUDENT_ID_INPUT_STYLE)
        self.student_name_label.setStyleSheet(JOIN_ROOM_STUDENT_NAME_LABEL_STYLE)
        self.student_name_input.setStyleSheet(JOIN_ROOM_STUDENT_NAME_INPUT_STYLE)


    def join_room(self):
            global CLASSROOM_INFO, STUDENT_ID, STUDENT_NAME
            room_number = self.room_number_input.toPlainText()
            STUDENT_ID = self.student_id_input.toPlainText()
            STUDENT_NAME = self.student_name_input.toPlainText()

            request = {'action': 'join_room', 'room_num': room_number, 'student_name': STUDENT_NAME, 'student_id': STUDENT_ID}
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(SERVER_ADDRESS)
            data = pickle.dumps(request)
            sock.sendall(data)
            recv_data = sock.recv(BUFF_SIZE)
            sock.close()

            CLASSROOM_INFO = pickle.loads(recv_data)
            print(CLASSROOM_INFO)

            if CLASSROOM_INFO.get('msg') == 'room not found':
                QMessageBox.warning(self, '查無此教室', '找不到此教室，請確認教室代碼是否有誤!')
            else:
                self.close()
                self.student_window = StudentWindow()
                self.student_window.show()





class StudentWindow(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi('ui/classroom.ui', self)
        self.setWindowTitle("教室(學生端)")
        self.quit_button.clicked.connect(self.close)
        self.screenshot_receive_thread = ScreenshotReceiveThread()
        self.screenshot_receive_thread.change_pixmap_signal.connect(self.update_screenshot_image)
        self.screenshot_receive_thread.start()

        self.camera_receive_thread = CameraReceiveThread()
        self.camera_receive_thread.change_pixmap_signal.connect(self.update_camera_image)
        self.camera_receive_thread.start()

        self.audio_receive_thread = AudioReceiveThread()
        self.audio_receive_thread.start()

        self.request_student_list_thread = RequestStudentListThread()
        self.request_student_list_thread.change_student_list_signal.connect(self.update_student_list)
        self.request_student_list_thread.start()

        self.send_button.clicked.connect(self.send_message)
        self.recv_msg_thread = RecvMsgThread()
        self.recv_msg_thread.update_chatroom_signal.connect(self.update_chatroom)
        self.recv_msg_thread.start()

        self.student_list.itemClicked.connect(self.show_student_info)

        self.class_name_label.setText(f"課程名稱: {CLASSROOM_INFO['class_name']}")
        self.room_number_label.setText(f"教室代碼: {CLASSROOM_INFO['room_num']}")
        self.teacher_name_label.setText(f"老師姓名: {CLASSROOM_INFO['teacher_name']}")

        self.setStyleSheet(ROOM_WIDGET_STYLE)
        self.quit_button.setStyleSheet(QUIT_BUTTON_STYLE)
        self.send_button.setStyleSheet(SEND_BUTTON_STYLE)
        self.chat_room_label.setStyleSheet(CHAT_ROOM_LABEL_STYLE)
        self.class_name_label.setStyleSheet(CLASS_NAME_LABEL_STYLE)
        self.room_number_label.setStyleSheet(ROOM_NUMBER_LABEL_STYLE)
        self.student_list_label.setStyleSheet(STUDENT_LIST_LABEL_STYLE)
        self.teacher_name_label.setStyleSheet(TEACHER_NAME_LABEL_STYLE)
        self.msg_input.setStyleSheet(MSG_INPUT_STYLE)
        self.chatroom.setStyleSheet(CHATROOM_STYLE)
        self.camera.setStyleSheet(CAMERA_STYLE)
        self.screenshot.setStyleSheet(SCREENSHOT_STYLE)
        self.student_list.setStyleSheet(STUDENT_LIST_STYLE)

    def closeEvent(self, event):
        self.screenshot_receive_thread.terminate()
        self.screenshot_receive_thread.sock.close()
        self.camera_receive_thread.terminate()
        self.camera_receive_thread.sock.close()
        self.audio_receive_thread.terminate()
        self.audio_receive_thread.sock.close()
        self.request_student_list_thread.terminate()
        self.recv_msg_thread.terminate()
        self.recv_msg_thread.sock.close()
        self.leave_room()
        event.accept()

    def leave_room(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(SERVER_ADDRESS)
        data = pickle.dumps({
            'action': 'leave_room',
            'room_num': str(CLASSROOM_INFO['room_num']),
            'student_id': STUDENT_ID,
        })
        sock.sendall(data)
        sock.close()

    def update_screenshot_image(self, qt_image):
        self.screenshot.setPixmap(QPixmap.fromImage(qt_image))

    def update_camera_image(self, qt_image):
        self.camera.setPixmap(QPixmap.fromImage(qt_image))

    def update_student_list(self, student_list):
        self.student_list.clear()
        self.student_list.addItems([f'[{k}] {v["name"]}' for k, v in student_list.items()])

    def send_message(self, message):
        msg = self.msg_input.toPlainText()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(SERVER_ADDRESS)
        data = pickle.dumps({
            'action': 'send_message',
            'room_num': CLASSROOM_INFO['room_num'],
            'name':  STUDENT_NAME,
            'is_teacher': False,
            'time': time.localtime(),
            'msg': msg,
        })
        sock.sendall(data)
        sock.close()
        self.msg_input.clear()

    def update_chatroom(self, data):
        #msg = f"{time.strftime('%Y-%m-%d %H:%M:%S', data['time'])} {data['name']} {data['msg']}"
        msg = f"<font color='#40464C'><b>{data['name']}</b>&nbsp;&nbsp;&nbsp;<small>{time.strftime('%H:%M:%S', data['time'])}</small></font><br>{data['msg']}"

        self.chatroom.append(msg)

    def show_student_info(self, item):
        student_id = item.text().split('[')[1].split(']')[0]
        name = CLASSROOM_INFO['students'][student_id]['name']
        join_time = CLASSROOM_INFO['students'][student_id]['join_time']
        msg_box = QMessageBox()
        msg_box.setWindowTitle(f"{student_id}-學生資訊")
        msg_box.setText(f'<font color="#666666"><b>學號: {student_id}</b></font><br>'
                        f'<font color="#666666"><b>姓名: {name}</b></font><br>'
                        f"<font color='#666666'><b>上線時間: {time.strftime('%Y-%m-%d %H:%M:%S', join_time)}</b></font>")
        msg_box.setStyleSheet(MSG_BOX_STYLE)
        msg_box.exec_()
        # QMessageBox.information(self, f"{student_id}-學生資訊",
        #                         f'<font color="white"><b>學號:</b> {student_id}</font><br>'
        #                         f'<font color="white"><b>姓名:</b> {name}</font><br>'
        #                         f"<font color='white'><b>上線時間:</b> {time.strftime('%Y-%m-%d %H:%M:%S', join_time)}</font>")


if __name__ == "__main__":
    # check if room_num exist


    app = QApplication(sys.argv)
    join_room_window = JoinRoomWindow()
    join_room_window.show()
    sys.exit(app.exec_())
