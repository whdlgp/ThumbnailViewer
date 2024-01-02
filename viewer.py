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
from datetime import datetime, timezone

# Thumbnail file directory
thumb_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent

# Read config from file
config_file_path = Path(sys.executable).parent / "config.txt" if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent / "config.txt"
config_data = {}
with open(config_file_path, 'r') as config_file:
    for line in config_file:
        # Ignore lines starting with '#' (comments)
        if line.startswith('#'):
            continue

        key, value = line.strip().split('=')
        config_data[key] = value

# Config
search_dir = Path(config_data.get('search_dir', r"I:\asmr"))
img_exts = config_data.get('img_exts', "png,jpg,webp,jpeg").split(',')
# Possible values for 'theme': light, dark, auto
theme = config_data.get('theme', "dark")
default_res = tuple(map(int, config_data.get('default_res', "1280x720").split('x')))
thumb_size = int(config_data.get('thumb_size', 200))

# Class to manage the list of thumbnails
class ThumbnailList():
    def __init__(self):
        # Initialize the thumbnail list when the program starts
        self.read_thumb_list(search_dir)

    def read_thumb_list(self, dir: Path):
        # Read the new directory information
        sub_dirs = [f for f in dir.glob("*") if f.is_dir()]

        thumb_dir_list = {}
        for sub_dir in sub_dirs:
            img_names = []
            for ext in img_exts:
                img_names += list(sub_dir.rglob(f"**/*.{ext}"))
            if len(img_names) > 0:
                thumb_name = img_names[0]
                thumb_dir_list[sub_dir.resolve()] = thumb_name.resolve()
            else:
                thumb_name = None
                thumb_dir_list[sub_dir.resolve()] = None

        # Check if the thumbnail cache file exists
        thumb_file = thumb_dir / "thumbnails.json"
        if not thumb_file.exists():
            # Save thumbnail information to a text file
            save_info = {}
            for key in thumb_dir_list:
                save_info[str(key)] = str(thumb_dir_list[key])
            with open(str(thumb_file), "w") as json_file:
                json.dump(save_info, json_file, indent=4)
        else:
            # Read the existing thumbnail file
            old_thumb_dir_list= {}
            with open(str(thumb_file), 'r') as f:
                file_dict = json.load(f)
                for old_key in file_dict:
                    directory = Path(old_key).resolve()
                    if file_dict[old_key] == "None":
                        thumbnail_path = None
                    else:
                        thumbnail_path = Path(file_dict[old_key]).resolve()
                    old_thumb_dir_list[directory] = thumbnail_path

            # Compare the newly read thumbnail list with the existing one
            ## Add new files that are in 'new' but not in 'old'
            for key, value in thumb_dir_list.items():
                if key not in old_thumb_dir_list:
                    print(f"Add New file {key.name}")
                    old_thumb_dir_list[key] = value

            ## Remove old files that are in 'old' but not in 'new'
            for key in list(old_thumb_dir_list.keys()):
                if key not in thumb_dir_list:
                    print(f"Del old file {key.name}")
                    del old_thumb_dir_list[key]

            thumb_dir_list = old_thumb_dir_list
            # Save the updated thumbnail information to the text file
            save_info = {}
            for key in thumb_dir_list:
                save_info[str(key)] = str(thumb_dir_list[key])
            with open(str(thumb_file), "w") as json_file:
                json.dump(save_info, json_file, indent=4)

        self.thumb_dir_list = thumb_dir_list

    def change_thumb(self, change_directory, new_image_path):
        # Read the thumbnail file
        thumb_file = thumb_dir / "thumbnails.json"
        thumb_dir_list= {}
        with open(str(thumb_file), 'r') as f:
            file_dict = json.load(f)
            for old_key in file_dict:
                directory = Path(old_key).resolve()
                if file_dict[old_key] == "None":
                    thumbnail_path = None
                else:
                    thumbnail_path = Path(file_dict[old_key]).resolve()
                thumb_dir_list[directory] = thumbnail_path
        
        # Change the thumbnail location in the dictionary
        thumb_dir_list[change_directory.resolve()] = Path(new_image_path).resolve()

        # Save the updated thumbnail information to the text file
        save_info = {}
        for key in thumb_dir_list:
            save_info[str(key)] = str(thumb_dir_list[key])
        with open(str(thumb_file), "w") as json_file:
            json.dump(save_info, json_file, indent=4)

        self.thumb_dir_list = thumb_dir_list


# Initialize the local thumbnail list from the file
thumbnail_list = ThumbnailList()

# Clickable Thumbnail Image class for handling double-click events
class ClickableDirName(QLabel):
    def __init__(self, dir_fullpath=None, parent=None):
        super(ClickableDirName, self).__init__(parent)
        self.directory = dir_fullpath

    def mouseDoubleClickEvent(self, event):
        # Double-click event handling
        subprocess.Popen(["explorer", str(self.directory)])


