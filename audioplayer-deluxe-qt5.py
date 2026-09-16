#!/usr/bin/env python3
import os
import sys
from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QPushButton, QSlider, QListWidget, QFileDialog
)

class Player(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Аудиоплеер")
        self.resize(400, 320)

        # Инициализация медиа-плеера PyQt5
        self.player = QMediaPlayer()

        # Списки для путей к файлам
        self.playlist = []
        self.current_track_index = 0
        self.is_seeking = False

        # Подключение сигналов плеера
        self.player.positionChanged.connect(self.update_timeline)
        self.player.durationChanged.connect(self.update_duration)
        self.player.stateChanged.connect(self.on_state_changed)

        # --- ИНТЕРФЕЙС ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Блок кнопок управления
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(6)

        self.open_button = QPushButton("Открыть")
        self.add_button = QPushButton("➕ Добавить")
        self.prev_button = QPushButton("⏮")
        self.play_button = QPushButton("Воспроизвести")
        self.next_button = QPushButton("⏭")
        self.stop_button = QPushButton("Стоп")

        # Привязка событий клика
        self.open_button.clicked.connect(self.open_files)
        self.add_button.clicked.connect(self.append_files)
        self.prev_button.clicked.connect(self.prev_track)
        self.play_button.clicked.connect(self.play_pause)
        self.next_button.clicked.connect(self.next_track)
        self.stop_button.clicked.connect(self.stop)

        controls_layout.addWidget(self.open_button)
        controls_layout.addWidget(self.add_button)
        controls_layout.addWidget(self.prev_button)
        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.next_button)
        controls_layout.addWidget(self.stop_button)
        main_layout.addLayout(controls_layout)

        # Блок перемотки (Слайдер)
        self.timeline = QSlider(Qt.Horizontal)
        self.timeline.setRange(0, 100)
        
        # Блокируем обновление позиции, пока пользователь тащит ползунок
        self.timeline.sliderPressed.connect(self.on_timeline_press)
        self.timeline.sliderReleased.connect(self.on_timeline_release)
        self.timeline.sliderMoved.connect(self.on_timeline_moved)

        main_layout.addWidget(self.timeline)

        # Визуальный список треков
        self.list_widget = QListWidget()
        self.list_widget.itemActivated.connect(self.on_row_activated)
        main_layout.addWidget(self.list_widget)

    # --- РАБОТА С ФАЙЛАМИ ---
    def run_file_chooser(self):
        file_filter = "Аудиофайлы (*.mp3 *.wav *.ogg *.m4a *.flac)"
        filenames, _ = QFileDialog.getOpenFileNames(
            self, "Выберите аудиофайлы", "", file_filter
        )
        return filenames

    def open_files(self):
        filenames = self.run_file_chooser()
        if filenames:
            self.playlist = filenames
            self.current_track_index = 0
            
            self.list_widget.clear()
            self.add_to_playlist_ui(filenames)
            self.play_current_track()

    def append_files(self):
        filenames = self.run_file_chooser()
        if filenames:
            playlist_was_empty = len(self.playlist) == 0
            self.playlist.extend(filenames)
            self.add_to_playlist_ui(filenames)
            
            if playlist_was_empty:
                self.current_track_index = 0
                self.play_current_track()

    def add_to_playlist_ui(self, filenames):
        for f in filenames:
            self.list_widget.addItem(os.path.basename(f))

    # --- СИСТЕМА ВОСПРОИЗВЕДЕНИЯ ---
    def play_current_track(self):
        if 0 <= self.current_track_index < len(self.playlist):
            file_path = self.playlist[self.current_track_index]
            
            # Передаем абсолютный путь напрямую через QUrl.fromLocalFile
            url = QUrl.fromLocalFile(os.path.abspath(file_path))
            content = QMediaContent(url)
            
            self.player.setMedia(content)
            self.player.play()
            self.play_button.setText("Пауза")
            self.list_widget.setCurrentRow(self.current_track_index)
        else:
            self.stop()


    def play_pause(self):
        if not self.playlist:
            return

        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.play_button.setText("Продолжить")
        else:
            self.player.play()
            self.play_button.setText("Пауза")

    def stop(self):
        self.player.stop()
        self.play_button.setText("Воспроизвести")
        self.timeline.setValue(0)

    def next_track(self):
        if self.playlist:
            self.current_track_index = (self.current_track_index + 1) % len(self.playlist)
            self.play_current_track()

    def prev_track(self):
        if self.playlist:
            self.current_track_index = (self.current_track_index - 1) % len(self.playlist)
            self.play_current_track()

    def on_row_activated(self, item):
        self.current_track_index = self.list_widget.row(item)
        self.play_current_track()

    # --- УПРАВЛЕНИЕ ПЕРЕМОТКОЙ ---
    def update_timeline(self, position):
        if self.is_seeking or self.player.duration() == 0:
            return
        # Переводим текущую позицию в проценты (0-100)
        percentage = int((position / self.player.duration()) * 100)
        self.timeline.setValue(percentage)

    def update_duration(self, duration):
        if duration > 0 and not self.is_seeking:
            self.update_timeline(self.player.position())

    def on_timeline_press(self):
        self.is_seeking = True

    def on_timeline_release(self):
        self.is_seeking = False
        self.on_timeline_moved(self.timeline.value())

    def on_timeline_moved(self, value):
        if self.player.duration() > 0:
            target_position = int((value / 100) * self.player.duration())
            self.player.setPosition(target_position)

    # --- АВТОПЕРЕКЛЮЧЕНИЕ ---
    def on_state_changed(self, state):
        # В PyQt5 отслеживание окончания трека идет через статус медиа или остановку состояния плеера
        # Когда трек доиграл до конца в обычном режиме, плеер переходит в StoppedState, 
        # при этом позиция воспроизведения равна нулю или длительности трека.
        if state == QMediaPlayer.StoppedState and self.player.position() == self.player.duration() and self.player.duration() > 0:
            self.next_track()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = Player()
    player.show()
    sys.exit(app.exec_())

