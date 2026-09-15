#!/usr/bin/env python3
import os
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")

from gi.repository import Gtk, Gst, GLib


class Player(Gtk.Window):
    def __init__(self):
        super().__init__(title="Аудиоплеер")
        self.set_border_width(10)
        self.set_default_size(400, 320)  # Скорректировали высоту окна

        Gst.init(None)

        self.player = Gst.ElementFactory.make("playbin", "player")

        self.playlist = []
        self.current_track_index = 0
        self.is_seeking = False  
        self.timeout_id = None   

        # Главный вертикальный контейнер
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(main_box)

        # --- БЛОК КНОПОК УПРАВЛЕНИЯ ---
        controls_box = Gtk.Box(spacing=6)
        
        self.open_button = Gtk.Button(label="Открыть")
        self.add_button = Gtk.Button(label="➕ Добавить")  
        self.prev_button = Gtk.Button(label="⏮")
        self.play_button = Gtk.Button(label="Воспроизвести")
        self.next_button = Gtk.Button(label="⏭")
        self.stop_button = Gtk.Button(label="Стоп")

        self.open_button.connect("clicked", self.open_files)
        self.add_button.connect("clicked", self.append_files)
        self.prev_button.connect("clicked", self.prev_track)
        self.play_button.connect("clicked", self.play_pause)
        self.next_button.connect("clicked", self.next_track)
        self.stop_button.connect("clicked", self.stop)
        self.connect("destroy", self.on_destroy)

        controls_box.pack_start(self.open_button, True, True, 0)
        controls_box.pack_start(self.add_button, True, True, 0)
        controls_box.pack_start(self.prev_button, False, False, 2)
        controls_box.pack_start(self.play_button, True, True, 0)
        controls_box.pack_start(self.next_button, False, False, 2)
        controls_box.pack_start(self.stop_button, True, True, 0)
        
        main_box.pack_start(controls_box, False, False, 0)

        # --- БЛОК ПЕРЕМОТКИ (ТАЙМЛАЙН) ---
        timeline_box = Gtk.Box(spacing=6)
        
        self.timeline = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.timeline.set_draw_value(False)  
        
        self.timeline.connect("button-press-event", self.on_timeline_press)
        self.timeline.connect("button-release-event", self.on_timeline_release)
        self.timeline.connect("value-changed", self.on_timeline_changed)
        
        timeline_box.pack_start(self.timeline, True, True, 0)
        main_box.pack_start(timeline_box, False, False, 0)

        # --- ВИЗУАЛЬНЫЙ СПИСОК ТРЕКОВ ---
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.list_box = Gtk.ListBox()
        self.list_box.connect("row-activated", self.on_row_activated)
        
        scrolled_window.add(self.list_box)
        main_box.pack_start(scrolled_window, True, True, 0)

        self.show_all()

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

    # --- РАБОТА С ФАЙЛАМИ ---
    def open_files(self, button):
        filenames = self.run_file_chooser()
        if filenames:
            self.playlist = [Gst.filename_to_uri(f) for f in filenames]
            self.current_track_index = 0
            
            for child in self.list_box.get_children():
                self.list_box.remove(child)
            self.add_to_playlist_ui(filenames)
            
            self.play_current_track()

    def append_files(self, button):
        filenames = self.run_file_chooser()
        if filenames:
            new_uris = [Gst.filename_to_uri(f) for f in filenames]
            playlist_was_empty = len(self.playlist) == 0
            
            self.playlist.extend(new_uris)
            self.add_to_playlist_ui(filenames)
            
            if playlist_was_empty:
                self.current_track_index = 0
                self.play_current_track()

    def run_file_chooser(self):
        dialog = Gtk.FileChooserDialog(
            title="Выберите аудиофайлы", parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        )
        dialog.set_select_multiple(True)
        audio_filter = Gtk.FileFilter()
        audio_filter.set_name("Аудиофайлы")
        audio_filter.add_mime_type("audio/*")
        dialog.add_filter(audio_filter)
        
        response = dialog.run()
        filenames = dialog.get_filenames() if response == Gtk.ResponseType.OK else None
        dialog.destroy()
        return filenames

    def add_to_playlist_ui(self, filenames):
        for f in filenames:
            label = Gtk.Label(label=os.path.basename(f), xalign=0)
            label.set_margin_start(10)
            label.set_margin_end(10)
            label.set_margin_top(5)
            label.set_margin_bottom(5)
            
            row = Gtk.ListBoxRow()
            row.add(label)
            self.list_box.add(row)
        self.list_box.show_all()

    # --- СИСТЕМА ВОСПРОИЗВЕДЕНИЯ ---
    def play_current_track(self):
        self.stop_timeline_timer()
        
        if 0 <= self.current_track_index < len(self.playlist):
            uri = self.playlist[self.current_track_index]
            self.player.set_state(Gst.State.NULL)
            self.player.set_property("uri", uri)
            self.player.set_state(Gst.State.PLAYING)
            self.play_button.set_label("Пауза")
            
            row = self.list_box.get_row_at_index(self.current_track_index)
            if row:
                self.list_box.select_row(row)
                
            self.start_timeline_timer()
        else:
            self.stop(None)

    def play_pause(self, button):
        if not self.playlist:
            return

        state = self.player.get_state(0).state
        if state == Gst.State.PLAYING:
            self.player.set_state(Gst.State.PAUSED)
            self.play_button.set_label("Продолжить")
            self.stop_timeline_timer()
        else:
            self.player.set_state(Gst.State.PLAYING)
            self.play_button.set_label("Пауза")
            self.start_timeline_timer()

    def stop(self, button):
        self.player.set_state(Gst.State.NULL)
        self.play_button.set_label("Воспроизвести")
        self.stop_timeline_timer()
        self.timeline.set_value(0)

    def next_track(self, button):
        if self.playlist:
            self.current_track_index = (self.current_track_index + 1) % len(self.playlist)
            self.play_current_track()

    def prev_track(self, button):
        if self.playlist:
            self.current_track_index = (self.current_track_index - 1) % len(self.playlist)
            self.play_current_track()

    def on_row_activated(self, list_box, row):
        self.current_track_index = row.get_index()
        self.play_current_track()

    # --- УПРАВЛЕНИЕ ПЕРЕМОТКОЙ ---
    def start_timeline_timer(self):
        if self.timeout_id is None:
            self.timeout_id = GLib.timeout_add(1000, self.update_timeline)

    def stop_timeline_timer(self):
        if self.timeout_id is not None:
            GLib.source_remove(self.timeout_id)
            self.timeout_id = None

    def update_timeline(self):
        if self.is_seeking:
            return True

        success_dur, duration = self.player.query_duration(Gst.Format.TIME)
        success_pos, position = self.player.query_position(Gst.Format.TIME)

        if success_dur and success_pos and duration > 0:
            percentage = (position / duration) * 100
            self.timeline.handler_block_by_func(self.on_timeline_changed)
            self.timeline.set_value(percentage)
            self.timeline.handler_unblock_by_func(self.on_timeline_changed)
            
        return True

    def on_timeline_press(self, widget, event):
        self.is_seeking = True

    def on_timeline_release(self, widget, event):
        self.is_seeking = False
        self.on_timeline_changed(self.timeline)

    def on_timeline_changed(self, range_widget):
        success, duration = self.player.query_duration(Gst.Format.TIME)
        if success and duration > 0:
            percentage = self.timeline.get_value()
            target_position = int((percentage / 100) * duration)
            
            self.player.seek_simple(
                Gst.Format.TIME, 
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, 
                target_position
            )

    # --- СООБЩЕНИЯ И ВЫХОД ---
    def on_message(self, bus, message):
        if message.type == Gst.MessageType.EOS:
            self.current_track_index += 1
            GLib.idle_add(self.play_current_track)
        elif message.type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            print("Ошибка:", error)
            self.current_track_index += 1
            GLib.idle_add(self.play_current_track)

    def on_destroy(self, widget):
        self.stop_timeline_timer()
        self.player.set_state(Gst.State.NULL)
        Gtk.main_quit()


if __name__ == "__main__":
    Player()
    Gtk.main()
