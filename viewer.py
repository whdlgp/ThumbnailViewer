import sys
import os
import json
import subprocess
from datetime import datetime
from enum import Enum

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QAbstractItemView
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from PySide6.QtWidgets import QFileDialog, QGraphicsScene, QGraphicsView
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from qt_material import apply_stylesheet


class SortMode(Enum):
    NAME_ASC = 0
    NAME_DESC = 1
    MTIME_NEW = 2
    MTIME_OLD = 3


DEFAULT_CONFIG = {
    "search_dir": r"Y:/asmr",
    "img_exts": ["png", "jpg", "jpeg", "webp", "bmp"],
    "theme": "dark_teal.xml",
    "default_res": [1280, 720],
    "thumb_size": 200,
    "page_size": 5,
}


def load_config(path):
    config = dict(DEFAULT_CONFIG)

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            config.update(json.load(f))

    return config


class DirectoryManager:
    def __init__(self, root, page_size=5, img_exts=None, data_dir=None):
        self.root = root
        self.page_size = page_size
        self.items = []
        self.filtered_items = []

        exts = img_exts or ["jpg", "jpeg", "png", "bmp", "webp"]
        self.image_exts = {f".{e.lower().lstrip('.')}" for e in exts}

        self.data_dir = data_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.override_file = os.path.join(self.data_dir, "thumb_overrides.json")

        if os.path.exists(self.override_file):
            with open(self.override_file, "r", encoding="utf-8") as f:
                self.overrides = json.load(f)
        else:
            self.overrides = {}

    def set_thumbnail_override(self, directory_path, image_path):
        key = os.path.relpath(os.path.abspath(directory_path), self.root)
        value = os.path.relpath(os.path.abspath(image_path), self.root)
        self.overrides[key] = value

        with open(self.override_file, "w", encoding="utf-8") as f:
            json.dump(self.overrides, f, indent=4)

    def read(self):
        self.items.clear()

        with os.scandir(self.root) as entries:
            for entry in entries:
                if not entry.is_dir(follow_symlinks=False):
                    continue

                stat = entry.stat(follow_symlinks=False)

                self.items.append({
                    "name": entry.name,
                    "path": entry.path,
                    "mtime": stat.st_mtime,
                })

        self.filtered_items = list(self.items)

    def sort(self, mode: SortMode):
        if mode == SortMode.NAME_ASC:
            self.items.sort(key=lambda x: x["name"].lower())

        elif mode == SortMode.NAME_DESC:
            self.items.sort(key=lambda x: x["name"].lower(), reverse=True)

        elif mode == SortMode.MTIME_NEW:
            self.items.sort(key=lambda x: x["mtime"], reverse=True)

        elif mode == SortMode.MTIME_OLD:
            self.items.sort(key=lambda x: x["mtime"])

    def filter(self, query):
        query = (query or "").lower().strip()

        if not query:
            self.filtered_items = list(self.items)
        else:
            self.filtered_items = [i for i in self.items if query in i["name"].lower()]

    def page_count(self):
        if not self.filtered_items:
            return 1
        return max(1, (len(self.filtered_items) + self.page_size - 1) // self.page_size)

    def get_page(self, page):
        start = page * self.page_size
        end = start + self.page_size
        return self.filtered_items[start:end]

    def find_thumbnail(self, directory):
        key = os.path.relpath(os.path.abspath(directory), self.root)
        override = self.overrides.get(key)

        if override:
            override_path = os.path.join(self.root, override)
            if os.path.exists(override_path):
                return override_path

        for current_root, _, files in os.walk(directory):
            for name in files:
                _, ext = os.path.splitext(name)

                if ext.lower() in self.image_exts:
                    return os.path.join(current_root, name)

        return None

    def get_page_thumbnails(self, page):
        result = []

        for item in self.get_page(page):
            result.append({
                "directory": item,
                "thumbnail": self.find_thumbnail(item["path"]),
            })

        return result


class ClickableThumbnail(QLabel):
    def __init__(self, directory_path, manager, thumb_size, parent=None):
        super().__init__(parent)
        self.directory_path = directory_path
        self.manager = manager
        self.thumb_size = thumb_size
        self.setFixedSize(thumb_size, thumb_size)
        self.setAlignment(Qt.AlignCenter)

    def set_pixmap_from_path(self, image_path):
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            pixmap = pixmap.scaled(
                self.thumb_size, self.thumb_size,
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        else:
            pixmap = QPixmap(self.thumb_size, self.thumb_size)
            pixmap.fill(Qt.transparent)

        self.setPixmap(pixmap)

    def mouseDoubleClickEvent(self, event):
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)")
        file_dialog.setDirectory(self.directory_path)

        if file_dialog.exec():
            selected = file_dialog.selectedFiles()

            if selected:
                new_path = selected[0]
                self.manager.set_thumbnail_override(self.directory_path, new_path)
                self.set_pixmap_from_path(new_path)


class ClickableDirName(QLabel):
    def __init__(self, directory_path, parent=None):
        super().__init__(parent)
        self.directory_path = directory_path

    def mouseDoubleClickEvent(self, event):
        subprocess.Popen(["explorer", self.directory_path])


class ThumbnailViewerApp(QMainWindow):
    def __init__(self, manager: DirectoryManager, thumb_size, default_res):
        super().__init__()
        self.manager = manager
        self.thumb_size = thumb_size
        self.default_res = default_res
        self.current_page = 0
        self.name_sort_desc = False
        self.mtime_sort_new = True

        self.manager.read()
        self.manager.sort(SortMode.MTIME_NEW)
        self.manager.filter("")

        self.init_ui()
        self.refresh_tree()

    def init_ui(self):
        self.setWindowTitle("Thumbnail Viewer")
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        layout = QVBoxLayout(self.central_widget)

        self.search_widget = QLineEdit(self.central_widget)
        self.search_widget.setPlaceholderText("Search...")
        self.search_widget.textChanged.connect(self.on_search_changed)
        layout.addWidget(self.search_widget)

        thumb_name_container = QWidget(self.central_widget)
        layout.addWidget(thumb_name_container)

        thumb_name_layout = QHBoxLayout(thumb_name_container)
        thumb_name_layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget(self.central_widget)
        self.tree.setHeaderLabels(["Thumbnail", "Name", "modified"])
        self.tree.setColumnWidth(0, self.thumb_size + 50)
        self.tree.setColumnWidth(1, self.thumb_size + 50)
        self.tree.setSortingEnabled(False)
        self.tree.header().setSectionsClickable(True)
        self.tree.header().sectionClicked.connect(self.on_header_clicked)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tree.verticalScrollBar().setSingleStep(15)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)

        thumb_name_layout.addWidget(self.tree)
        thumb_name_layout.addWidget(self.view)

        pagination_layout = QHBoxLayout()
        self.prev_button = QPushButton("< Prev")
        self.next_button = QPushButton("Next >")
        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignCenter)

        self.prev_button.clicked.connect(self.on_prev_page)
        self.next_button.clicked.connect(self.on_next_page)

        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_button)
        layout.addLayout(pagination_layout)

        self.resize(*self.default_res)
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)

    def refresh_tree(self):
        self.tree.setUpdatesEnabled(False)
        self.tree.clear()

        for entry in self.manager.get_page_thumbnails(self.current_page):
            directory = entry["directory"]
            thumbnail_path = entry["thumbnail"]

            item = QTreeWidgetItem(self.tree)
            item.setData(0, Qt.UserRole, directory["path"])

            thumb_widget = ClickableThumbnail(directory["path"], self.manager, self.thumb_size)
            thumb_widget.set_pixmap_from_path(thumbnail_path)
            self.tree.setItemWidget(item, 0, thumb_widget)

            name_widget = ClickableDirName(directory["path"])
            name_widget.setText(directory["name"])
            self.tree.setItemWidget(item, 1, name_widget)

            modified_str = datetime.fromtimestamp(directory["mtime"]).strftime("%Y-%m-%d %H:%M")
            item.setText(2, modified_str)

        self.tree.setUpdatesEnabled(True)
        self.update_pagination_label()

    def update_pagination_label(self):
        total_pages = self.manager.page_count()
        total_items = len(self.manager.filtered_items)

        start = self.current_page * self.manager.page_size + 1
        end = min(start + self.manager.page_size - 1, total_items)

        if total_items == 0:
            start, end = 0, 0

        self.page_label.setText(
            f"Page {self.current_page + 1} / {total_pages}   ({start}-{end} / {total_items})"
        )
        self.prev_button.setEnabled(self.current_page > 0)
        self.next_button.setEnabled(self.current_page < total_pages - 1)

    def on_prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.refresh_tree()

    def on_next_page(self):
        if self.current_page < self.manager.page_count() - 1:
            self.current_page += 1
            self.refresh_tree()

    def on_search_changed(self, text):
        self.manager.filter(text)
        self.current_page = 0
        self.refresh_tree()

    def on_header_clicked(self, column):
        if column == 1:
            self.name_sort_desc = not self.name_sort_desc
            mode = SortMode.NAME_DESC if self.name_sort_desc else SortMode.NAME_ASC
        elif column == 2:
            self.mtime_sort_new = not self.mtime_sort_new
            mode = SortMode.MTIME_NEW if self.mtime_sort_new else SortMode.MTIME_OLD
        else:
            return

        self.manager.sort(mode)
        self.manager.filter(self.search_widget.text())
        self.current_page = 0
        self.refresh_tree()

    def on_item_clicked(self, item, column):
        directory_path = item.data(0, Qt.UserRole)
        thumbnail_path = self.manager.find_thumbnail(directory_path)
        self.scene.clear()

        if thumbnail_path and os.path.exists(thumbnail_path):
            pixmap = QPixmap(thumbnail_path)
            self.scene.addPixmap(
                pixmap.scaled(self.view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.view.setScene(self.scene)


def main():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    config = load_config(config_path)

    app = QApplication(sys.argv)
    apply_stylesheet(app, theme=config.get("theme", "dark_teal.xml"))

    manager = DirectoryManager(
        root=config.get("search_dir", r"Y:\asmr"),
        page_size=int(config.get("page_size", 5)),
        img_exts=config.get("img_exts"),
    )

    window = ThumbnailViewerApp(
        manager=manager,
        thumb_size=int(config.get("thumb_size", 200)),
        default_res=tuple(config.get("default_res", [1280, 720])),
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()