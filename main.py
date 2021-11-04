"""
created by PyCharm
date: 2021/6/16
time: 14:23
user: wkc
"""
import sys
import MainWindow
from PyQt5.QtWidgets import QApplication, QMainWindow
from VideoDisplay import Display


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = QMainWindow()
    ui = MainWindow.Ui_MainWindow()
    ui.setupUi(main_window)
    display = Display(ui, main_window)
    main_window.show()
    sys.exit(app.exec_())