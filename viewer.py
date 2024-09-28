import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QTreeWidget, QTreeWidgetItem, QLabel,
    QDesktopWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
    QFileDialog, QMainWindow, QGraphicsScene, QGraphicsView, QLineEdit
)
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5.QtCore import Qt
import qdarktheme
from pathlib import Path
import subprocess
import json
from PIL import Image
from datetime import datetime

# Thumbnail file directory
thumb_dir = Path(sys.executable).parent / "thumbnails" if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent / "thumbnails"
thumb_dir.mkdir(exist_ok=True)

# Helper function to load configuration
def load_config():
    config_file_path = Path(sys.executable).parent / "config.txt" if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent / "config.txt"
    config_data = {}
    with open(config_file_path, 'r') as config_file:
        for line in config_file:
            if line.startswith('#'):
                continue
            key, value = line.strip().split('=')
            config_data[key] = value
    return config_data

# Helper function to save JSON data to a file
def save_json(file_path, data):
    with open(str(file_path), "w") as json_file:
        json.dump(data, json_file, indent=4)

# Configuration settings
config_data = load_config()
search_dir = Path(config_data.get('search_dir', r"I:\asmr"))
img_exts = config_data.get('img_exts', "png,jpg,webp,jpeg").split(',')
theme = config_data.get('theme', "dark")
default_res = tuple(map(int, config_data.get('default_res', "1280x720").split('x')))
thumb_size = int(config_data.get('thumb_size', 200))

# Class to manage the list of thumbnails
class ThumbnailList:
    def __init__(self):
        self.search_dir = search_dir
        self.thumb_dir = thumb_dir
        self.thumb_size = thumb_size
        self.img_exts = img_exts
        self.thumb_file = thumb_dir / "thumbnails.json"
        self.thumb_dir_list = {}

        self.thumb_dir.mkdir(exist_ok=True)

        self.read_thumb_list()

    def read_thumb_list(self):
        # Load existing thumbnails if the file exists, otherwise create new ones
        if self.thumb_file.exists():
            self.load_existing_thumbnails()
        else:
            self.thumb_dir_list = self.scan_directories(self.search_dir)
            self.save_thumbnails()

        # Update to reflect the latest directory state
        self.update_thumbnails()

    def load_existing_thumbnails(self):
        # Load the existing thumbnail information from the JSON file.
        with open(self.thumb_file, 'r') as f:
            self.thumb_dir_list = {
                Path(k).resolve(): {
                    'thumbnail_image': Path(v['thumbnail_image']).resolve() if v['thumbnail_image'] != "None" else None,
                    'original_image': Path(v['original_image']).resolve() if v['original_image'] != "None" else None
                } for k, v in json.load(f).items()
            }

    def scan_directories(self, base_dir: Path):
        # Scan the specified directory for image files, and create thumbnails if necessary.
        thumb_dir_list = {}
        sub_dirs = [f for f in base_dir.glob("*") if f.is_dir()]

        for sub_dir in sub_dirs:
            img_names = [img for ext in self.img_exts for img in sub_dir.rglob(f"*.{ext}")]
            if img_names:
                original_image = img_names[0]
                thumb_save_path = self.thumb_dir / f"{sub_dir.name}.jpg"
                if not thumb_save_path.exists():
                    self.save_resized_thumbnail(original_image, thumb_save_path)
                thumb_dir_list[sub_dir.resolve()] = {
                    'thumbnail_image': thumb_save_path.resolve(),
                    'original_image': original_image.resolve()
                }
            else:
                thumb_dir_list[sub_dir.resolve()] = {
                    'thumbnail_image': None,
                    'original_image': None
                }

        return thumb_dir_list

    def update_thumbnails(self):
        # Update the thumbnail list based on the current directory structure.
        current_thumb_dir_list = self.scan_directories(self.search_dir)

        # Add new directories
        for directory, paths in current_thumb_dir_list.items():
            if directory not in self.thumb_dir_list:
                print(f"New directory added: {directory.name}")
                self.thumb_dir_list[directory] = paths

        # Remove deleted directories
        for directory in list(self.thumb_dir_list.keys()):
            if directory not in current_thumb_dir_list:
                print(f"Directory removed: {directory.name}")
                del self.thumb_dir_list[directory]

        # Save the updated information
        self.save_thumbnails()

    def save_resized_thumbnail(self, image_path: Path, save_path: Path):
        # Resize the image and save it as a JPEG file.
        with Image.open(image_path) as img:
            img.thumbnail((self.thumb_size, self.thumb_size))
            if img.mode != 'RGB':
                img = img.convert('RGB')  # Convert RGBA to RGB since JPEG does not support RGBA
            img.save(save_path, format='JPEG')

    def save_thumbnails(self):
        # Save the current thumbnail information to the JSON file.
        save_info = {
            str(k): {
                'thumbnail_image': str(v['thumbnail_image']),
                'original_image': str(v['original_image'])
            } for k, v in self.thumb_dir_list.items()
        }
        with open(self.thumb_file, 'w') as f:
            json.dump(save_info, f, indent=4)

    def change_thumb(self, change_directory: Path, new_image_path: Path):
        # Change the thumbnail and update both thumbnail and original image paths.
        thumb_save_path = self.thumb_dir / f"{change_directory.name}.jpg"
        self.save_resized_thumbnail(new_image_path, thumb_save_path)
        self.thumb_dir_list[change_directory.resolve()] = {
            'thumbnail_image': thumb_save_path.resolve(),
            'original_image': new_image_path.resolve()
        }
        self.save_thumbnails()

