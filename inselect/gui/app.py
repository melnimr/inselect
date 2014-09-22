import numpy as np
import os
import json
import cv2

from PySide import QtCore, QtGui
from PySide.QtGui import QMessageBox

from inselect.lib import utils
from inselect.lib.qt_util import read_qt_image, convert_numpy_to_qt
from inselect.lib.segment import segment_edges, segment_grabcut
from inselect.gui.sidebar import SegmentListWidget
from inselect.gui.graphics import GraphicsView, GraphicsScene, BoxResizable
import inselect.settings


class WorkerThread(QtCore.QThread):
    results = QtCore.Signal(list, np.ndarray)

    def __init__(self, image, resegment_window, selected=None, parent=None):
        super(WorkerThread, self).__init__(parent)
        self.image = image
        self.resegment_window = resegment_window
        self.selected = selected

    def run(self):
        if self.resegment_window:
            seeds = self.selected.seeds
            rects, display = segment_grabcut(self.image, seeds=seeds,
                                             window=self.resegment_window)
        else:
            rects, display = segment_edges(self.image,
                                           window=None,
                                           variance_threshold=100,
                                           size_filter=0)
        self.results.emit(rects, display)


class InselectMainWindow(QtGui.QMainWindow):
    def __init__(self, app, filename=None):
        super(InselectMainWindow, self).__init__()
        self.app = app
        self.container = QtGui.QWidget(self)
        self.splitter = QtGui.QSplitter(self)
        self.view = GraphicsView(self)
        self.scene = GraphicsScene(self)
        self.sidebar = SegmentListWidget(self)
        self.view.setViewportUpdateMode(QtGui.QGraphicsView.FullViewportUpdate)
        self.view.setTransformationAnchor(QtGui.QGraphicsView.AnchorUnderMouse)
        self.view.setRenderHint(QtGui.QPainter.Antialiasing)
        self.view.setUpdatesEnabled(True)
        self.view.setMouseTracking(True)
        self.scene.setGraphicsView(self.view)
        self.view.setScene(self.scene)
        self.view.setCacheMode(QtGui.QGraphicsView.CacheBackground)

        self.setCentralWidget(self.splitter)
        self.splitter.addWidget(self.view)
        self.splitter.addWidget(self.sidebar)
        self.splitter.setSizes([1000, 100])

        self.view.move_box = BoxResizable(QtCore.QRectF(10, 10, 100, 100),
                                          color=QtCore.Qt.red,
                                          transparent=True,
                                          scene=self.scene)
        self.scene.addItem(self.view.move_box)
        self.view.move_box.setVisible(False)
        self.view.move_box.setZValue(1E9)

        if filename is None:
            image = QtGui.QImage()
        else:
            image = read_qt_image(filename)

        item = QtGui.QGraphicsPixmapItem(QtGui.QPixmap.fromImage(image))
        self.image = None
        self.padding = 0
        self.segment_display = None
        self.segment_image_visible = False
        self.scene.addItem(item)
        self.image_item = item
        self.scene.image = item
        self.create_actions()
        self.create_menus()

        self.setWindowTitle("Image Viewer")
        self.resize(500, 400)
        if filename:
            self.open(filename)

        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Q"), self, self.close)

    def open(self, filename=None):
        if not filename:
            folder = inselect.settings.get("working_directory")
            filename, _ = QtGui.QFileDialog.getOpenFileName(
                self, "Open File", folder)
        if filename:
            path = os.path.normpath(os.path.dirname(filename))
            inselect.settings.set_value('working_directory', path)
            self.filename = filename
            image = read_qt_image(filename)
            self.image = image
            if image.isNull():
                QtGui.QMessageBox.information(self, "Image Viewer",
                                              "Cannot load %s." % filename)
                return
            for item in list(self.view.items):
                self.view.remove_item(item)
            self.sidebar.clear()
            self.image_item.setPixmap(QtGui.QPixmap.fromImage(image))
            self.scene.setSceneRect(0, 0, self.image.width(), image.height())
            w, h = self.image.width(), self.image.height(),
            self.segment_display = np.zeros((h, w, 3), dtype=np.uint8)
            self.segment_image_visible = False
            self.toggle_segment_action.setEnabled(False)
            self.segment_action.setEnabled(True)
            self.export_action.setEnabled(True)
            self.zoom_in_action.setEnabled(True)
            self.zoom_out_action.setEnabled(True)
            self.save_action.setEnabled(True)
            self.import_action.setEnabled(True)

    def zoom_in(self):
        self.view.set_scale(1.2)

    def zoom_out(self):
        self.view.set_scale(0.8)

    def about(self):
        QtGui.QMessageBox.about(self, "Insect Selector",
                                "Stefan van der Walt\nPieter Holtzhausen")

    def get_icon(self, box):
        rect = box.map_rect_to_scene(box._rect).toRect()
        pixmap = self.image_item.pixmap().copy(rect)
        pixmap = pixmap.scaledToWidth(200, QtCore.Qt.SmoothTransformation)
        icon = QtGui.QIcon()
        icon.addPixmap(pixmap)
        return icon

    def add_box(self, rect, padding=0.05):
        """Adds a box to the viewer.

        Parameters
        ----------
        rect : (x, y, w, h) tuple
            The rectangle specifying the box.
        padding : int (default 0.05)
            The percentage padding added to box width and height.
        """
        x, y, w, h = rect[:4]
        pad_w = padding * w
        pad_h = padding * h
        x -= pad_w
        y -= pad_h
        w += 2 * pad_w
        h += 2 * pad_h
        sx = max(0, x)
        sy = max(0, y)
        ex = min(x + w, self.image.width())
        ey = min(y + h, self.image.height())
        s = QtCore.QPoint(sx, sy)
        e = QtCore.QPoint(ex, ey)
        qrect = QtCore.QRectF(s.x(), s.y(), e.x() - s.x(), e.y() - s.y())
        box = BoxResizable(qrect,
                           transparent=False,
                           scene=self.scene)
        self.view.add_item(box)
        b = box.boundingRect()
        box.setZValue(max(1000, 1E9 - b.width() * b.height()))
        box.updateResizeHandles()
        return box

    def worker_finished(self, rects, display):
        self.progressDialog.hide()
        window = self.worker.resegment_window
        if window:
            x, y, w, h = window
            self.segment_display[y:y+h, x:x+w] = display
            # removes the selected box before replacing it with resegmentations
            box = self.worker.selected
            self.sidebar.takeItem(self.sidebar.row(box.list_item))
            self.view.remove_item(box)
        else:
            self.segment_display = display.copy()
        self.toggle_segment_action.setEnabled(True)
        if self.segment_image_visible:
            self.display_image(self.segment_display)
        # add detected boxes
        for rect in rects:
            self.add_box(rect, padding=self.padding)

    def segment(self):
        self.progressDialog = QtGui.QProgressDialog(self)
        self.progressDialog.setWindowTitle("Segmenting...")
        self.progressDialog.setValue(0)
        self.progressDialog.setMaximum(0)
        self.progressDialog.setMinimum(0)
        self.progressDialog.show()
        image = cv2.imread(self.filename)
        resegment_window = None
        # if object selected, resegment the window
        selected = self.scene.selectedItems()
        if selected:
            selected = selected[0]
            window_rect = selected.map_rect_to_scene(selected._rect)
            p = window_rect.topLeft()
            resegment_window = [p.x(), p.y(), window_rect.width(),
                                window_rect.height()]
        self.worker = WorkerThread(image, resegment_window, selected)
        self.worker.results.connect(self.worker_finished)
        self.worker.start()

    def export(self):
        path = QtGui.QFileDialog.getExistingDirectory(
            self, "Export Destination", QtCore.QDir.currentPath())
        filename = self.filename
        # check for tiff file image
        extension = [".tif", ".tiff", ".TIF", ".TIFF"]
        target_name, _ = os.path.splitext(self.filename)
        for ext in extension:
            if os.path.exists(target_name + ext):
                msgBox = QMessageBox()
                msgBox.setText("Tiff file detected in input directory")
                msgBox.setInformativeText("Extract images from tiff file?")
                msgBox.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok)
                result = msgBox.exec_()
                if result == QMessageBox.Ok:
                    filename = target_name + ext
                break

        image = cv2.imread(filename)
        field_defaults = [(field, '-') for field in inselect.settings.get('annotation_fields')]
        export_template = inselect.settings.get('export_template')
        image_names = []
        for i, item in enumerate(self.view.items):
            b = item._rect
            x, y, w, h = b.x(), b.y(), b.width(), b.height()
            extract = image[y:y+h, x:x+w]
            # Generate file name from template
            placeholders = dict(field_defaults + item.list_item.fields.items())
            file_name = utils.unique_file_name(path, export_template.format(**placeholders), '.png')
            image_names.append(file_name)
            cv2.imwrite(file_name, extract)
        self._save_box_data(utils.unique_file_name(path, 'metadata', '.json'), image_names)

    def select_all(self):
        for item in self.view.items:
            item.setSelected(True)

    def display_image(self, image):
        """Displays an image in the user interface.

        Parameters
        ----------
        image : np.ndarray, QtCore.QImage
            Image to be displayed in viewer.
        """
        if isinstance(image, np.ndarray):
            image = convert_numpy_to_qt(image)
        self.image_item.setPixmap(QtGui.QPixmap.fromImage(image))

    def toggle_padding(self):
        """Action method to toggle box padding."""
        if self.padding == 0:
            self.padding = 0.05
        else:
            self.padding = 0

    def toggle_segment_image(self):
        """Action method to switch between display of segmentation image and
        actual image.
        """
        self.segment_image_visible = not self.segment_image_visible
        if self.segment_image_visible:
            image = self.segment_display
        else:
            image = self.image
        self.display_image(image)

    def create_actions(self):
        self.open_action = QtGui.QAction(
            self.style().standardIcon(QtGui.QStyle.SP_DirIcon),
            "&Open Image", self, shortcut="ctrl+O",
            triggered=self.open)

        self.exit_action = QtGui.QAction(
            "E&xit", self, shortcut="alt+f4", triggered=self.close)

        self.select_all_action = QtGui.QAction(
            "Select &All", self, shortcut="ctrl+A", triggered=self.select_all)

        self.zoom_in_action = QtGui.QAction(
            self.style().standardIcon(QtGui.QStyle.SP_ArrowUp),
            "Zoom &In", self, enabled=False, shortcut="Ctrl++",
            triggered=self.zoom_in)

        self.zoom_out_action = QtGui.QAction(
            self.style().standardIcon(QtGui.QStyle.SP_ArrowDown),
            "Zoom &Out", self, enabled=False, shortcut="Ctrl+-",
            triggered=self.zoom_out)

        self.toggle_segment_action = QtGui.QAction(
            self.style().standardIcon(QtGui.QStyle.SP_ComputerIcon),
            "&Display segmentation", self, shortcut="f3", enabled=False,
            statusTip="Display segmentation image", checkable=True,
            triggered=self.toggle_segment_image)

        self.toggle_padding_action = QtGui.QAction(
            "&Toggle padding", self, shortcut="", enabled=True,
            statusTip="Toggle padding", checkable=True,
            triggered=self.toggle_padding)

        self.about_action = QtGui.QAction("&About", self, triggered=self.about)

        self.segment_action = QtGui.QAction(
            self.style().standardIcon(QtGui.QStyle.SP_ComputerIcon),
            "&Segment", self, shortcut="f5", enabled=False,
            statusTip="Segment",
            triggered=self.segment)

        self.save_action = QtGui.QAction(
            self.style().standardIcon(QtGui.QStyle.SP_DesktopIcon),
            "&Save Boxes", self, shortcut="ctrl+s", enabled=False,
            statusTip="Save Boxes",
            triggered=self.save_boxes)

        self.import_action = QtGui.QAction(
            self.style().standardIcon(QtGui.QStyle.SP_DesktopIcon),
            "&Import Boxes", self, shortcut="ctrl+i", enabled=False,
            statusTip="Import Boxes",
            triggered=self.import_boxes)

        self.export_action = QtGui.QAction(
            self.style().standardIcon(QtGui.QStyle.SP_FileIcon),
            "&Export Images...", self, shortcut="", enabled=False,
            statusTip="Export",
            triggered=self.export)

        self.settings_action = QtGui.QAction(
            self.style().standardIcon(QtGui.QStyle.SP_MessageBoxInformation),
            "Settings", self, triggered=self.open_settings_dialog)

    def import_boxes(self):
        files, filtr = QtGui.QFileDialog.getOpenFileNames(
            self,
            "QFileDialog.getOpenFileNames()", "data",
            "All Files (*);;Text Files (*.json)", "",
            QtGui.QFileDialog.Options())

        if files:
            width = self.image_item.pixmap().width()
            height = self.image_item.pixmap().height()
            for file_name in files:
                data = json.load(open(file_name))
                for item in data["items"]:
                    rect = [float(x) for x in item["rect"]]
                    rect[0] *= width
                    rect[1] *= height
                    rect[2] *= width
                    rect[3] *= height
                    box = self.add_box(rect)
                    box.list_item.fields = item["fields"]

    def save_boxes(self):
        file_name, filtr = QtGui.QFileDialog.getSaveFileName(
            self,
            "QFileDialog.getSaveFileName()",
            self.filename + ".json",
            "All Files (*);;json Files (*.json)", "",
            QtGui.QFileDialog.Options())
        if file_name:
            self._save_box_data(file_name)

    def _save_box_data(self, file_name, image_names=None):
        data = {'image_name': self.filename}
        data["items"] = []
        for i, box in enumerate(self.view.items):
            rect = box.rect()
            bx, by = box.pos().x(), box.pos().y()
            rect = [rect.left() + bx, rect.top() + by,
                    rect.width(), rect.height()]
            width = self.image_item.pixmap().width()
            height = self.image_item.pixmap().height()
            rect[0] /= width
            rect[1] /= height
            rect[2] /= width
            rect[3] /= height
            export = {'rect': rect, 'fields': box.list_item.fields}
            if image_names:
                export['image_name'] = image_names[i]
            data['items'].append(export)
        json.dump(data, open(file_name, "w"), indent=4)

    def create_menus(self):
        self.toolbar = self.addToolBar("Edit")
        self.toolbar.addAction(self.open_action)
        self.toolbar.addAction(self.segment_action)
        self.toolbar.addAction(self.zoom_in_action)
        self.toolbar.addAction(self.zoom_out_action)
        self.toolbar.addAction(self.save_action)
        self.toolbar.addAction(self.import_action)
        self.toolbar.addAction(self.export_action)
        self.toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)

        self.fileMenu = QtGui.QMenu("&File", self)
        self.fileMenu.addAction(self.open_action)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.save_action)
        self.fileMenu.addAction(self.import_action)
        self.fileMenu.addAction(self.export_action)

        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.settings_action)

        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exit_action)

        self.editMenu = QtGui.QMenu("&Edit", self)
        self.editMenu.addAction(self.toggle_padding_action)

        self.viewMenu = QtGui.QMenu("&View", self)
        self.viewMenu.addAction(self.select_all_action)
        self.viewMenu.addAction(self.zoom_in_action)
        self.viewMenu.addAction(self.zoom_out_action)
        self.viewMenu.addAction(self.toggle_segment_action)

        self.helpMenu = QtGui.QMenu("&Help", self)
        self.helpMenu.addAction(self.about_action)

        self.menuBar().addMenu(self.fileMenu)
        self.menuBar().addMenu(self.editMenu)
        self.menuBar().addMenu(self.viewMenu)
        self.menuBar().addMenu(self.helpMenu)

    def open_settings_dialog(self):
        inselect.settings.open_settings_dialog()