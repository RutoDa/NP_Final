import base64
import imutils
import pyaudio
import pyautogui
import numpy as np
import cv2
import socket
import struct
import pickle
import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5 import uic, QtGui
import time
from PyQt5.QtWidgets import QWidget

from ui.Style import *

BUFF_SIZE = 65536
SERVER_IP = '127.0.0.1'
MULTICAST_GROUP = '224.1.1.1'
SERVER_ADDRESS = (SERVER_IP, 7777)
CLASSROOM_INFO = dict()


class ScreenshotThread(QThread):
    def run(self):
        global CLASSROOM_INFO
        server_address = (SERVER_IP, CLASSROOM_INFO['screenshot_port'])
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
        self.sock.connect(server_address)

        while True:
            time.sleep(0.01)
            screenshot = pyautogui.screenshot()
            screenshot = screenshot.resize((screenshot.width // 4, screenshot.height // 4))
            frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            encoded, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            message = base64.b64encode(buffer)
            self.sock.sendto(message, server_address)
        self.sock.close()


class CameraThread(QThread):
    def run(self):
        global CLASSROOM_INFO
        server_address = (SERVER_IP, CLASSROOM_INFO['camera_port'])
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
        self.sock.connect(server_address)
        vid = cv2.VideoCapture(0)
        while vid.isOpened():
            time.sleep(0.01)
            _, frame = vid.read()
            frame = imutils.resize(frame, width=200)
            encoded, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            message = base64.b64encode(buffer)
            self.sock.sendto(message, server_address)
        self.sock.close()


class AudioThread(QThread):
    def run(self):
        global CLASSROOM_INFO
        # PyAudio参数
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 20000

        server_address = (SERVER_IP, CLASSROOM_INFO['audio_port'])
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
        self.sock.connect(server_address)
        audio = pyaudio.PyAudio()
        stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        print("Audio streaming started...")
        while True:
            data = stream.read(CHUNK)
            self.sock.sendto(data, server_address)
        stream.stop_stream()
        stream.close()
        audio.terminate()
        self.sock.close()


class RequestStudentListThread(QThread):
    change_student_list_signal = pyqtSignal(dict)

    def run(self):
        global CLASSROOM_INFO
        while True:
            time.sleep(5)
            server_address = (SERVER_IP, 7777)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(server_address)
            data = pickle.dumps({
                'action': 'request_student_list',
                'room_num': str(CLASSROOM_INFO['room_num']),
            })
            sock.sendall(data)
            recv_data = sock.recv(BUFF_SIZE)
            student_list = pickle.loads(recv_data)
            sock.close()
            print(student_list)
            CLASSROOM_INFO['students'] = student_list
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


class CreateRoomWindow(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi('ui/create_room.ui', self)
        self.setWindowIcon(QtGui.QIcon('img/video-conference-gray.png'))
        self.setWindowTitle("線上同步教室(建立教室)")
        self.create_room_button.clicked.connect(self.create_room)
        self.setStyleSheet(CREATE_ROOM_WIDGET_STYLE)
        self.create_room_button.setStyleSheet(CREATE_ROOM_BUTTON_STYLE)
        self.label_title.setStyleSheet(ROOM_TITLE_LABEL_STYLE)
        self.class_name_label.setStyleSheet(CREATE_ROOM_CLASS_NAME_LABEL_STYLE)
        self.class_name_input.setStyleSheet(CREATE_ROOM_CLASS_NAME_INPUT_STYLE)
        self.teacher_name_label.setStyleSheet(CREATE_ROOM_TEACHER_NAME_LABEL_STYLE)
        self.teacher_name_input.setStyleSheet(CREATE_ROOM_TEACHER_NAME_INPUT_STYLE)

    def create_room(self):
        global CLASSROOM_INFO
        class_name = self.class_name_input.toPlainText()
        teacher_name = self.teacher_name_input.toPlainText()
        request = {'action': 'create_room', 'class_name': class_name, 'teacher_name': teacher_name}
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(SERVER_ADDRESS)
        data = pickle.dumps(request)
        sock.sendall(data)
        recv_data = sock.recv(BUFF_SIZE)
        CLASSROOM_INFO = pickle.loads(recv_data)
        sock.close()
        print(CLASSROOM_INFO)

        self.close()
        self.teacher_window = TeacherWindow()
        self.teacher_window.show()


class TeacherWindow(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi('ui/classroom.ui', self)
        self.setWindowIcon(QtGui.QIcon('img/video-conference-gray.png'))
        self.setWindowTitle("線上同步教室(老師端)")
        self.quit_button.clicked.connect(self.close)
        self.screenshot_thread = ScreenshotThread()
        self.screenshot_thread.start()
        self.camera_thread = CameraThread()
        self.camera_thread.start()
        self.audio_thread = AudioThread()
        self.audio_thread.start()
        self.request_student_list_thread = RequestStudentListThread()
        self.request_student_list_thread.change_student_list_signal.connect(self.update_student_list)
        self.request_student_list_thread.start()
        self.send_button.clicked.connect(self.send_message)
        self.recv_msg_thread = RecvMsgThread()
        self.recv_msg_thread.update_chatroom_signal.connect(self.update_chatroom)
        self.recv_msg_thread.start()

        self.class_name_label.setText(f"課程名稱: {CLASSROOM_INFO['class_name']}")
        self.room_number_label.setText(f"教室代碼: {CLASSROOM_INFO['room_num']}")
        self.teacher_name_label.setText(f"老師姓名: {CLASSROOM_INFO['teacher_name']}")

        self.screenshot.setText("螢幕畫面已開始傳送...")
        self.camera.setText("視訊畫面\n已開始傳送...")
        self.student_list.itemClicked.connect(self.show_student_info)

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
        self.screenshot_thread.terminate()
        self.screenshot_thread.sock.close()
        self.camera_thread.terminate()
        self.camera_thread.sock.close()
        self.audio_thread.terminate()
        self.audio_thread.sock.close()
        self.request_student_list_thread.terminate()
        self.recv_msg_thread.terminate()
        self.recv_msg_thread.sock.close()
        event.accept()

    def send_message(self, message):
        msg = self.msg_input.toPlainText()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(SERVER_ADDRESS)
        data = pickle.dumps({
            'action': 'send_message',
            'room_num': CLASSROOM_INFO['room_num'],
            'name': CLASSROOM_INFO['teacher_name'],
            'is_teacher': True,
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

    def update_student_list(self, student_list):
        self.student_list.clear()
        self.student_list.addItems([f"[{k}] {v['name']}" for k, v in student_list.items()])

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
        #                         f'<font color="#666666"><b>學號:</b> {student_id}</font><br>'
        #                         f'<font color="#666666"><b>姓名:</b> {name}</font><br>'
        #                         f"<font color='#666666'><b>上線時間:</b> {time.strftime('%Y-%m-%d %H:%M:%S', join_time)}</font>")

    # def update_image(self, qt_image):
    #     self.screenshot.setPixmap(QPixmap.fromImage(qt_image))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    create_room_window = CreateRoomWindow()
    create_room_window.show()

    sys.exit(app.exec_())