# Global thumbnail list instance
thumbnail_list = ThumbnailList()

# Clickable Thumbnail Image class for handling double-click events
class ClickableLabel(QLabel):
    def __init__(self, directory=None, parent=None):
        super().__init__(parent)
        self.directory = directory

class ClickableDirName(ClickableLabel):
    def mouseDoubleClickEvent(self, event):
        subprocess.Popen(["explorer", str(self.directory)])

class ClickableThumbnail(ClickableLabel):
    def mouseDoubleClickEvent(self, event):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("Images (*.png *.jpg *.webp *.jpeg);;All Files (*)")
        if self.directory:
            file_dialog.setDirectory(str(self.directory))
        if file_dialog.exec_():
            self.change_thumbnail(file_dialog.selectedFiles()[0])

    def change_thumbnail(self, new_image_path):
        # Change the thumbnail image and update both thumbnail and original paths
        thumbnail_list.change_thumb(Path(self.directory), Path(new_image_path))
        new_thumb = thumbnail_list.thumb_dir_list[Path(self.directory).resolve()]["thumbnail_image"]
        self.get_thumbnail(new_thumb)

    def get_thumbnail(self, thumbnail_path):
        pixmap = QPixmap(str(thumbnail_path)) if thumbnail_path else QPixmap(thumb_size, thumb_size)
        self.setPixmap(pixmap)
        return pixmap

# Main application window
class ThumbnailViewerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Thumbnail Viewer')
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        layout = QVBoxLayout(self.central_widget)
        self.search_widget = QLineEdit(self.central_widget)
        self.search_widget.setPlaceholderText("Search...")
        self.search_widget.textChanged.connect(self.search_items)
        layout.addWidget(self.search_widget)

        groupBox = QGroupBox("Thumbs and Names")
        layout.addWidget(groupBox)

        thumb_name_layout = QHBoxLayout()
        groupBox.setLayout(thumb_name_layout)

        self.tree = QTreeWidget(self.central_widget)
        self.tree.setHeaderLabels(["Thumbnail", "Name", "modified"])
        self.tree.setColumnWidth(0, thumb_size + 50)
        self.tree.setColumnWidth(1, thumb_size + 50)
        self.tree.setSortingEnabled(True)
        self.tree.sortItems(2, Qt.DescendingOrder)

        self.populate_tree()

        self.image_label = QLabel(self.central_widget)
        self.image_label.setAlignment(Qt.AlignTop)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        thumb_name_layout.addWidget(self.tree)
        thumb_name_layout.addWidget(self.image_label)
        thumb_name_layout.addWidget(self.view)

        self.tree.itemClicked.connect(self.show_large_image)

        self.resize(default_res[0], default_res[1])
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def populate_tree(self):
        for directory, thumbnail_data in thumbnail_list.thumb_dir_list.items():
            item = QTreeWidgetItem(self.tree)
            thumbnail_item = ClickableThumbnail(directory)
            thumbnail_item.get_thumbnail(thumbnail_data["thumbnail_image"])
            self.tree.setItemWidget(item, 0, thumbnail_item)
            name_item = ClickableDirName(directory)
            item.setText(1, directory.name)
            self.tree.setItemWidget(item, 1, name_item)
            birth_time_str = datetime.fromtimestamp(directory.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            item.setText(2, birth_time_str)

    def show_large_image(self, item, column):
        thumbnail_item = self.tree.itemWidget(item, 0)
        original_image_path = thumbnail_list.thumb_dir_list[thumbnail_item.directory.resolve()]['original_image']
        self.scene.clear()

        if original_image_path and original_image_path.exists():
            pixmap = QPixmap(str(original_image_path))
            self.scene.addPixmap(pixmap.scaled(self.view.size(), Qt.KeepAspectRatio))
            self.view.setScene(self.scene)

    def search_items(self):
        search_text = self.search_widget.text().lower()
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            name_item = self.tree.itemWidget(item, 1)
            item.setHidden(search_text not in name_item.directory.name.lower())
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            if not item.isHidden():
                self.tree.scrollToItem(item)
                break

# Entry point for the application
if __name__ == '__main__':
    app = QApplication(sys.argv)
    qdarktheme.setup_theme(theme)
    ex = ThumbnailViewerApp()
    ex.show()
    sys.exit(app.exec_())