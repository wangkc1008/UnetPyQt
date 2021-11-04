"""
created by PyCharm
date: 2021/6/16
time: 14:21
user: wkc
"""
import time

import cv2
import threading
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtGui import QImage, QPixmap
from IVUS import IVUS
from PyQt5.QtWidgets import qApp


class Display:
    def __init__(self, ui, main_window):
        """
        初始化
        :param ui: ui界面对象
        :param main_window: 主窗口对象
        """
        self.ui = ui
        self.main_window = main_window

        # 按钮信号槽设置
        self.ui.open.clicked.connect(self.open)    # 打开文件按钮绑定open方法
        self.ui.start.clicked.connect(self.start)  # 开始按钮绑定start方法
        self.ui.pause.clicked.connect(self.pause)  # 暂停按钮绑定pause方法
        self.ui.close.clicked.connect(self.close)  # 清除按钮绑定close方法
        # 按钮状态设置
        self.ui.start.setEnabled(False)
        self.ui.pause.setEnabled(False)
        self.ui.close.setEnabled(False)
        # 菜单栏快捷键设置
        self.ui.action_open.triggered.connect(self.open)
        self.ui.action_start.triggered.connect(self.start)
        self.ui.action_pause.triggered.connect(self.pause)
        self.ui.action_close.triggered.connect(self.close)
        self.ui.action_quit.triggered.connect(qApp.quit)
        # 状态栏
        self.ui.statusbar.showMessage("未打开文件")
        # 时间进度条
        self.ui.total_num.setText(compute_time(0))
        self.ui.cur_num.setText(compute_time(0))
        # 视频处理线程
        self.lock = threading.Lock()            # 互斥量
        self.condition = threading.Condition()
        self.stop_event = threading.Event()
        self.stop_event.clear()                 # 初始化时清理结束标志位
        self.pipeline = []                      # 线程间帧传递队列  暂时先用list实现
        # 实例化视频分割对象
        self.ivus = IVUS()
        # 初始化
        self.cap = None                         
        self.file_name = None           
        self.frame_rate = 0                     # 帧率
        self.frame_total = 0                    # 总帧数
        self.frame_num = 0                      # 当前已播放帧数 计算进度条位置
        self.restart_flag = False               # 重新播放标志位
        self.pause_flag = False                 # 暂停标志位
        self.thread_pool = []
        self.tmp_flag = False                   # 解决暂停后打开文件时因部分线程结束，将左侧屏幕清掉显示空白的情况

    def open(self):
        """
        打开文件
        :return:
        """
        if self.file_name:                      # file_name不为None说明当前正在播放中 将播放暂停并改变按钮显示
            self.pause_flag = True
            self.ui.pause.setText("继续")

        file_name, file_type = QFileDialog.getOpenFileName(self.main_window, 'Choose file', '', '*.mp4')
        if not file_name:                       # 未打开任何文件
            if self.file_name:              # filename不为空说明此时有视频在播放 需要恢复视频播放
                self.pause_flag = False
                self.ui.pause.setText("暂停")
            else:
                self.ui.statusbar.showMessage("未打开文件")
            return

        self._close()  # 打开视频时需将一些标志位置为初始值
        self.file_name = file_name
        self.ui.statusbar.showMessage(file_name)  # 底部状态栏显示文件名
        self.ui.start.setEnabled(True)            # 开始按钮可点击

        # 读取第一帧数据在未开始播放时显示
        self.cap = cv2.VideoCapture(self.file_name)                 # 实例化视频读取对象
        self.frame_rate = self.cap.get(cv2.CAP_PROP_FPS)            # 当前视频帧率
        self.frame_total = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)   # 当前视频总帧数
        res = compute_time(self.frame_total / self.frame_rate)      # 计算视频时长 单位/s
        self.ui.process.setValue(0)                                 # 进度条设置为0
        self.ui.total_num.setText(res)                              # 设置总时长
        self.ui.cur_num.setText(compute_time(0))                    # 设置当前时间
        success, frame = self.cap.read()                            # 读取视频 读取成功后success为True否则为False frame读取到的帧数据
        # frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)              # opencv读取的数据为RGB转BGR
        frame = cv2.resize(frame, (512, 512))                       # 对每一帧进行resize为512*512(窗体宽高)
        img = QImage(frame.data, frame.shape[1], frame.shape[0], QImage.Format_RGB888)
        self.ui.video_orign.setPixmap(QPixmap.fromImage(img))       # 显示第一帧图像
        self.tmp_flag = True

    def start(self):
        """
        开始或重新播放
        :return:
        """
        if not self.file_name:                  # 未打开文件点击无效
            return

        self.ui.pause.setEnabled(True)          # 暂停/继续按钮可点击
        if not self.restart_flag:               # 首次播放
            self.cap = cv2.VideoCapture(self.file_name)
            self.pause_flag = False             # 暂停标志置为False
            self.restart_flag = True            # 重新播放标志位置为True 且改变按钮显示
            self.ui.start.setText("重新播放")
            self.stop_event.clear()             # 释放掉打开文件时的结束标志
            self._create_thread()               # 创建视频播放线程
        else:                                   # 重新播放 当前视频未播放完点击重新播放时不会开启新线程
            self.cap = cv2.VideoCapture(self.file_name)  # 重新读取视频文件 从第一帧开始播放
            self.pause_flag = False                      # 暂停标志位置为False且改变按钮显示
            self.ui.pause.setText("暂停")
            self.frame_num = 0                           # 当前已播放帧数置为0
            self.ui.process.setValue(0)                  # 进度条置为0
            if self.stop_event.is_set():                 # 在视频播放完毕后点击重新播放时会重新开启播放线程
                self.stop_event.clear()                  # 释放掉播放播放完时的结束标志
                self._create_thread()                    # 创建视频播放线程

    def _create_thread(self):
        """
        创建线程
        :return:
        """
        self.thread_pool = []
        # 创建左侧视频读取线程
        thread_origin = threading.Thread(target=self.display_origin, args=('thread_origin',))
        self.thread_pool.append(thread_origin)
        # 创建右侧分割视频处理线程
        for i in range(5):
            thread_seg = threading.Thread(target=self.display_seg, args=('thread_{}'.format(str(i)),))
            self.thread_pool.append(thread_seg)
        for thread in self.thread_pool:
            # 此处如果不设置守护线程 则主线程结束后子线程继续执行 执行完才会结束
            thread.setDaemon(True)  # 设置守护线程 主线程一旦结束 所有子线程全部结束
            thread.start()

    def close(self):
        """
        清除并关闭当前播放视频
        :return:
        """
        self._close()                               # 清除视频时需将一些标志位置为初始值
        self.ui.start.setEnabled(False)             # 开始按钮不可点击

    def _close(self):
        """
        打开视频或者点击清除将一些标志位设为初始值
        :return:
        """
        self.ui.video_orign.clear()  # 左侧、右侧清屏
        self.ui.video_handle.clear()
        self.stop_event.set()  # 设置结束标志位
        self.tmp_flag = False
        self.file_name = None
        self.ui.process.setValue(0)                 # 进度条置为0
        self.ui.statusbar.showMessage("未打开文件")   # 底部状态栏置为未打开文件
        self.ui.total_num.setText(compute_time(0))  # 总时长和当前时长都置为0
        self.ui.cur_num.setText(compute_time(0))
        self.ui.start.setText("开始")
        self.pause_flag = False          # 此时无视频播放 暂停标志位置为False 且禁止点击
        self.ui.pause.setText("暂停")
        self.ui.pause.setEnabled(False)
        self.restart_flag = False        # 打开视频或者点击清除 此时重新播放标志位置为False
        self.frame_num = 0               # 当前已播放帧数置为0

    def pause(self):
        """
        暂停/继续
        :return:
        """
        if not self.file_name:          # 未打开文件点击无效
            return
        if self.pause_flag:             # 已暂停则恢复播放且改变按钮显示
            self.pause_flag = False
            self.ui.pause.setText("暂停")
        else:                           # 未暂停则暂停播放且改变按钮显示
            self.pause_flag = True
            self.ui.pause.setText("继续")

    def quit(self):
        pass

    def display_origin(self, t_name):
        """
        左侧播放原视频
        :return:
        """
        self.ui.close.setEnabled(True)  # 清除按钮可点击
        while True:
            if self.stop_event.is_set():         # 判断close事件是否已触发
                if not self.tmp_flag:
                    self.ui.video_orign.clear()      # 清除左侧、右侧屏幕
                self.ui.video_handle.clear()
                self.ui.close.setEnabled(False)  # 清除按钮不可点击 跳出循环
                break

            if self.pause_flag:                  # 已暂停时不再读取视频数据
                time.sleep(0.1)
                continue

            success, frame = self.cap.read()     # 读取视频数据
            if not success:                      # 当前视频读取结束 设置结束标志位
                self.stop_event.set()
                self.ui.pause.setEnabled(False)
                break

            self.frame_num = self.frame_num + 1                   # 已读取阵数
            res = compute_time(self.frame_num / self.frame_rate)  # 计算并显示当前时间
            self.ui.cur_num.setText(res)
            self.ui.process.setValue(int((self.frame_num / self.frame_total) * 100))  # 设置进度条数值
            # frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)        # RGB转BGR
            # print(int(frame.shape[0] * 0.1), int(frame.shape[0] * 0.85))
            # frame = cv2.resize(frame[int(frame.shape[0] * 0.1):int(frame.shape[0] * 0.75), :, :], (512, 512))
            frame = cv2.resize(frame, (512, 512))
            # frame = cv2.convertScaleAbs(frame, alpha=1.5, beta=0)
            # frame = cv2.normalize(frame, dst=None, alpha=350, beta=10, norm_type=cv2.NORM_MINMAX)
            self.lock.acquire()                                   # 加互斥锁
            self.pipeline.append(frame)                           # 向队列中写帧数据
            self.lock.release()                                   # 释放互斥锁
            self.condition.acquire()                              # 条件变量加锁
            self.condition.notify()                               # 通知正在等待处理帧数据的线程
            self.condition.release()                              # 释放条件变量
            img = QImage(frame.data, frame.shape[1], frame.shape[0], QImage.Format_RGB888)
            self.ui.video_orign.setPixmap(QPixmap.fromImage(img))  # 左侧显示原视频帧
            cv2.waitKey(int(1000 / self.frame_rate))               # 设置原视频帧持续时间

    def display_seg(self, t_name):
        """
        右侧播放分割视频
        :return:
        """
        while True:
            if self.stop_event.is_set():      # 判断close事件是否已触发
                self.ui.video_handle.clear()
                break

            if self.pause_flag:               # 已暂停时不再处理视频数据
                time.sleep(0.1)
                continue

            if len(self.pipeline) == 0:       # 当前队列为空时 等待 阻塞当前线程
                self.condition.acquire()
                self.condition.wait()
                self.condition.release()
                continue
            else:
                self.lock.acquire()                         # 加互斥锁 读取帧数据
                frame = self.pipeline.pop(0)
                new_frame = self.ivus.ivus_classify(frame)  # 释放加互斥锁
                self.lock.release()
                img = QImage(new_frame.tostring(), new_frame.shape[1], new_frame.shape[0], QImage.Format_RGB888)
                self.ui.video_handle.setPixmap(QPixmap.fromImage(img))


def compute_time(duration):
    if duration == 0:
        return '00:00:00'
    second = int(duration % 60)
    second = '0{}'.format(second) if second < 10 else second
    minute = int(duration / 60 % 60)
    minute = '0{}'.format(minute) if minute < 10 else minute
    hour = int(duration / 3600 % 24)
    hour = '0{}'.format(hour) if hour < 10 else hour
    res = '{}:{}:{}'.format(hour, minute, second)
    return res
