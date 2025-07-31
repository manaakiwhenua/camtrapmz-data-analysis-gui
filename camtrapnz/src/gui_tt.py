import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout

class TestApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test GUI")
        layout = QVBoxLayout()
        button = QPushButton("Hello!")
        layout.addWidget(button)
        self.setLayout(layout)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestApp()
    window.show()
    sys.exit(app.exec_())
