import sys
import random
import json
import socket
import threading
import struct
import time
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, \
    QLabel, QDialog, QGridLayout, QRadioButton, QButtonGroup, QSpacerItem, QSizePolicy, \
    QTextEdit, QLineEdit
from PyQt6.QtGui import QPixmap, QIcon, QTransform
from PyQt6.QtCore import Qt, QCoreApplication, QTimer, pyqtSignal, QObject
import qdarktheme

# Dark Mode Styling
Dark = qdarktheme.load_stylesheet(
    theme="dark",
    custom_colors={
        "[dark]": {
            "primary": "#0078D4",
            "background": "#202124",
            "border": "#8A8A8A",
            "background>popup": "#252626",
        }
    },
) + """
    QMessageBox QLabel {
        color: #E4E7EB;
    }
    QDialog {
        background-color: #252626;
    }
    QComboBox:disabled {
        background-color: #1A1A1C; 
        border: 1px solid #3B3B3B;
        color: #3B3B3B;  
    }
    QPushButton {
    background-color: #0078D4; 
    color: #FFFFFF;           
    border: 1px solid #8A8A8A; 
    }
    QPushButton:hover {
        background-color: #669df2; 
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 #80CFFF, stop:1 #004080);
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 #004080, stop:1 #001B3D);
    }
    QPushButton:disabled {
        background-color: #202124; 
        border: 1px solid #3B3B3B;
        color: #FFFFFF;   
    }
"""

RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
VALUES = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
CARD_WIDTH = 56
CARD_HEIGHT = 84
BUTTON_WIDTH = 66
BUTTON_HEIGHT = 87

class SignalCommunicator(QObject):
    updateOpponentBottomCardsSignal = pyqtSignal(int, list)
    updateOpponentTopCardsSignal = pyqtSignal(int, list)
    updateOpponentHandSignal = pyqtSignal(int, list)
    updateDeckSignal = pyqtSignal(dict)
    startGameSignal = pyqtSignal()
    proceedWithGameSetupSignal = pyqtSignal()
    updateUISignal = pyqtSignal()

def centerDialog(dialog, parent, name):
    offset = 0
    if name == "playerSelectionDialog":
        offset = 100
    elif name == "rulesDialog":
        offset = 225
    parent_geo = parent.geometry()
    parent_center_x = parent_geo.center().x()
    parent_center_y = parent_geo.center().y()
    dialog_geo = dialog.geometry()
    dialog_center_x = dialog_geo.width() // 2
    dialog_center_y = dialog_geo.height() // 2
    new_x = parent_center_x - dialog_center_x
    new_y = parent_center_y - dialog_center_y - offset
    dialog.move(new_x, new_y)