# Clickable Directory Name class for handling double-click events
class ClickableThumbnail(QLabel):
    def __init__(self, directory=None, parent=None):
        super(ClickableThumbnail, self).__init__(parent)
        self.directory = directory

    def mouseDoubleClickEvent(self, event):
        # Double-click event handling
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("Images (*.png *.jpg *.webp *.jpeg);;All Files (*)")

        if self.directory is not None:
            file_dialog.setDirectory(str(self.directory))

        if file_dialog.exec_():
            selected_file = file_dialog.selectedFiles()[0]
            self.change_thumbnail(selected_file)

    def change_thumbnail(self, new_image_path):
        # Change the thumbnail with the selected image
        self.get_thumbnail(Path(new_image_path))

        # Save the updated thumbnail information to the local list
        thumbnail_list.change_thumb(self.directory, new_image_path)

    def get_thumbnail(self, thumbnail_path):
        # Get the thumbnail image
        if thumbnail_path:
            thumbnail_path_str = str(thumbnail_path)
            pixmap = QPixmap(thumbnail_path_str)
            pixmap = pixmap.scaled(thumb_size, thumb_size, Qt.KeepAspectRatio)
            self.setPixmap(pixmap)
            return pixmap
        else:
            # Create and return a "No image" pixmap
            no_image_pixmap = QPixmap(thumb_size, thumb_size)
            no_image_pixmap.fill(Qt.gray)
            self.setPixmap(no_image_pixmap)
            return no_image_pixmap


# Main application window
class ThumbnailViewerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        # Create or check the thumb directory
        thumb_dir.mkdir(exist_ok=True)

        self.init_ui()

    def init_ui(self):
        # Initialize the user interface

        # Set window title
        self.setWindowTitle('Thumbnail Viewer')

        # Set the central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Add a search widget
        self.search_widget = QLineEdit(self.central_widget)
        self.search_widget.setPlaceholderText("Search...")
        self.search_widget.textChanged.connect(self.search_items)

        # Create a tree widget for displaying thumbnails and names
        self.tree = QTreeWidget(self.central_widget)
        self.tree.setHeaderLabels(["Thumbnail", "Name", "modified"])
        self.tree.setColumnWidth(0, thumb_size + 50)
        self.tree.setColumnWidth(1, thumb_size + 50)

        # Set initial sorting
        self.tree.setSortingEnabled(True)
        self.tree.sortItems(2, Qt.DescendingOrder)  # Sort by the "modified" column in Descending order

        # Populate the tree with existing thumbnail information
        for directory in thumbnail_list.thumb_dir_list:
            thumbnail_path = thumbnail_list.thumb_dir_list[directory]

            item = QTreeWidgetItem(self.tree)

            # Add the thumbnail image to the tree widget
            thumbnail_item = ClickableThumbnail(directory)
            thumbnail_item.get_thumbnail(thumbnail_path)
            self.tree.setItemWidget(item, 0, thumbnail_item)

            # Add the directory name to the tree widget
            name_item = ClickableDirName(directory)
            item.setText(1, directory.name)
            name_item.setWordWrap(True)
            self.tree.setItemWidget(item, 1, name_item)

            # Add the modified date time to the tree widget
            birth_time = directory.stat().st_mtime
            birth_time_str = datetime.fromtimestamp(birth_time).strftime('%Y-%m-%d %H:%M')
            item.setText(2, birth_time_str)

        # Add labels for displaying images
        self.image_label = QLabel(self.central_widget)
        self.image_label.setAlignment(Qt.AlignTop)

        # Use QGraphicsScene and QGraphicsView to display large thumbnail images
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing, True)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.view.setRenderHint(QPainter.HighQualityAntialiasing, True)
        self.view.setScene(self.scene)

        # Use a vertical layout to arrange small thumbnail images and directory names on the left,
        # and large thumbnail images on the right
        groupBox = QGroupBox("Thumbs and Names")
        thumb_name_layout = QHBoxLayout()
        thumb_name_layout.addWidget(self.tree)
        thumb_name_layout.addWidget(self.image_label)
        thumb_name_layout.addWidget(self.view)
        groupBox.setLayout(thumb_name_layout)

        # Add the search bar to the layout
        layout = QVBoxLayout(self.central_widget)
        layout.addWidget(self.search_widget)
        layout.addWidget(groupBox)
        
        # Connect the itemClicked signal of the tree widget to the show_large_image method
        self.tree.itemClicked.connect(self.show_large_image)

        # Set the initial window size
        self.resize(default_res[0], default_res[1])
        # Set window to center
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def show_large_image(self, item, column):
        # Display the large thumbnail image when a directory item is clicked
        thumbnail_item = self.tree.itemWidget(item, 0)
        directory = thumbnail_item.directory
        thumbnail_path = thumbnail_list.thumb_dir_list[Path(directory).resolve()]
        
        # Display the thumbnail image in the QGraphicsScene
        self.scene.clear()  # Clear the previous image

        if thumbnail_path:
            pixmap = QPixmap(str(thumbnail_path))
            # Scale the image to fit the size of the right QLabel
            self.scene.addPixmap(pixmap.scaled(self.view.size(), Qt.KeepAspectRatio))
            self.view.setScene(self.scene)

    def search_items(self):
        # Search for items based on the entered text
        search_text = self.search_widget.text().lower()
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            name_item = self.tree.itemWidget(item, 1)

            # Check if the search text is in the directory name or file name
            if search_text in name_item.directory.name.lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

        # Scroll to the first matching item
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