class HostLobby(QDialog):
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("Host Lobby")
        self.setGeometry(0, 0, 300, 200)
        # self.setGeometry(835, 400, 300, 200)
        self.server_socket = None
        self.client_sockets = []
        self.client_addresses = {}
        self.client_nicknames = {}
        self.server_thread = None
        self.running = False
        self.player_count = 1  # Starting with host player
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.infoLabel = QLabel("Hosting Lobby...\nWaiting for players to join.")
        layout.addWidget(self.infoLabel)

        self.logText = QTextEdit()
        self.logText.setReadOnly(True)
        layout.addWidget(self.logText)

        self.playerCountLabel = QLabel("Players: 1/4")
        layout.addWidget(self.playerCountLabel)

        self.startButton = QPushButton("Start Game")
        self.startButton.setEnabled(False)
        self.startButton.clicked.connect(self.startGame)
        layout.addWidget(self.startButton)

        backButton = QPushButton("Back")
        backButton.clicked.connect(self.backToOnlineDialog)
        layout.addWidget(backButton)

        self.setLayout(layout)
        self.startServer()
    
    def showEvent(self, event):
        centerDialog(self, self.main_window, "Host Lobby")
    
    def startServer(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind(('127.0.0.1', 12345))  # Bind to the loopback address for local testing
            self.server_socket.listen(5)
            self.logText.append("Server started, waiting for connections...")
            self.logText.append("Host Connected")
            self.running = True
            self.server_thread = threading.Thread(target=self.accept_connections, daemon=True)
            self.server_thread.start()
        except Exception as e:
            self.logText.append(f"Failed to start server: {e}")

    def accept_connections(self):
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                if len(self.client_sockets) >= 3:
                    client_socket.sendall(b'lobby full')
                    client_socket.close()
                    self.logText.append(f"Connection attempt from {client_address} - Lobby Full")
                else:
                    self.client_sockets.append(client_socket)
                    self.client_addresses[client_socket] = client_address
                    threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()
                    threading.Thread(target=self.listen_for_disconnection, args=(client_socket,), daemon=True).start()
            except Exception as e:
                if self.running:  # Only log if the server is supposed to be running
                    self.logText.append(f"Error accepting connections: {e}")

    def handle_client(self, client_socket):
        try:
            data = client_socket.recv(1024).decode('utf-8')
            if data == "Player":
                data = f"Player {self.player_count + 1}"
            nickname = data
            self.client_nicknames[client_socket] = nickname
            self.player_count += 1
            log_message = f"{nickname} connected from {self.client_addresses[client_socket]}"
            self.logText.append(log_message)
            self.send_log_to_clients(log_message)  # Send log message to all clients
            self.playerCountLabel.setText(f"Players: {self.player_count}/4")
            if self.player_count > 1:
                self.startButton.setEnabled(True)
        except Exception as e:
            self.logText.append(f"Error handling client: {e}")

    def send_log_to_clients(self, message):
        for client_socket in self.client_sockets:
            try:
                client_socket.sendall(f"log: {message}".encode('utf-8'))
            except Exception as e:
                self.logText.append(f"Failed to send log to client: {e}")

    def listen_for_disconnection(self, client_socket):
        try:
            while self.running:
                data = client_socket.recv(1024).decode('utf-8')
                if data == 'leave':
                    self.remove_client(client_socket)
                    break
        except Exception as e:
            self.remove_client(client_socket)

    def remove_client(self, client_socket):
        nickname = self.client_nicknames.pop(client_socket, "Unknown")
        if client_socket in self.client_sockets:
            self.client_sockets.remove(client_socket)
            self.client_addresses.pop(client_socket, None)
            self.player_count -= 1
            self.logText.append(f"{nickname} has left the server.")
            self.playerCountLabel.setText(f"Players: {self.player_count}/4")
            client_socket.close()
            if self.player_count <= 1:
                self.startButton.setEnabled(False)

    def startGame(self):
        self.logText.append("Starting game...")
        self.notify_clients_to_start()
        self.accept()  # Close the lobby window
        self.main_window.startHost()

    def notify_clients_to_start(self):
        for client_socket in self.client_sockets:
            try:
                client_socket.sendall(b'start')
            except Exception as e:
                self.logText.append(f"Failed to notify client: {e}")
    
    def backToOnlineDialog(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        for client_socket in self.client_sockets:
            client_socket.close()
        self.accept()
        self.main_window.playOnline()
        
    def cleanup(self):
        if self.server_socket:
            self.server_socket.close()
        for client_socket in self.client_sockets:
            client_socket.close()
        self.running = False

    def closeEvent(self, event):
        self.cleanup()
        event.accept()

class JoinLobby(QDialog):
    connectionEstablished = pyqtSignal()
    startSignalReceived = pyqtSignal()
    lobbyFullSignal = pyqtSignal()

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("Join Lobby")
        self.setGeometry(0, 0, 300, 200)  # Default position, will be centered later
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)
        self.client_socket = None
        self.initUI()
        
        # Connect signals to slots
        self.connectionEstablished.connect(self.onConnectionEstablished)
        self.startSignalReceived.connect(self.onStartSignalReceived)
        self.lobbyFullSignal.connect(self.onLobbyFull)

    def initUI(self):
        layout = QVBoxLayout()
        
        self.infoLabel = QLabel("Enter host address to join lobby:")
        layout.addWidget(self.infoLabel)

        self.addressInput = QLineEdit()
        self.addressInput.setPlaceholderText("Host IP Address")
        layout.addWidget(self.addressInput)

        self.nicknameInput = QLineEdit()
        self.nicknameInput.setPlaceholderText("Enter Nickname")
        layout.addWidget(self.nicknameInput)

        self.logText = QTextEdit()
        self.logText.setReadOnly(True)
        layout.addWidget(self.logText)

        self.joinButton = QPushButton("Join Lobby")
        self.joinButton.clicked.connect(self.joinLobby)
        layout.addWidget(self.joinButton)

        self.backButton = QPushButton("Back")
        self.backButton.clicked.connect(self.backToOnlineDialog)
        layout.addWidget(self.backButton)
        
        self.leaveButton = QPushButton("Leave Server")
        self.leaveButton.setStyleSheet("background-color: red; color: white;")
        self.leaveButton.clicked.connect(self.leaveServer)
        self.leaveButton.setVisible(False)
        layout.addWidget(self.leaveButton)

        self.setLayout(layout)
    
    def showEvent(self, event):
        centerDialog(self, self.main_window, "JoinLobby")

    def joinLobby(self):
        host_address = self.addressInput.text()
        nickname = self.nicknameInput.text() or "Player"
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client_socket.connect((host_address, 12345))
            self.client_socket.sendall(nickname.encode('utf-8'))
            self.connectionEstablished.emit() 
            threading.Thread(target=self.listen_for_start_signal, daemon=True).start()
            self.backButton.setVisible(False)
            self.leaveButton.setVisible(True)
            self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
            self.show()
        except OSError as e:
            if e.errno == 10049:
                self.logText.append("Server does not exist.")
            elif e.errno == 10061:
                self.logText.append("Server is not running.")
            else:
                self.logText.append(f"Failed to connect: {e}")

    def listen_for_start_signal(self):
        try:
            while True:
                self.joinButton.setDisabled(True)
                try:
                    data = self.client_socket.recv(1024).decode('utf-8')
                except OSError as e:
                    if e.errno == 10053:
                        break
                    else:
                        raise e
                if data.startswith('log:'):
                    log_message = data[4:].strip()
                    self.logText.append(log_message)
                elif data == 'start':
                    self.startSignalReceived.emit()
                    break
                elif data == 'lobby full':
                    self.lobbyFullSignal.emit()
                    break
        except Exception as e:
            print(f"Error in listen_for_start_signal: {e}")

    def onConnectionEstablished(self):
        self.logText.append(f"Connected to lobby")
        
    def onStartSignalReceived(self):
        self.accept() 
        self.main_window.startClient()

    def onLobbyFull(self):
        self.logText.append("Lobby is full. Unable to join.")
        self.client_socket.close()

    def leaveServer(self):
        if self.client_socket:
            self.client_socket.sendall(b'leave')
            self.client_socket.close()
        self.client_socket = None
        self.leaveButton.setVisible(False)
        self.joinButton.setVisible(True)
        self.logText.append("Disconnected from server.")
        self.addressInput.setEnabled(True)
        self.nicknameInput.setEnabled(True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)
        self.show()
        self.main_window.joinLobby(self)
        self.accept()

    def backToOnlineDialog(self):
        if self.client_socket:
            self.client_socket.sendall(b'leave')
            self.client_socket.close()
        self.accept()
        self.main_window.playOnline()
    
    def cleanup(self):
        if self.client_socket:
            try:
                self.client_socket.sendall(b'leave')
            except Exception:
                pass
            self.client_socket.close()

    def closeEvent(self, event):
        self.cleanup()
        event.accept()

class Server:
    def __init__(self, host, port, communicator):
        self.host = host
        self.port = port
        self.communicator = communicator
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.bind((self.host, self.port))
        self.serverSocket.listen(1)
        self.controller = None 
        print(f"Server listening on {self.host}:{self.port}\n")
        self.clientSocket, self.clientAddress = self.serverSocket.accept()
        print(f"Connection from {self.clientAddress}\n")

        # Start a thread to handle client communication
        threading.Thread(target=self.handleClient).start()

    def handleClient(self):
        while True:
            try:
                data = self.receiveData(self.clientSocket)
                if data:
                    self.processClientData(data)
            except ConnectionResetError:
                print("Connection reset by client\n")
                break
            except ConnectionAbortedError:
                print("Connection aborted by client\n")
                break
            except Exception as e:
                print(f"Unexpected error: {e}\n")
                break
        self.clientSocket.close()

    def processClientData(self, data):
        if data is None:
            return
        if data['action'] == 'confirmTopCards':
            playerIndex = int(data['playerIndex'])
            self.communicator.updateOpponentBottomCardsSignal.emit(playerIndex, data['bottomCards'])
            self.communicator.updateOpponentTopCardsSignal.emit(playerIndex, data['topCards'])
            self.communicator.updateOpponentHandSignal.emit(playerIndex, data['hand'])
            self.controller.checkBothPlayersConfirmed()
        elif data['action'] == 'startGame':
            self.controller.proceedWithGameSetup()
        elif data['action'] == 'playCard':
            self.controller.receiveGameState(data)
        elif data['action'] == 'playAgainRequest':
            self.controller.handlePlayAgain()
        elif data['action'] == 'resetGame':
            self.controller.resetGame()
            self.controller.setupGame()
        elif data['action'] == 'gameOver':
            self.controller.gameOverSignal.emit(data['winner'])

    def sendToClient(self, data):
        if self.clientSocket:
            try:
                serializedData = json.dumps(data).encode('utf-8')
                msgLen = struct.pack('>I', len(serializedData))
                print(f"Sending data to client: {data}\n")
                self.clientSocket.sendall(msgLen + serializedData)
            except Exception as e:
                print(f"Error sending data to client: {e}\n")
        else:
            print("Client socket is not connected\n")

    def receiveData(self, sock):
        rawMsgLen = self.recvall(sock, 4)
        if not rawMsgLen:
            return None
        msglen = struct.unpack('>I', rawMsgLen)[0]
        message = self.recvall(sock, msglen)
        if message is None:
            return None
        data = json.loads(message)
        print(f"Received data: {data}\n")
        return data

    def recvall(self, sock, n):
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data

    def close(self):
        if self.clientSocket:
            self.clientSocket.close()
        if self.serverSocket:
            self.serverSocket.close()

class Client:
    def __init__(self, host, port, communicator):
        self.host = host
        self.port = port
        self.communicator = communicator
        self.clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.controller = None 
        try:
            self.clientSocket.connect((self.host, self.port))
            print("Connected to the server\n")
            threading.Thread(target=self.handleServer).start()
        except Exception as e:
            print(f"Failed to connect to the server: {e}\n")
            self.clientSocket = None  

    def handleServer(self):
        while self.clientSocket: 
            try:
                data = self.receiveData(self.clientSocket)
                if data:
                    self.processServerData(data)
                else:
                    print("No data received in handleServer\n")
            except ConnectionResetError:
                print("Connection reset by server\n")
                break
            except ConnectionAbortedError:
                print("Connection aborted by server\n")
                break
            except Exception as e:
                print(f"Unexpected error: {e}\n")
                break
        if self.clientSocket:
            self.clientSocket.close()

    def processServerData(self, data):
        if data is None:
            print("Received None data from server\n")
            return
        if data['action'] == 'confirmTopCards':
            playerIndex = int(data['playerIndex'])
            self.communicator.updateOpponentBottomCardsSignal.emit(playerIndex, data['bottomCards'])
            self.communicator.updateOpponentTopCardsSignal.emit(playerIndex, data['topCards'])
            self.communicator.updateOpponentHandSignal.emit(playerIndex, data['hand'])
            self.controller.checkBothPlayersConfirmed()
        elif data['action'] == 'deckSync':
            self.communicator.updateDeckSignal.emit(data)
        elif data['action'] == 'startGame':
            self.controller.proceedWithGameSetup()
        elif data['action'] == 'playCard':
            self.controller.receiveGameState(data)
        elif data['action'] == 'playAgainRequest':
            self.controller.handlePlayAgain()
        elif data['action'] == 'resetGame':
            self.controller.resetGame()
            self.controller.setupGame()
        elif data['action'] == 'gameOver':
            self.controller.gameOverSignal.emit(data['winner'])

    def sendToServer(self, data):
        if self.clientSocket:
            try:
                serializedData = json.dumps(data).encode('utf-8')
                msgLen = struct.pack('>I', len(serializedData))
                print(f"Sending data to server: {data}\n")
                self.clientSocket.sendall(msgLen + serializedData)
            except Exception as e:
                print(f"Error sending data to server: {e}\n")
        else:
            print("Client socket is not connected\n")

    def receiveData(self, sock):
        rawMsgLen = self.recvall(sock, 4)
        if not rawMsgLen:
            return None
        msglen = struct.unpack('>I', rawMsgLen)[0]
        message = self.recvall(sock, msglen)
        if message is None:
            return None
        data = json.loads(message)
        print(f"Received data: {data}\n")
        return data

    def recvall(self, sock, n):
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data

    def close(self):
        if self.clientSocket: 
            self.clientSocket.close()
            self.clientSocket = None

class GameOverDialog(QDialog):
    playAgainSignal = pyqtSignal()
    mainMenuSignal = pyqtSignal()
    exitSignal = pyqtSignal()

    def __init__(self, winnerName, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Game Over")
        self.setGeometry(805, 350, 300, 200)

        layout = QVBoxLayout()

        label = QLabel(f"Game Over! {winnerName} wins!")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        buttonBox = QHBoxLayout()
        playAgainButton = QPushButton("Play Again")
        playAgainButton.clicked.connect(self.playAgain)
        mainMenuButton = QPushButton("Main Menu")
        mainMenuButton.clicked.connect(self.mainMenu)
        exitButton = QPushButton("Exit")
        exitButton.clicked.connect(self.exitGame)
        buttonBox.addWidget(playAgainButton)
        buttonBox.addWidget(mainMenuButton)
        buttonBox.addWidget(exitButton)
        layout.addLayout(buttonBox)

        self.setLayout(layout)

    def showEvent(self, event):
        centerDialog(self, self.parent(), "GameOverDialog")
    
    def playAgain(self):
        self.playAgainSignal.emit()
        self.accept()

    def mainMenu(self):
        self.mainMenuSignal.emit()
        self.accept()

    def exitGame(self):
        self.exitSignal.emit()
        QCoreApplication.instance().quit()

class HomeScreen(QWidget):
    def __init__(self, communicator):
        super().__init__()
        self.communicator = communicator
        self.controller = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Palace')
        self.setWindowIcon(QIcon(r"_internal\palaceData\palace.ico"))
        self.setGeometry(660, 215, 600, 500)
        layout = QVBoxLayout()
        title = QLabel("Palace")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 36px; font-weight: bold;")
        layout.addWidget(title)

        buttonLayout = QVBoxLayout()

        buttonLayout.addWidget(QLabel(""))
        buttonLayout.addWidget(QLabel(""))

        playButton = QPushButton("Play")
        playButton.setFixedHeight(40)
        playButton.setFixedWidth(275)
        playButton.clicked.connect(self.showPlayerSelectionDialog)
        buttonLayout.addWidget(playButton)

        buttonLayout.addWidget(QLabel(""))

        onlineButton = QPushButton("Online")
        onlineButton.clicked.connect(self.playOnline)
        onlineButton.setFixedWidth(225)
        buttonLayout.addWidget(onlineButton, alignment=Qt.AlignmentFlag.AlignCenter)

        buttonLayout.addWidget(QLabel(""))
        
        rulesButton = QPushButton("Rules")
        rulesButton.clicked.connect(self.showRules)
        rulesButton.setFixedWidth(225)
        buttonLayout.addWidget(rulesButton, alignment=Qt.AlignmentFlag.AlignCenter)

        buttonLayout.addWidget(QLabel(""))

        exitButton = QPushButton("Exit")
        exitButton.clicked.connect(QCoreApplication.instance().quit)
        exitButton.setFixedWidth(225)
        buttonLayout.addWidget(exitButton, alignment=Qt.AlignmentFlag.AlignCenter)

        buttonLayout.addWidget(QLabel(""))

        buttonContainer = QWidget()
        buttonContainer.setLayout(buttonLayout)
        layout.addWidget(buttonContainer, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)
    
    def returnToMainMenu(self):
        self.show()
        if self.controller:
            self.controller.view.close()
    
    def showPlayerSelectionDialog(self):
        self.playerSelectionDialog = QDialog(self)
        self.playerSelectionDialog.setWindowTitle("Select Number of Players")
        self.playerSelectionDialog.setGeometry(805, 350, 300, 200)

        layout = QVBoxLayout()

        label = QLabel("How many players?")
        layout.addWidget(label)

        self.radioGroup = QButtonGroup(self.playerSelectionDialog)
        radioButton2 = QRadioButton("Player vs. CPU")
        radioButton2.setFixedWidth(107)
        radioButton3 = QRadioButton("Player vs. CPU vs. CPU")
        radioButton3.setFixedWidth(150)
        radioButton4 = QRadioButton("Player vs. CPU vs. CPU vs. CPU")
        radioButton4.setFixedWidth(193)

        self.radioGroup.addButton(radioButton2, 2)
        self.radioGroup.addButton(radioButton3, 3)
        self.radioGroup.addButton(radioButton4, 4)

        layout.addWidget(radioButton2)
        layout.addWidget(radioButton3)
        layout.addWidget(radioButton4)
        layout.addWidget(QLabel(""))

        difficultyLabel = QLabel("Select AI Difficulty:")
        layout.addWidget(difficultyLabel)

        self.difficultyGroup = QButtonGroup(self.playerSelectionDialog)
        easyButton = QRadioButton("Easy")
        easyButton.setFixedWidth(55)
        mediumButton = QRadioButton("Medium")
        mediumButton.setFixedWidth(75)
        hardButton = QRadioButton("Hard")
        hardButton.setFixedWidth(57)
        impossibleButton = QRadioButton("Impossible")
        impossibleButton.setFixedWidth(115)

        self.difficultyGroup.addButton(easyButton, 1)
        self.difficultyGroup.addButton(mediumButton, 2)
        self.difficultyGroup.addButton(hardButton, 3)
        self.difficultyGroup.addButton(impossibleButton, 3)

        layout.addWidget(easyButton)
        layout.addWidget(mediumButton)
        layout.addWidget(hardButton)
        layout.addWidget(impossibleButton)
        layout.addWidget(QLabel(""))
        
        buttonBox = QHBoxLayout()
        okButton = QPushButton("OK")
        cancelButton = QPushButton("Cancel")
        okButton.clicked.connect(lambda: self.startGameWithSelectedPlayers(self.playerSelectionDialog))
        cancelButton.clicked.connect(self.playerSelectionDialog.reject)
        buttonBox.addWidget(okButton)
        buttonBox.addWidget(cancelButton)
        layout.addLayout(buttonBox)

        self.playerSelectionDialog.setLayout(layout)
        centerDialog(self.playerSelectionDialog, self, "playerSelectionDialog")
        self.playerSelectionDialog.exec()

    def startGameWithSelectedPlayers(self, dialog):
        numPlayers = self.radioGroup.checkedId()
        difficulty = self.difficultyGroup.checkedId()
        if numPlayers in [2, 3, 4]:
            dialog.accept()
            self.hide()
            difficultyMap = {1: 'easy', 2: 'medium', 3: 'hard'}
            difficultyLevel = difficultyMap.get(difficulty, 'medium')
            self.controller = GameController(numPlayers, difficultyLevel)  # Start game with selected number of players and difficulty level
            self.controller.mainMenuRequested.connect(self.returnToMainMenu)
            self.controller.view.show()

    def playOnline(self):
        self.onlineDialog = QDialog(self)
        self.onlineDialog.setWindowTitle("Online Multiplayer")
        self.onlineDialog.setGeometry(835, 400, 250, 150)
        layout = QVBoxLayout()

        hostButton = QPushButton("Host Lobby")
        hostButton.clicked.connect(lambda: self.hostLobby(self.onlineDialog))
        layout.addWidget(hostButton)

        layout.addWidget(QLabel())

        joinButton = QPushButton("Join Lobby")
        joinButton.clicked.connect(lambda: self.joinLobby(self.onlineDialog))
        layout.addWidget(joinButton)

        layout.addWidget(QLabel())

        closeButton = QPushButton("Close")
        closeButton.setFixedWidth(75)
        closeButton.clicked.connect(self.onlineDialog.accept)
        layout.addWidget(closeButton, alignment=Qt.AlignmentFlag.AlignCenter)

        self.onlineDialog.setLayout(layout)
        centerDialog(self.onlineDialog, self, "playOnlineDialog")
        self.onlineDialog.exec()

    def hostLobby(self, onlineDialog):
        self.hostLobbyDialog = HostLobby(self, self)
        self.hostLobbyDialog.show()
        onlineDialog.accept()

    def joinLobby(self, onlineDialog):
        self.joinLobbyDialog = JoinLobby(self, self)
        self.joinLobbyDialog.show()
        onlineDialog.accept()

    def startHost(self):
        self.hide()
        self.server = Server('localhost', 5555, self.communicator)
        self.controller = GameController(numPlayers=2, difficulty='medium', connection=self.server, isHost=True)  # 2 players for online
        self.server.controller = self.controller 
        self.controller.mainMenuRequested.connect(self.returnToMainMenu)
        self.controller.view.show()
    
    def startClient(self):
        self.hide()
        self.client = Client('localhost', 5555, self.communicator) 
        self.controller = GameController(numPlayers=2, difficulty='medium', connection=self.client, isHost=False)  # 2 players for online
        self.client.controller = self.controller 
        self.controller.mainMenuRequested.connect(self.returnToMainMenu)
        self.controller.view.show()
    
    def showRules(self):
        self.rulesDialog = QDialog(self)
        self.rulesDialog.setWindowTitle("Rules")
        self.rulesDialog.setGeometry(560, 100, 800, 300)
        self.rulesDialog.setWindowIcon(QIcon(r"_internal\palaceData\palace.ico"))
        layout = QVBoxLayout()
        rulesLabel = QLabel(
            """<h2>The Pack</h2>
        <ul>
            <li>2-4 players use one standard deck of 52 cards.</li>
        </ul>
        <h2>Rank of Cards</h2>
        <ul>
            <li>A-K-Q-J-9-8-7-6-5-4-3</li>
            <li>The 2 and 10 are special cards that reset the deck.</li>
            <li>The 7 is a special card that reverses the rank hierarchy, the next player ONLY must play a card rank 7 or lower.</li>
        </ul>
        <h2>Object of the Game</h2>
        <ul>
            <li>Play your cards in a pile using ascending order, and the first player to run out of cards wins.</li>
        </ul>
        <h2>The Deal</h2>
        <ul>
            <li>Deal three cards face down to each player. Players are not allowed to look at these cards and must place them
            face down in three columns in front of each player.</li>
            <li>Deal six cards to each player face down. Players may look at these cards in their hand.</li>
            <li>Players select three cards from their hand and place them face up on the three face down cards in front of them.
            Typically, higher value cards are placed face up.</li>
            <li>Place the remaining cards from the deck face down in the center of the table to form the Draw pile.</li>
        </ul>
        <h2>The Play</h2>
        <ul>
            <li>The player with the agreed worst average top cards is the first player and the second player is clockwise or counter clockwise
            with the second worst average top cards.</li>
            <li>The first player plays any card from their hand. You can play multiple cards on your turn, as long as they're all equal to or
            higher than the top pile card.</li>
            <li>Once you have have finished your turn, draw cards from the Draw pile to maintain three cards in your hand at all times.</li>
            <li>You must play a card if you can or pick up the current pile and add it to your hand.</li>
            <li>On their turn, a player can play any 2 card which resets the top pile card to 2, starting the sequence all over.</li>
            <li>On their turn, a player can play the 10 on any card, but it puts the pile into a bomb pile instead of resetting the sequence. The
            player who put the 10 down then draws up to three cards and plays any card.</li>
            <li>If four of the same rank are played in a row, either by one player or multiple players, it clears the pile. Place it in the bomb pile,
            as these cards are out of the game. The player that played the fourth card can then play any card from their hand.</li>
            <li>Play continues around the table until the deck is depleted.</li>
            <li>Once the deck is depleted, players rely solely on the cards in their hand. Keep playing until there are no cards left in your
            hand.</li>
            <li>When it's your turn and you don't have a hand, play one card from your face-up cards in front of you.</li>
            <li>When it's your turn and you've played all your face-up cards, pick a card that's face-down on the table. Don't look at it to choose.
            Simply flip it over. If it plays on the current card by being equal or higher, you can play it. If not, you must pick up the discard pile.</li>
            <li>If you pick up the discard pile, you must play those before continuing to play your face-down cards.</li>
            <li>First player to finish all cards in hand, face-up cards, and face-down cards, wins the game.</li>
        </ul>
        <ul>
            <li>
        </ul>
        """
        )
        rulesLabel.setTextFormat(Qt.TextFormat.RichText)
        rulesLabel.setWordWrap(True)
        rulesLabel.setFixedWidth(800)
        layout.addWidget(rulesLabel)
        closeButton = QPushButton("Close")
        closeButton.clicked.connect(self.rulesDialog.accept)
        layout.addWidget(closeButton)
        self.rulesDialog.setLayout(layout)
        centerDialog(self.rulesDialog, self, "rulesDialog")
        self.rulesDialog.exec()

class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []
        self.bottomCards = []
        self.topCards = []

    def playCard(self, cardIndex, pile):
        card = self.hand.pop(cardIndex)
        if card[2]:
            card = (card[0], card[1], False, False)
        if card[3]:
            card = (card[0], card[1], card[2], False)
        pile.append(card)
        return card

    def addToHand(self, cards):
        self.hand.extend(cards)

    def pickUpPile(self, pile):
        self.hand.extend(pile)
        pile.clear()

class GameView(QWidget):
    def __init__(self, controller, playerType, communicator, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.playerType = playerType
        self.communicator = communicator
        self.initUI()

        # Connect signals to slots
        self.communicator.updateOpponentBottomCardsSignal.connect(self.updateOpponentBottomCards)
        self.communicator.updateOpponentTopCardsSignal.connect(self.updateOpponentTopCards)
        self.communicator.updateOpponentHandSignal.connect(self.updateOpponentHand)
        
    def initUI(self):
        self.setWindowTitle(f'Palace Card Game - {self.playerType}')
        self.setWindowIcon(QIcon(r"_internal\palaceData\palace.ico"))
        self.setGeometry(450, 75, 900, 900)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)

        self.layout = QGridLayout()

        # Opponent Hand (row 0, column 5)
        self.opponentHandContainer = QWidget()
        self.opponentHandContainer.setMaximumWidth(500)  # Set maximum width here
        self.opponentHandLayout = QHBoxLayout(self.opponentHandContainer)
        # Create a container layout with spacers to center the hand layout
        self.opponentHandContainerLayout = QHBoxLayout()
        self.opponentHandContainerLayout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.opponentHandContainerLayout.addWidget(self.opponentHandContainer, alignment=Qt.AlignmentFlag.AlignCenter)
        self.opponentHandContainerLayout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.layout.addLayout(self.opponentHandContainerLayout, 0, 5, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Opponent Hand Label (row 1, column 5)
        self.opponentHandLabel = QLabel(f"{'Player 2' if self.playerType == 'Player 1' else 'Player 1'}'s Hand")
        self.opponentHandLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.opponentHandLabel, 1, 5, alignment=Qt.AlignmentFlag.AlignCenter)

        # Opponent Top Cards (row 2, column 5)
        self.opponentTopCardsLayout = QHBoxLayout()
        self.layout.addLayout(self.opponentTopCardsLayout, 2, 5, alignment=Qt.AlignmentFlag.AlignCenter)

        # Opponent Bottom Cards (row 3, column 5)
        self.opponentBottomCardsLayout = QHBoxLayout()
        self.layout.addLayout(self.opponentBottomCardsLayout, 3, 5, alignment=Qt.AlignmentFlag.AlignCenter)

        # Spacer (row 4, column 5)
        spacer1 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.layout.addItem(spacer1, 4, 5)

        # Center layout setup (row 5, column 5)
        self.deckLabel = QLabel()
        self.deckLabel.setFixedWidth(190)
        self.deckLabel.setVisible(False)
        self.pileLabel = QLabel("\t     Select your 3 Top cards...")
        self.pileLabel.setStyleSheet("border: 0px solid black; background-color: transparent;")
        self.pickUpPileButton = QPushButton("Pick Up Pile")
        self.pickUpPileButton.setFixedWidth(125)
        self.pickUpPileButton.setVisible(False)
        self.pickUpPileButton.clicked.connect(self.controller.pickUpPile)
        self.currentPlayerLabel = QLabel("")

        spacer = QSpacerItem(60, 1, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.consoleLayout = QHBoxLayout()
        self.consoleLayout.addWidget(self.deckLabel, alignment=Qt.AlignmentFlag.AlignLeft)
        self.consoleLayout.addWidget(self.pileLabel, alignment=Qt.AlignmentFlag.AlignCenter)
        self.consoleLayout.addItem(spacer)
        self.consoleLayout.addWidget(self.pickUpPileButton, alignment=Qt.AlignmentFlag.AlignRight)

        self.centerContainer = QWidget()
        self.centerContainer.setLayout(self.consoleLayout)
        self.centerContainer.setFixedWidth(500)

        self.centerLayout = QVBoxLayout()
        self.centerLayout.addWidget(QLabel(""))
        self.centerLayout.addWidget(self.currentPlayerLabel, alignment=Qt.AlignmentFlag.AlignCenter)
        self.centerLayout.addWidget(self.centerContainer, alignment=Qt.AlignmentFlag.AlignCenter)
        self.centerLayout.addWidget(QLabel(""))
        self.centerLayout.addWidget(QLabel(""))

        self.layout.addLayout(self.centerLayout, 5, 5, alignment=Qt.AlignmentFlag.AlignCenter)

        # Spacer (row 6, column 5)
        spacer2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.layout.addItem(spacer2, 6, 5)

        # Player Bottom Cards (row 7, column 5)
        self.bottomCardsLayout = QHBoxLayout()
        self.layout.addLayout(self.bottomCardsLayout, 7, 5, alignment=Qt.AlignmentFlag.AlignCenter)

        # Player Top Cards (row 8, column 5)
        self.topCardsLayout = QHBoxLayout()
        self.layout.addLayout(self.topCardsLayout, 8, 5, alignment=Qt.AlignmentFlag.AlignCenter)

        # Player Hand Label (row 9, column 5)
        self.playerHandLabel = QLabel(f"{self.playerType}'s Hand")
        self.playerHandLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.playerHandLabel, 9, 5, alignment=Qt.AlignmentFlag.AlignCenter)

        # Player Hand (row 10, column 5)
        self.playerHandContainer = QWidget()
        self.playerHandContainer.setMaximumWidth(500)  # Set maximum width here
        self.playerHandLayout = QHBoxLayout(self.playerHandContainer)
        # Create a container layout with spacers to center the hand layout
        self.playerHandContainerLayout = QHBoxLayout()
        self.playerHandContainerLayout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.playerHandContainerLayout.addWidget(self.playerHandContainer, alignment=Qt.AlignmentFlag.AlignCenter)
        self.playerHandContainerLayout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.layout.addLayout(self.playerHandContainerLayout, 10, 5, alignment=Qt.AlignmentFlag.AlignCenter)

        # Confirm/Place Button (row 11, column 5)
        buttonsContainerLayout = QVBoxLayout()
        self.confirmButton = QPushButton("Confirm")
        self.confirmButton.setEnabled(False)
        self.confirmButton.setFixedWidth(240)
        self.confirmButton.clicked.connect(self.confirmTopCardSelection)
        self.placeButton = QPushButton("Select A Card")
        self.placeButton.setEnabled(False)
        self.placeButton.setFixedWidth(240)
        self.placeButton.clicked.connect(self.controller.placeCard)
        self.placeButton.setVisible(False)

        buttonsContainerLayout.addWidget(self.confirmButton, alignment=Qt.AlignmentFlag.AlignCenter)
        buttonsContainerLayout.addWidget(self.placeButton, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addLayout(buttonsContainerLayout, 11, 5, alignment=Qt.AlignmentFlag.AlignCenter)

        # Width of the center console column
        self.layout.setColumnMinimumWidth(5, 500)

        if self.controller.numPlayers >= 3:
            # Player 3 setup
            self.player3HandLayout = QVBoxLayout()
            self.player3TopCardsLayout = QVBoxLayout()
            self.player3BottomCardsLayout = QVBoxLayout()

            self.layout.addLayout(self.player3HandLayout, 5, 0, alignment=Qt.AlignmentFlag.AlignCenter)
            self.player3HandLabel = QLabel("Player 3's Hand")
            self.player3HandLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(self.player3HandLabel, 5, 1, alignment=Qt.AlignmentFlag.AlignCenter)
            self.layout.addLayout(self.player3TopCardsLayout, 5, 2, alignment=Qt.AlignmentFlag.AlignCenter)
            self.layout.addLayout(self.player3BottomCardsLayout, 5, 3, alignment=Qt.AlignmentFlag.AlignCenter)

            # Spacer (row 5, column 4)
            spacer3 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            self.layout.addItem(spacer3, 5, 4)

        if self.controller.numPlayers == 4:
            # Player 4 setup
            self.player4HandLayout = QVBoxLayout()
            self.player4TopCardsLayout = QVBoxLayout()
            self.player4BottomCardsLayout = QVBoxLayout()

            # Spacer (row 5, column 6)
            self.layout.addItem(spacer3, 5, 6)

            self.layout.addLayout(self.player4BottomCardsLayout, 5, 7, alignment=Qt.AlignmentFlag.AlignCenter)
            self.layout.addLayout(self.player4TopCardsLayout, 5, 8, alignment=Qt.AlignmentFlag.AlignCenter)
            self.player4HandLabel = QLabel("Player 4's Hand")
            self.player4HandLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(self.player4HandLabel, 5, 9, alignment=Qt.AlignmentFlag.AlignCenter)
            self.layout.addLayout(self.player4HandLayout, 5, 10, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(self.layout)

    def showEvent(self, event):
        centerDialog(self, self.main_window, "GameView")
    
    def updateHandButtons(self, hand, layout, isPlayer, rotate):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.controller.playCardButtons = []
        for idx, card in enumerate(hand):
            button = QLabel()
            if rotate:
                button.setFixedSize(BUTTON_HEIGHT, BUTTON_WIDTH)
            else:
                button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            button.setStyleSheet("border: 0px solid black; background-color: transparent;")
            if not card[3] and isPlayer:
                pixmap = QPixmap(fr"_internal\palaceData\cards\{card[0].lower()}_of_{card[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                if rotate:
                    transform = QTransform().rotate(90)
                    pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation).scaled(CARD_HEIGHT, CARD_WIDTH, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                else:
                    pixmap = pixmap.scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                button.setPixmap(pixmap)
            else:
                pixmap = QPixmap(r"_internal\palaceData\cards\back.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                if rotate:
                    transform = QTransform().rotate(90)
                    pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation).scaled(CARD_HEIGHT, CARD_WIDTH, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                else:
                    pixmap = pixmap.scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                button.setPixmap(pixmap)
            button.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if self.controller.topCardSelectionPhase:
                button.mousePressEvent = lambda event, idx=idx, btn=button: self.selectTopCard(idx, btn)
            else:
                try:
                    button.mousePressEvent = lambda event, idx=idx, btn=button: self.controller.prepareCardPlacement(idx, btn)
                except IndexError:
                    return
            self.controller.playCardButtons.append(button)
            layout.addWidget(button)

        if len(hand) >= 10:
            spacer = QLabel()
            spacer.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            layout.addWidget(spacer)

    def updateOpponentHand(self, playerIndex, hand):
        self.controller.players[playerIndex].hand = hand
        self.updateOpponentHandButtons(hand)
        
    def updateOpponentTopCards(self, playerIndex, topCards):
        self.controller.players[playerIndex].topCards = topCards
        self.updateOpponentTopCardButtons(topCards)
        
    def updateOpponentBottomCards(self, playerIndex, bottomCards):
        self.controller.players[playerIndex].bottomCards = bottomCards
        self.updateOpponentBottomCardButtons(bottomCards)
    
    def updatePlayerHandButtons(self, hand):
        self.updateHandButtons(hand, self.playerHandLayout, True, False)
    
    def updateOpponentHandButtons(self, hand):
        self.updateHandButtons(hand, self.opponentHandLayout, False, False)

    def updatePlayerTopCardButtons(self, topCards):
        for i in reversed(range(self.topCardsLayout.count())):
            self.topCardsLayout.itemAt(i).widget().deleteLater()

        for card in topCards:
            button = QLabel()
            button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            button.setStyleSheet("border: 0px solid black; background-color: transparent;")
            pixmap = QPixmap(f"_internal\palaceData\cards\{card[0].lower()}_of_{card[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            button.setPixmap(pixmap)
            button.setAlignment(Qt.AlignmentFlag.AlignCenter)
            button.setDisabled(True)
            self.topCardsLayout.addWidget(button)
        if not topCards:
            self.placeholder = QLabel()
            self.placeholder.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            self.topCardsLayout.addWidget(self.placeholder)

    def updateOpponentTopCardButtons(self, topCards):
        for i in reversed(range(self.opponentTopCardsLayout.count())):
            self.opponentTopCardsLayout.itemAt(i).widget().deleteLater()

        for card in topCards:
            button = QLabel()
            button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            button.setStyleSheet("border: 0px solid black; background-color: transparent;")
            pixmap = QPixmap(f"_internal\palaceData\cards\{card[0].lower()}_of_{card[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            button.setPixmap(pixmap)
            button.setAlignment(Qt.AlignmentFlag.AlignCenter)
            button.setDisabled(True)
            self.opponentTopCardsLayout.addWidget(button)
        if not topCards:
            self.placeholder = QLabel()
            self.placeholder.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            self.opponentTopCardsLayout.addWidget(self.placeholder)

    def updatePlayerBottomCardButtons(self, bottomCards):
        for i in reversed(range(self.bottomCardsLayout.count())):
            self.bottomCardsLayout.itemAt(i).widget().deleteLater()

        for card in bottomCards:
            button = QLabel()
            button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            button.setStyleSheet("border: 0px solid black; background-color: transparent;")
            pixmap = QPixmap(r"_internal\palaceData\cards\back.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            button.setPixmap(pixmap)
            button.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.bottomCardsLayout.addWidget(button)
        if not bottomCards:
            self.placeholder = QLabel()
            self.placeholder.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            self.bottomCardsLayout.addWidget(self.placeholder)

    def updateOpponentBottomCardButtons(self, bottomCards):
        for i in reversed(range(self.opponentBottomCardsLayout.count())):
            self.opponentBottomCardsLayout.itemAt(i).widget().deleteLater()

        for card in bottomCards:
            button = QLabel()
            button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            button.setStyleSheet("border: 0px solid black; background-color: transparent;")
            pixmap = QPixmap(r"_internal\palaceData\cards\back.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            button.setPixmap(pixmap)
            button.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.opponentBottomCardsLayout.addWidget(button)
        if not bottomCards:
            self.placeholder = QLabel()
            self.placeholder.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            self.opponentBottomCardsLayout.addWidget(self.placeholder)

    def confirmTopCardSelection(self):
        if self.controller.isHost:
            playerIndex = 0
        else:
            playerIndex = 1
        player = self.controller.players[playerIndex]
        for card, _ in self.chosenCards:
            player.topCards.append((card[0], card[1], True, False))
        for card, cardIndex in sorted(self.chosenCards, key=lambda x: x[1], reverse=True):
            del player.hand[cardIndex]

        if self.controller.isHost:
            self.updatePlayerBottomCardButtons(player.bottomCards)
            self.updatePlayerTopCardButtons(player.topCards)
            self.updatePlayerHandButtons(player.hand)
            self.controller.connection.sendToClient({
                'action': 'confirmTopCards',
                'playerIndex': playerIndex,
                'topCards': player.topCards,
                'bottomCards': player.bottomCards,
                'hand': player.hand
            })
        else:
            self.updatePlayerBottomCardButtons(player.bottomCards)
            self.updatePlayerTopCardButtons(player.topCards)
            self.updatePlayerHandButtons(player.hand)
            self.controller.connection.sendToServer({
                'action': 'confirmTopCards',
                'playerIndex': playerIndex,
                'topCards': player.topCards,
                'bottomCards': player.bottomCards,
                'hand': player.hand
            })
        self.confirmButton.setDisabled(True)
        self.disablePlayerHand()
    
    def updateUI(self, currentPlayer, deckSize, pile):
        self.enableOpponentHandNotClickable()
        if self.controller.topCardSelectionPhase:
            self.currentPlayerLabel.setText(f"Select your 3 Top cards...")
            self.confirmButton.setEnabled(len(self.chosenCards) == 3)
        else:
            self.confirmButton.setVisible(False)
            self.placeButton.setVisible(True)
            self.deckLabel.setVisible(True)
            self.currentPlayerLabel.setVisible(True)
            self.pickUpPileButton.setVisible(True)
            self.currentPlayerLabel.setText("Current Player: ")
            self.pileLabel.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            self.currentPlayerLabel.setText(f"Current Player: {currentPlayer.name}")

            if deckSize:
                self.deckLabel.setText(f"Draw Deck:\n\n{deckSize} cards remaining")
            else:
                self.deckLabel.setText("Draw Deck:\n\nEmpty")

            if self.pileLabel.text() != "Bombed!!!" and not pile:
                self.pileLabel.setText("Pile: Empty")
            
            if pile:
                topCard = pile[-1]
                pixmap = QPixmap(fr"_internal/palaceData/cards/{topCard[0].lower()}_of_{topCard[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.pileLabel.setPixmap(pixmap)

            self.placeButton.setEnabled(len(self.controller.selectedCards) > 0)
       
    def revealCard(self, cardLabel, card):
        pixmap = QPixmap(fr"_internal/palaceData/cards/{card[0].lower()}_of_{card[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        cardLabel.setPixmap(pixmap)

    def showTopCardSelection(self):
        self.chosenCards = []
        self.cardButtons = []

    def selectTopCard(self, cardIndex, button):
        if self.controller.isHost:
            playerIndex = 0 
        else:
            playerIndex = 1
        card = self.controller.players[playerIndex].hand[cardIndex]
        if (card, cardIndex) in self.chosenCards:
            self.chosenCards.remove((card, cardIndex))
            button.setStyleSheet("border: 0px solid black; background-color: transparent;")
        else:
            if len(self.chosenCards) < 3:
                self.chosenCards.append((card, cardIndex))
                button.setStyleSheet("border: 0px solid black; background-color: blue;")
        self.confirmButton.setEnabled(len(self.chosenCards) == 3)

    def clearSelectionLayout(self):
        self.chosenCards = []
        self.cardButtons = []
        self.confirmButton.setEnabled(False)
        self.placeButton.setEnabled(False)
        
        # Clear player hand layout
        while self.playerHandLayout.count():
            item = self.playerHandLayout.takeAt(0)
            widget = item.widget()
            if widget is None or (isinstance(widget, QLabel) and widget.pixmap() is None):  # Check if it's the spacer
                continue
            widget.deleteLater()
        
        # Clear opponent hand layout
        while self.opponentHandLayout.count():
            item = self.opponentHandLayout.takeAt(0)
            widget = item.widget()
            if widget is None or (isinstance(widget, QLabel) and widget.pixmap() is None):  # Check if it's the spacer
                continue
            widget.deleteLater()
        
        # Clear player top cards layout
        while self.topCardsLayout.count():
            item = self.topCardsLayout.takeAt(0)
            widget = item.widget()
            if widget is None or (isinstance(widget, QLabel) and widget.pixmap() is None):  # Check if it's the spacer
                continue
            widget.deleteLater()
        
        # Clear player bottom cards layout
        while self.bottomCardsLayout.count():
            item = self.bottomCardsLayout.takeAt(0)
            widget = item.widget()
            if widget is None or (isinstance(widget, QLabel) and widget.pixmap() is None):  # Check if it's the spacer
                continue
            widget.deleteLater()
        
        # Clear opponent top cards layout
        while self.opponentTopCardsLayout.count():
            item = self.opponentTopCardsLayout.takeAt(0)
            widget = item.widget()
            if widget is None or (isinstance(widget, QLabel) and widget.pixmap() is None):  # Check if it's the spacer
                continue
            widget.deleteLater()
        
        # Clear opponent bottom cards layout
        while self.opponentBottomCardsLayout.count():
            item = self.opponentBottomCardsLayout.takeAt(0)
            widget = item.widget()
            if widget is None or (isinstance(widget, QLabel) and widget.pixmap() is None):  # Check if it's the spacer
                continue
            widget.deleteLater()

    def enablePlayerHand(self):
        for i in range(self.playerHandLayout.count()):
            widget = self.playerHandLayout.itemAt(i).widget()
            if widget is None or (isinstance(widget, QLabel) and widget.pixmap() is None):  # Check if it's the spacer
                continue
            widget.setEnabled(True)

    def disablePlayerHand(self):
        for i in range(self.playerHandLayout.count()):
            widget = self.playerHandLayout.itemAt(i).widget()
            if widget is None or (isinstance(widget, QLabel) and widget.pixmap() is None):  # Check if it's the spacer
                continue
            widget.setEnabled(False)

    def enableOpponentHandNotClickable(self):
        for i in range(self.opponentHandLayout.count()):
            widget = self.opponentHandLayout.itemAt(i).widget()
            if widget:
                widget.setEnabled(True)
                widget.mousePressEvent = lambda event: None 

    def closeEvent(self, event):
        self.controller.closeConnections()
        event.accept()
    
class GameController(QObject):
    playAgainRequested = pyqtSignal()
    mainMenuRequested = pyqtSignal()
    exitRequested = pyqtSignal()
    gameOverSignal = pyqtSignal(str)

    def __init__(self, numPlayers, difficulty, connection=None, isHost=False):
        super().__init__()
        self.numPlayers = numPlayers
        self.difficulty = difficulty
        self.isHost = isHost
        if connection is None:
            self.communicator = SignalCommunicator()
        else:
            self.communicator = connection.communicator
        self.communicator.startGameSignal.connect(self.proceedWithGameSetup)
        self.communicator.proceedWithGameSetupSignal.connect(self.proceedWithGameSetupOnMainThread)
        self.communicator.updateUISignal.connect(self.updateUI) 
        if isHost:
            self.playerType = "Player 1" 
        else:
            self.playerType = "Player 2"
        self.view = GameView(self, self.playerType, self.communicator)
        self.players = [Player("Player 1"), Player("Player 2")]
        self.sevenSwitch = False
        self.deck = []
        self.pile = []
        self.currentPlayerIndex = 0
        self.selectedCards = []
        self.playCardButtons = []
        self.topCardSelectionPhase = True
        self.connection = connection
        self.setupGame()
        self.gameOver = False

        self.communicator.updateDeckSignal.connect(self.receiveDeckFromServer)
    
        self.playAgainRequested.connect(self.handlePlayAgain)
        self.mainMenuRequested.connect(self.handleMainMenu)
        self.exitRequested.connect(QCoreApplication.instance().quit)
        self.playAgainCount = 0
        
        self.gameOverSignal.connect(self.stopTimer)
        self.gameOverSignal.connect(self.showGameOverDialog)
    
    def showGameOverDialog(self, winnerName):
        dialog = GameOverDialog(winnerName, self.view)
        dialog.playAgainSignal.connect(self.requestPlayAgain)
        dialog.mainMenuSignal.connect(self.mainMenuRequested)
        dialog.exitSignal.connect(self.exitRequested)
        dialog.exec()

    def requestPlayAgain(self):
        self.playAgainCount += 1
        if self.playAgainCount == 2:
            self.playAgainCount = 0
            self.resetGame()
            self.setupGame()
            self.notifyReset()
        else:
            data = {'action': 'playAgainRequest'}
            if self.isHost:
                self.connection.sendToClient(data)
            else:
                self.connection.sendToServer(data)

    def handlePlayAgain(self):
        self.playAgainCount += 1
        if self.playAgainCount == 2:
            self.playAgainCount = 0
            self.resetGame()
            self.setupGame()
            self.notifyReset()
        elif not self.isHost:
            data = {'action': 'playAgainRequest'}
            self.connection.sendToServer(data)

    def notifyReset(self):
        data = {'action': 'resetGame'}
        if self.isHost:
            self.connection.sendToClient(data)
        else:
            self.connection.sendToServer(data)

    def resetGame(self):
        self.deck = []
        self.pile = []
        self.currentPlayerIndex = 0
        self.selectedCards = []
        self.playCardButtons = []
        self.topCardSelectionPhase = True
        self.players = [Player("Player 1"), Player("Player 2")]
        self.view.clearSelectionLayout()

    def handleMainMenu(self):
        self.closeConnections()
        self.view.close()
        self.mainMenuRequested.emit()
    
    def stopTimer(self):
        if hasattr(self, 'timer'):
            self.timer.stop()
    
    def startGameLoop(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.gameLoop)
        self.timer.start(1000)  # Run the game loop every second

    def gameLoop(self):
        currentPlayer = self.players[self.currentPlayerIndex]
        self.view.updateUI(currentPlayer, len(self.deck), self.pile)

    def pickUpPile(self):
        if not self.pile:
            return
        currentPlayer = self.players[self.currentPlayerIndex]
        currentPlayer.pickUpPile(self.pile)
        print(f"{currentPlayer.name} picks up the pile\n")
        self.view.pileLabel.setText("Pile: Empty")
        self.sevenSwitch = False
        self.updateUI()
        self.changeTurn()
        self.sendGameState()
        self.view.placeButton.setText("Opponent's Turn...")

    def setupGame(self):
        if self.isHost:
            self.deck = self.createDeck()
            random.shuffle(self.deck)
            self.dealInitialCards(self.players[0])
            self.dealInitialCards(self.players[1])
            self.sendDeckToClient()
            self.view.updatePlayerHandButtons(self.players[0].hand)
        else:
            self.view.updatePlayerHandButtons(self.players[1].hand)
        self.view.showTopCardSelection()

    def proceedWithGameSetup(self):
        self.communicator.proceedWithGameSetupSignal.emit()

    def proceedWithGameSetupOnMainThread(self):
        self.topCardSelectionPhase = False
        self.updateUI()
        self.view.pileLabel.setText("Pile: Empty")
        if self.playerType == "Player 2":
            self.view.disablePlayerHand()
            self.view.pickUpPileButton.setDisabled(True)
        self.startGameLoop()

    def createDeck(self):
        suits = ['clubs', 'spades']
        return [(rank, suit, False, False) for rank in RANKS for suit in suits]

    def dealInitialCards(self, player):
        player.bottomCards = [(card[0], card[1], False, True) for card in self.deck[:3]]
        player.hand = self.deck[3:9]
        self.deck = self.deck[9:]

    def sendDeckToClient(self):
        data = {'action': 'deckSync', 
                'deck': self.deck, 
                'player2bot': self.players[1].bottomCards,
                'player2top': self.players[1].topCards,
                'player2hand': self.players[1].hand
            }
        self.connection.sendToClient(data)
                
    def receiveDeckFromServer(self, data):
        self.deck = data['deck']
        self.players[1].bottomCards = data['player2bot']
        self.players[1].topCards = data['player2top']
        self.players[1].hand = data['player2hand']
        self.view.updatePlayerHandButtons(self.players[1].hand)
        self.view.placeButton.setText("Opponent's Turn...")

    def checkBothPlayersConfirmed(self):
        time.sleep(1)
        if all(player.topCards for player in self.players):
            self.sendStartGameSignal()
            self.proceedWithGameSetup()
    
    def sendStartGameSignal(self):
        data = {'action': 'startGame', 'gameState': ""}
        if self.isHost:
            self.connection.sendToClient(data)
        else:
            self.connection.sendToServer(data)
    
    def updateUI(self):
        self.view.enableOpponentHandNotClickable()
        currentPlayer = self.players[self.currentPlayerIndex]
        if not self.topCardSelectionPhase:
            self.view.updateUI(currentPlayer, len(self.deck), self.pile)
            if self.isHost:
                self.view.updatePlayerHandButtons(self.players[0].hand)
                self.view.updateOpponentHandButtons(self.players[1].hand)
                self.view.updatePlayerTopCardButtons(self.players[0].topCards)
                self.view.updateOpponentTopCardButtons(self.players[1].topCards)
                self.view.updatePlayerBottomCardButtons(self.players[0].bottomCards)
                self.view.updateOpponentBottomCardButtons(self.players[1].bottomCards)
            else:
                self.view.updatePlayerHandButtons(self.players[1].hand)
                self.view.updateOpponentHandButtons(self.players[0].hand)
                self.view.updatePlayerTopCardButtons(self.players[1].topCards)
                self.view.updateOpponentTopCardButtons(self.players[0].topCards)
                self.view.updatePlayerBottomCardButtons(self.players[1].bottomCards)
                self.view.updateOpponentBottomCardButtons(self.players[0].bottomCards)
        if self.isSessionPlayer():
            self.updatePlayableCards()
        else:
            self.view.disablePlayerHand()

    def prepareCardPlacement(self, cardIndex, cardLabel):
        card = self.players[self.currentPlayerIndex].hand[cardIndex]
        if (card, cardLabel) in self.selectedCards:
            self.selectedCards.remove((card, cardLabel))
            cardLabel.setStyleSheet("border: 0px solid black; background-color: transparent;")
        else:
            self.selectedCards.append((card, cardLabel))
            cardLabel.setStyleSheet("border: 0px solid black; background-color: blue;")

        selectedCardRank = card[0]
        handIndex = 0
        if not self.selectedCards:
            for i in range(self.view.playerHandLayout.count()):
                lbl = self.view.playerHandLayout.itemAt(i).widget()
                if lbl is None or (isinstance(lbl, QLabel) and lbl.pixmap() is None):
                    continue
                if handIndex >= len(self.players[self.currentPlayerIndex].hand):
                    break
                handCard = self.players[self.currentPlayerIndex].hand[handIndex]
                if handCard[3] or self.isCardPlayable(handCard):
                    lbl.setEnabled(True)
                handIndex += 1
        else:
            handIndex = 0
            for i in range(self.view.playerHandLayout.count()):
                lbl = self.view.playerHandLayout.itemAt(i).widget()
                if lbl is None or (isinstance(lbl, QLabel) and lbl.pixmap() is None):
                    continue
                if handIndex >= len(self.players[self.currentPlayerIndex].hand):
                    break
                handCard = self.players[self.currentPlayerIndex].hand[handIndex]
                if handCard[0] == selectedCardRank or (handCard, lbl) in self.selectedCards:
                    lbl.setEnabled(True)
                elif not handCard[3]:
                    lbl.setEnabled(False)
                handIndex += 1
        self.view.placeButton.setEnabled(len(self.selectedCards) > 0)
        if self.view.placeButton.text() == "Place":
            self.view.placeButton.setText("Select A Card")
        else:
            self.view.placeButton.setText("Place")

    def isCardPlayable(self, card):
        if self.pile:
            topCard = self.pile[-1]
        else:
            topCard = None
        if self.sevenSwitch:
            return VALUES[card[0]] <= 7 or card[0] in ['2', '10']
        if not topCard:
            return True
        return card[0] == '2' or card[0] == '10' or VALUES[card[0]] >= VALUES[topCard[0]]

    def placeCard(self):
        currentPlayer = self.players[self.currentPlayerIndex]
        playedCards = []
        pickUp = False

        for card, button in sorted(self.selectedCards, key=lambda x: currentPlayer.hand.index(x[0])):
            if card[3] and not self.isCardPlayable(card):
                playedCards.append(card)
                for i, card in enumerate(playedCards):
                    self.pile.append(currentPlayer.hand.pop(currentPlayer.hand.index(playedCards[i])))
                    self.pile[-1] = (card[0], card[1], card[2], False)
                    self.view.revealCard(button, card)
                pickUp = True
                button.setParent(None)
                button.deleteLater()
            else:
                playedCards.append(card)
                currentPlayer.playCard(currentPlayer.hand.index(card), self.pile)
                self.view.revealCard(button, card)
                button.setParent(None)
                button.deleteLater()

        if pickUp:
            topCard = self.pile[-1]
            pixmap = QPixmap(fr"_internal/palaceData/cards/{topCard[0].lower()}_of_{topCard[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.view.pileLabel.setPixmap(pixmap)
            QCoreApplication.processEvents()
            time.sleep(1)
            currentPlayer.pickUpPile(self.pile)
            print(f"{currentPlayer.name} picks up the pile\n")
            self.view.pileLabel.setText("Pile: Empty")
            self.sevenSwitch = False
            for card in reversed(currentPlayer.hand):
                if card[3]:
                    currentPlayer.bottomCards.append(currentPlayer.hand.pop(currentPlayer.hand.index(card)))
            self.updateUI()
            self.changeTurn()
            self.sendGameState()
            self.view.placeButton.setText("Opponent's Turn...")
            return

        self.selectedCards = []
        print(f"{currentPlayer.name} plays {', '.join([f'{card[0]} of {card[1]}' for card in playedCards])}\n")

        while len(currentPlayer.hand) < 3 and self.deck:
            currentPlayer.hand.append(self.deck.pop(0))

        self.view.updatePlayerHandButtons(currentPlayer.hand)

        if self.checkFourOfAKind():
            print("Four of a kind! Clearing the pile.\n")
            self.sevenSwitch = False
            topCard = self.pile[-1]
            pixmap = QPixmap(fr"_internal/palaceData/cards/{topCard[0].lower()}_of_{topCard[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.view.pileLabel.setPixmap(pixmap)
            self.updateUI()
            self.checkGameState()
            if self.gameOver:
                self.sendGameState()
                self.gameOverSignal.emit(currentPlayer.name)
                return
            self.sendGameState()
            self.pile.clear()
            self.updateUI()
            self.view.pileLabel.setText("Bombed!!!")
            self.view.placeButton.setText("Select A Card")
            return
        
        if '2' in [card[0] for card in playedCards]:
            self.sevenSwitch = False
            topCard = self.pile[-1]
            pixmap = QPixmap(fr"_internal/palaceData/cards/{topCard[0].lower()}_of_{topCard[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.view.pileLabel.setPixmap(pixmap)
            self.updateUI()
            self.checkGameState()
            if self.gameOver:
                self.sendGameState()
                self.gameOverSignal.emit(currentPlayer.name)
                return
            self.sendGameState()
            self.view.placeButton.setText("Select A Card")
        elif '10' in [card[0] for card in playedCards]:
            self.sevenSwitch = False
            topCard = self.pile[-1]
            pixmap = QPixmap(fr"_internal/palaceData/cards/{topCard[0].lower()}_of_{topCard[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.view.pileLabel.setPixmap(pixmap)
            self.updateUI()
            self.checkGameState()
            if self.gameOver:
                self.sendGameState()
                self.gameOverSignal.emit(currentPlayer.name)
                return
            self.sendGameState()
            self.pile.clear()
            self.updateUI()
            self.view.pileLabel.setText("Bombed!!!")
            self.view.placeButton.setText("Select A Card")
        else:
            if '7' in [card[0] for card in playedCards]:
                self.sevenSwitch = True
            else:
                self.sevenSwitch = False
            self.view.placeButton.setEnabled(False)
            topCard = self.pile[-1]
            pixmap = QPixmap(fr"_internal/palaceData/cards/{topCard[0].lower()}_of_{topCard[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.view.pileLabel.setPixmap(pixmap)
            self.updateUI()
            self.checkGameState()
            if self.gameOver:
                self.sendGameState()
                self.gameOverSignal.emit(currentPlayer.name)
                return
            self.changeTurn()
            self.sendGameState()
            self.view.placeButton.setText("Opponent's Turn...")

    def changeTurn(self):
        self.currentPlayerIndex = (self.currentPlayerIndex + 1) % len(self.players)
        self.selectedCards = []
        self.updateUI()
        self.view.disablePlayerHand()
        self.view.pickUpPileButton.setEnabled(False)

    def checkFourOfAKind(self):
        if len(self.pile) < 4:
            return False
        return len(set(card[0] for card in self.pile[-4:])) == 1

    def isSessionPlayer(self):
        if self.isHost:
            return self.currentPlayerIndex == 0 and self.playerType == "Player 1"
        else:
            return self.currentPlayerIndex == 1 and self.playerType == "Player 2"
    
    def checkGameState(self):
        currentPlayer = self.players[self.currentPlayerIndex]
        if not currentPlayer.hand and not self.deck:
            if currentPlayer.topCards:
                currentPlayer.hand = currentPlayer.topCards
                currentPlayer.topCards = []
                if self.isSessionPlayer():
                    self.view.updatePlayerHandButtons(currentPlayer.hand)
                    self.view.updatePlayerTopCardButtons(currentPlayer.topCards)
                else:
                    self.view.updateOpponentHandButtons(currentPlayer.hand)
                    self.view.updateOpponentTopCardButtons(currentPlayer.topCards)
            elif currentPlayer.bottomCards:
                currentPlayer.hand = currentPlayer.bottomCards
                currentPlayer.bottomCards = []
                if self.isSessionPlayer():
                    self.view.updatePlayerHandButtons(currentPlayer.hand)
                    self.view.updatePlayerBottomCardButtons(currentPlayer.bottomCards)
                else:
                    self.view.updateOpponentHandButtons(currentPlayer.hand)
                    self.view.updateOpponentBottomCardButtons(currentPlayer.bottomCards)
            elif not currentPlayer.bottomCards:
                placeholder = QLabel()
                placeholder.setFixedSize(BUTTON_HEIGHT, BUTTON_WIDTH)
                currentPlayer.hand.append(placeholder)
                self.view.pickUpPileButton.setDisabled(True)
                self.view.placeButton.setDisabled(True)
                for button in self.playCardButtons:
                    button.setDisabled(True)
                print(f"{currentPlayer.name} wins!")
                self.gameOver = True

    def updatePlayableCards(self):
        currentPlayer = self.players[self.currentPlayerIndex]
        handIndex = 0  # To keep track of the actual card index in the player's hand

        for i in range(self.view.playerHandLayout.count()):
            item = self.view.playerHandLayout.itemAt(i)
            if item is None:
                continue
            lbl = item.widget()
            if lbl is None or (isinstance(lbl, QLabel) and lbl.pixmap() is None):  # Check if it's the spacer
                continue  # Skip the spacer

            if handIndex >= len(currentPlayer.hand):
                break  # Prevent index out of range error

            handCard = currentPlayer.hand[handIndex]
            if handCard[0] in ['2', '10'] or handCard[3] or self.isCardPlayable(handCard):
                lbl.setEnabled(True)
            else:
                lbl.setEnabled(False)
            
            handIndex += 1
        
    def sendGameState(self):
        if self.connection:
            if self.gameOver:
                data = {
                    'action': 'gameOver',
                    'winner': self.players[self.currentPlayerIndex].name
                }
                if isinstance(self.connection, Server):
                    self.connection.sendToClient(data)
                else:
                    self.connection.sendToServer(data)
            else:
                data = self.serializeGameState()
                if isinstance(self.connection, Server):
                    self.connection.sendToClient(data)
                else:
                    self.connection.sendToServer(data)

    def receiveGameState(self, data):
        self.deserializeGameState(data)
        if self.pile and self.pile[-1][0] == "2":
            pass
        elif self.pile and self.pile[-1][0] == "10":
            self.pile.clear()
            self.view.pileLabel.setText("Bombed!!!")
        else:
            self.view.placeButton.setText("Select a Card")
            self.view.pickUpPileButton.setEnabled(True)

    def serializeGameState(self):
        return {
            'action': 'playCard',
            'players': [
                {
                    'hand': self.players[0].hand,
                    'topCards': self.players[0].topCards,
                    'bottomCards': self.players[0].bottomCards
                },
                {
                    'hand': self.players[1].hand,
                    'topCards': self.players[1].topCards,
                    'bottomCards': self.players[1].bottomCards
                }
            ],
            'deck': self.deck,
            'pile': self.pile,
            'seven': self.sevenSwitch,
            'currentPlayerIndex': self.currentPlayerIndex,
        }

    def deserializeGameState(self, data):
        self.deck = data['deck']
        self.pile = data['pile']
        self.currentPlayerIndex = data['currentPlayerIndex']
        self.sevenSwitch = data['seven']
        self.players[0].hand = data['players'][0]['hand']
        self.players[0].topCards = data['players'][0]['topCards']
        self.players[0].bottomCards = data['players'][0]['bottomCards']
        self.players[1].hand = data['players'][1]['hand']
        self.players[1].topCards = data['players'][1]['topCards']
        self.players[1].bottomCards = data['players'][1]['bottomCards']
        self.communicator.updateUISignal.emit()
    
    def closeConnections(self):
        if self.connection:
            self.connection.close()
       
def main():
    global scalingFactorWidth
    global scalingFactorHeight
    app = QApplication(sys.argv)
    app.setStyleSheet(Dark)
    screen = app.primaryScreen()
    screenSize = screen.size()
    screenWidth = screenSize.width()
    screenHeight = screenSize.height()
    scalingFactorWidth = screenWidth / 1920
    scalingFactorHeight = screenHeight / 1080
    communicator = SignalCommunicator()
    homeScreen = HomeScreen(communicator)
    homeScreen.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()