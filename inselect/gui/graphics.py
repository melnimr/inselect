__all__ = ['GraphicsView', 'GraphicsScene', 'BoxResizable']


from PySide import QtCore, QtGui

from inselect.lib.mouse_handler import MouseHandler, MouseState
from inselect.lib.key_handler import KeyHandler
from inselect.gui.sidebar import SegmentListItem
from inselect.gui.annotator import AnnotateDialog


class GraphicsView(KeyHandler, MouseHandler, QtGui.QGraphicsView):
    def __init__(self, parent=None):
        QtGui.QGraphicsView.__init__(self, parent)
        MouseHandler.__init__(self, parent_class=QtGui.QGraphicsView)
        KeyHandler.__init__(self, parent_class=QtGui.QGraphicsView)
        self.scrollBarValuesOnMousePress = QtCore.QPoint()
        self.setDragMode(QtGui.QGraphicsView.RubberBandDrag)
        self.items = []
        self.parent = parent
        # Setup key handlers
        self.add_key_handler(QtCore.Qt.Key_Delete, self.delete_boxes)
        self.add_key_handler(QtCore.Qt.Key_Return, self.annotate_boxes)
        self.add_key_handler(QtCore.Qt.Key_Z, self.zoom_to_selection)
        self.add_key_handler(QtCore.Qt.Key_Up, self.move_boxes, [0, -1])
        self.add_key_handler(QtCore.Qt.Key_Up, self.move_boxes, [0, -1])
        self.add_key_handler(QtCore.Qt.Key_Right, self.move_boxes, [1, 0])
        self.add_key_handler(QtCore.Qt.Key_Down, self.move_boxes, [0, 1])
        self.add_key_handler(QtCore.Qt.Key_Left, self.move_boxes, [-1, 0])
        self.add_key_handler(
            key=(QtCore.Qt.ControlModifier, QtCore.Qt.Key_Up),
            callback=self.move_boxes,
            args=[0, -1, 0, 0]
        )
        self.add_key_handler(
            key=(QtCore.Qt.ControlModifier, QtCore.Qt.Key_Right),
            callback=self.move_boxes,
            args=[1, 0, 0, 0]
        )
        self.add_key_handler(
            key=(QtCore.Qt.ControlModifier, QtCore.Qt.Key_Down),
            callback=self.move_boxes,
            args=[0, 1, 0, 0]
        )
        self.add_key_handler(
            key=(QtCore.Qt.ControlModifier, QtCore.Qt.Key_Left),
            callback=self.move_boxes,
            args=[-1, 0, 0, 0]
        )
        self.add_key_handler(
            key=(QtCore.Qt.ShiftModifier, QtCore.Qt.Key_Up),
            callback=self.move_boxes,
            args=[0, 0, 0, -1]
        )
        self.add_key_handler(
            key=(QtCore.Qt.ShiftModifier, QtCore.Qt.Key_Right),
            callback=self.move_boxes,
            args=[0, 0, 1, 0]
        )
        self.add_key_handler(
            key=(QtCore.Qt.ShiftModifier, QtCore.Qt.Key_Down),
            callback=self.move_boxes,
            args=[0, 0, 0, 1]
        )
        self.add_key_handler(
            key=(QtCore.Qt.ShiftModifier, QtCore.Qt.Key_Left),
            callback=self.move_boxes,
            args=[0, 0, -1, 0]
        )
        self.add_key_handler(QtCore.Qt.Key_N, self.select_next)
        self.add_key_handler(QtCore.Qt.Key_P, self.select_previous)
        # Add mouse event handlers
        self.add_mouse_handler(
            event={
                'event': 'move',
                'button': 'middle'
            },
            callback=self.scroll_view,
            args=[MouseState('delta_x'), MouseState('delta_y')]
        )
        self.add_mouse_handler(
            event={
                'event': 'press',
                'button': 'right'
            },
            callback=self._start_new_box,
            args=[MouseState('x'), MouseState('y')]
        )
        self.add_mouse_handler(
            event={
                'event': 'move',
                'button': 'right'
            },
            callback=self._update_new_box,
            args=[MouseState('x'), MouseState('y')]
        )
        self.add_mouse_handler(
            event={
                'event': 'release',
                'button': 'right'
            },
            callback=self._finish_new_box,
            args=[MouseState('x'), MouseState('y')]
        )
        self.add_mouse_handler(
            event={
                'event': 'wheel',
                'button': None,
                'modifier': QtCore.Qt.ControlModifier
            },
            callback=self.zoom,
            args=[MouseState('wheel_delta')]
        )

    def add_item(self, item):
        # Insert into the list so as to ease prev/next navigation
        band_size = int(self.scene().height()/20)
        item_box = item.boundingRect()
        insert_at = len(self.items)
        for i in range(len(self.items)):
            box = self.items[i].boundingRect()
            item_box_band = int(item_box.y()/band_size)
            box_band = int(box.y()/band_size)
            if item_box_band > box_band:
                continue
            if item_box_band < box_band or item_box.x() < box.x():
                insert_at = i
                break
        self.items.insert(insert_at, item)
        # Add the item to the sidebar
        window = self.parent
        sidebar = self.parent.sidebar
        icon = window.get_icon(item)
        list_item = SegmentListItem(icon, "", box=item)
        item.list_item = list_item
        sidebar.insertItem(insert_at, list_item)

    def remove_item(self, item):
        self.items.remove(item)
        self.scene().removeItem(item)

    def set_scale(self, scale):
        self.scale_factor = scale
        self.scale(scale, scale)

    def zoom_to_selection(self):
        """Zoom the view to the current selection"""
        box = self._get_selection_box()
        if box is not None:
            self.fitInView(box[0][0], box[0][1], box[1][0] - box[0][0],
                           box[1][1] - box[0][1], QtCore.Qt.KeepAspectRatio)

    def zoom(self, delta, factor=0.2):
        """Zoom the scene in or out.

        Notes
        -----
        Only the sign of the delta is important. This sets the scale to 1 +
        sign(delta) * factor

        Parameters
        ----------
        delta : int
            Positive to zoom in, negative to zoom out
        factor : float
            The factor - should be between 0 and 1 (Exclusive)
        """
        self.set_scale(1 + cmp(delta, 0) * factor)

    def move_boxes(self, tl_dx, tl_dy, br_dx=None, br_dy=None):
        """Move the selected boxes

        If only two values are specified, the top left and bottom right corners
        are moved equally (so the entire box is moved). If four values are
        specified, then the top left and bottom right corners are moved
        independently.

        Parameters
        ----------
        tl_dx : int
            X increment for top left corner/box
        tl_dy : int
            Y increment for top left corner/box
        br_dx : int
            X increment for bottom right corner or None
        br_dy : int
            Y increment for bottom right corner or None
        """
        selected_boxes = self.scene().selectedItems()
        for box in selected_boxes:
            box.move_box(tl_dx, tl_dy, br_dx, br_dy)
            box.setZValue(1E9)

    def annotate_boxes(self):
        """Annotates selected box"""
        boxes = self.scene().selectedItems()
        dialog = AnnotateDialog(boxes, parent=self.parent)
        dialog.exec_()

    def delete_boxes(self):
        """Delete all selected boxes"""
        sidebar = self.parent.sidebar
        selected_boxes = self.scene().selectedItems()
        for box in selected_boxes:
            sidebar.takeItem(sidebar.row(box.list_item))
            self.remove_item(box)

    def deselect_all(self):
        """Deselect all items in the scene"""
        for item in self.scene().selectedItems():
            item.setSelected(False)
            b = item.boundingRect()
            item.setZValue(max(1000, 1E9 - b.width() * b.height()))

    def select_next(self):
        """Select the next object in the scene"""
        if len(self.items) == 0:
            return
        selected = self.scene().selectedItems()
        if len(selected) > 0:
            to_select = (self.items.index(selected[0]) + 1) % len(self.items)
        else:
            to_select = 0
        self.deselect_all()
        self.items[to_select].setSelected(True)
        self.items[to_select].setZValue(1E9)
        self.ensure_selection_visible()

    def select_previous(self):
        """Select the previous object in the scene"""
        if len(self.items) == 0:
            return
        selected = self.scene().selectedItems()
        if len(selected) > 0:
            to_select = (self.items.index(selected[0]) - 1) % len(self.items)
        else:
            to_select = 0
        self.deselect_all()
        self.items[to_select].setSelected(True)
        self.items[to_select].setZValue(1E9)
        self.ensure_selection_visible()

    def ensure_selection_visible(self):
        """Ensure the selected boxes are visible

        Notes
        -----
        Doing on this on a mouse-triggered selection change event might cause
        the box to move.
        """
        box = self._get_selection_box()
        if box is not None:
            self.ensureVisible(box[0][0], box[0][1], box[1][0] - box[0][0],
                               box[1][1] - box[0][1])

    def _get_selection_box(self):
        """Return the bounding box of selected items

        Returns
        --------
        tuple : (top_left, bottom_right) where each tuple is formed of (x,y) or
            None if there is no selection
        """
        tl = None
        br = None
        for item in self.scene().selectedItems():
            box = item.boundingRect()
            if tl is None:
                tl = (box.left(), box.top())
                br = (box.right(), box.bottom())
            else:
                tl = (min(tl[0], box.left()), min(tl[1], box.top()))
                br = (max(br[0], box.right()), max(br[1], box.bottom()))
        if tl is None:
            return None
        return tl, br

    def _start_new_box(self, x, y):
        """Start drawing a new box

        Parameters
        ----------
        x : int
            Screen X coordinate of first corner
        y : int
            Screen Y coordinate of first corner
        """
        s = self.mapToScene(x, y).toPoint()
        r = self.scene().addRect(s.x(), s.y(), 0, 0, QtCore.Qt.DotLine)
        r.setZValue(1E9)
        self._new_box = (s.x(), s.y(), r)

    def _update_new_box(self, x, y):
        """Update the size of the newly created box

        Parameters
        ----------
        x : int
            Screen X coordinate of other corner
        y : int
            Screen Y coordinate of other corner
        """
        u = self.mapToScene(x, y).toPoint()
        x1, y1 = min(self._new_box[0], u.x()), min(self._new_box[1], u.y())
        x2, y2 = max(self._new_box[0], u.x()), max(self._new_box[1], u.y())
        w = x2 - x1
        h = y2 - y1
        self._new_box[2].setRect(x1, y1, w, h)
        self.scene().update()

    def _finish_new_box(self, x, y):
        """Finish drawing a box and add it to the list of objects

        Parameters
        ----------
        x : int
            Screen X coordinate of other corner
        y : int
            Screen Y coordinate of other corner
        """
        u = self.mapToScene(x, y).toPoint()
        x1, y1 = min(self._new_box[0], u.x()), min(self._new_box[1], u.y())
        x2, y2 = max(self._new_box[0], u.x()), max(self._new_box[1], u.y())
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(x2, self.scene().width())
        y2 = min(y2, self.scene().height())

        w = x2 - x1
        h = y2 - y1

        if w > 5 and h > 5:
            box = BoxResizable(QtCore.QRectF(x1, y1, w, h),
                               scene=self.scene())

            b = box.boundingRect()
            box.setZValue(max(1000, 1E9 - b.width() * b.height()))
            box.updateResizeHandles()

            self.add_item(box)

        # Remove the creation box
        self.scene().removeItem(self._new_box[2])
        self._new_box = None

    def scroll_view(self, delta_x, delta_y):
        """ Scroll the view

        Parameters
        ----------
        delta_x : int
        delta_y : int
        """
        h = self.horizontalScrollBar()
        v = self.verticalScrollBar()
        h.setValue(h.value() + delta_x)
        v.setValue(v.value() + delta_y)


class GraphicsScene(QtGui.QGraphicsScene):
    def __init__(self, parent=None):
        QtGui.QGraphicsScene.__init__(self, parent)
        self.parent = parent

    def setGraphicsView(self, view):
        self.view = view


class BoxResizable(MouseHandler, QtGui.QGraphicsRectItem):
    def __init__(self, rect, parent=None, color=QtCore.Qt.blue,
                 transparent=False, scene=None):
        QtGui.QGraphicsRectItem.__init__(self, rect, parent, scene)
        MouseHandler.__init__(self, parent_class=QtGui.QGraphicsRectItem)
        self._rect = rect
        self._scene = scene
        self.parent = scene.parent
        self.list_item = None
        self.orig_rect = QtCore.QRectF(rect)
        self.handle_size = 4.0
        self.mouse_press_area = None
        self.color = color
        self.transparent = transparent
        self.seeds = []
        self.setFlags(QtGui.QGraphicsItem.ItemIsFocusable)
        self.setFlag(QtGui.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtGui.QGraphicsItem.ItemIsSelectable)
        self.setFlag(QtGui.QGraphicsItem.ItemSendsGeometryChanges)
        # Set mouse handlers
        self.setAcceptsHoverEvents(True)
        self.add_mouse_handler('double-click', self.open_annotation_dialog)
        self.add_mouse_handler(
            event={
                'event': 'press',
                'button': 'left',
                'modifier': QtCore.Qt.ShiftModifier
            },
            callback=self.add_seed,
            args=[MouseState('x'), MouseState('y')]
        )
        # Box resizing events
        self.add_mouse_handler(
            event={
                'event': 'press',
                'button': 'left',
                'modifier': QtCore.Qt.NoModifier
            },
            callback=self._start_move_resize,
            args=[MouseState('x'), MouseState('y')],
            delegate=True
        )
        self.add_mouse_handler(
            event={
                'event': 'move',
                'button': 'left',
                'modifier': QtCore.Qt.NoModifier
            },
            callback=self._move_resize,
            args=[MouseState('x'), MouseState('y')],
            delegate=True
        )
        self.add_mouse_handler(
            event={
                'event': 'release',
                'button': 'left',
                'modifier': QtCore.Qt.NoModifier
            },
            callback=self._end_move_resize,
            delegate=True
        )
        # Ensure that resize handles are updated when the mouse is active over
        # the element
        self.add_mouse_handler(
            event='enter',
            callback=self._update_graphics,
            args=[MouseState('x'), MouseState('y')],
            delegate=True
        )
        self.add_mouse_handler(
            event='leave',
            callback=self._update_graphics,
            args=[MouseState('x'), MouseState('y')],
            delegate=True
        )
        self.add_mouse_handler(
            event={
                'event': 'move',
                'over': True
            },
            callback=self._update_graphics,
            args=[MouseState('x'), MouseState('y')],
            delegate=True
        )
        self.updateResizeHandles()

    def shape(self):
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def open_annotation_dialog(self):
        dialog = AnnotateDialog(self, parent=self.parent)
        dialog.exec_()

    def _update_graphics(self, x, y):
        if any([self.top_left_handle.contains(x, y),
               self.bottom_right_handle.contains(x, y)]):

            self.setCursor(QtCore.Qt.SizeFDiagCursor)

        elif (self.top_right_handle.contains(x, y) or
              self.bottom_left_handle.contains(x, y)):

            self.setCursor(QtCore.Qt.SizeBDiagCursor)

        else:
            self.setCursor(QtCore.Qt.SizeAllCursor)

        b = self.boundingRect()
        if self.isSelected() and self.get_mouse_state('over'):
            self.setZValue(1E9)
        else:
            self.setZValue(max(1000, 1E9 - b.width() * b.height()))
        self.prepareGeometryChange()
        self.updateResizeHandles()
        return True

    def add_seed(self, x, y):
        """Add a new see for segmentation

        Paramaters
        ----------
        x : int
            X Screen coordinate of seed
        y : int
            Y Screen coordinate of seed
        """
        p = self.mapToScene(x, y).toPoint()
        rect = self._innerRect
        self.seeds.append((p.x() - rect.x() - self.pos().x(),
                           p.y() - rect.y() - self.pos().y()))

    def _start_move_resize(self, x, y):
        """Start moving/resizing the box

        Parameters
        ----------
        x : int
            X Screen coordinate
        y : int
            Y Screen coordinate
        """
        self.rect_press = QtCore.QRectF(self._rect)
        if self.top_left_handle.contains(x, y):
            self.mouse_press_area = 'topleft'
        elif self.top_right_handle.contains(x, y):
            self.mouse_press_area = 'topright'
        elif self.bottom_left_handle.contains(x, y):
            self.mouse_press_area = 'bottomleft'
        elif self.bottom_right_handle.contains(x, y):
            self.mouse_press_area = 'bottomright'
        else:
            # Entire rectangle
            self.mouse_press_area = None
        # Propagate to ensure the box gets selected
        return True

    def _end_move_resize(self):
        """End moving/resizing the box"""
        self._rect = self._rect.normalized()
        self.updateResizeHandles()
        # Propagate to ensure the box gets selected/etc.
        return True

    def _move_resize(self, x, y):
        """Move/resize the box

        Parameters
        ----------
        x : int
            X Screen coordinate
        y : int
            Y Screen coordinate
        """
        self.prepareGeometryChange()
        delta = QtCore.QPoint(
            self.get_mouse_state('pressed_x') - x,
            self.get_mouse_state('pressed_y') - y
        )
        if self.mouse_press_area:
            if self.mouse_press_area == 'topleft':
                self._rect.setTopLeft(self.rect_press.topLeft() - delta)
            elif self.mouse_press_area == 'topright':
                self._rect.setTopRight(self.rect_press.topRight() - delta)
            elif self.mouse_press_area == 'bottomleft':
                self._rect.setBottomLeft(self.rect_press.bottomLeft() - delta)
            elif self.mouse_press_area == 'bottomright':
                self._rect.setBottomRight(self.rect_press.bottomRight() - delta)
            return False
        # Propagate to ensure the box gets moved
        return True

    def boundingRect(self):
        """
        Return bounding rectangle
        """
        return self._boundingRect

    def move_box(self, tl_dx, tl_dy, br_dx=None, br_dy=None):
        """Move the box

        If only two values are specified, the top left and bottom right corners
        are moved equally (so the entire box is moved). If four values are
        specified, then the top left and bottom right corners are moved
        independently.

        Parameters
        ----------
        tl_dx : int
            X increment for top left corner/box
        tl_dy : int
            Y increment for top left corner/box
        br_dx : int
            X increment for bottom right corner or None
        br_dy : int
            Y increment for bottom right corner or None
        """
        if br_dx is None or br_dy is None:
            self._rect.moveTo(self._rect.x() + tl_dx, self._rect.y() + tl_dy)
        else:
            tl = self._rect.topLeft()
            br = self._rect.bottomRight()
            self._rect.setCoords(tl.x() + tl_dx, tl.y() + tl_dy,
                                 br.x() + br_dx, br.y() + br_dy)
        self.updateResizeHandles()

    def updateResizeHandles(self):
        """
        Update bounding rectangle and resize handles
        """
        self.prepareGeometryChange()

        self.offset = self.handle_size * \
            (self._scene.view.mapToScene(1, 0) -
             self._scene.view.mapToScene(0, 1)).x()
        self._boundingRect = self._rect.adjusted(-self.offset, -self.offset,
                                                 self.offset, self.offset)

        self.offset1 = (self._scene.view.mapToScene(1, 0) -
                        self._scene.view.mapToScene(0, 1)).x()
        self._innerRect = self._rect.adjusted(self.offset1, self.offset1,
                                              -self.offset1, -self.offset1)

        b = self._boundingRect
        self.top_left_handle = QtCore.QRectF(b.topLeft().x(),
                                             b.topLeft().y(),
                                             2*self.offset,
                                             2*self.offset)

        self.top_right_handle = QtCore.QRectF(b.topRight().x() - 2*self.offset,
                                              b.topRight().y(),
                                              2*self.offset,
                                              2*self.offset)

        self.bottom_left_handle = QtCore.QRectF(
            b.bottomLeft().x(),
            b.bottomLeft().y() - 2*self.offset,
            2*self.offset,
            2*self.offset)

        self.bottom_right_handle = QtCore.QRectF(
            b.bottomRight().x() - 2*self.offset,
            b.bottomRight().y() - 2*self.offset,
            2*self.offset,
            2*self.offset)

        # update the list item icon
        if self.list_item:
            icon = self.parent.get_icon(self)
            self.list_item.setIcon(icon)

    def map_rect_to_scene(self, map_rect):
        """Change from box coordinate system to view coordinate system.
        Where (0, 0) is the box coordinates at top left corner of the box,
        the position of the box is added to give the view coordinates.
        """
        rect = map_rect
        target_rect = QtCore.QRectF(rect)
        t = rect.topLeft()
        b = rect.bottomRight()
        x1, y1 = t.x() + self.pos().x(), t.y() + self.pos().y()
        x2, y2 = b.x() + self.pos().x(), b.y() + self.pos().y()
        target_rect.setTopLeft(QtCore.QPointF(min(x1, x2), min(y1, y2)))
        target_rect.setBottomRight(QtCore.QPointF(max(x1, x2), max(y1, y2)))
        return target_rect

    def paint(self, painter, option, widget):
        """
        Paint Widget
        """
        # Paint rectangle
        if self.isSelected():
            color = QtCore.Qt.red
            thickness = 3
        else:
            color = self.color
            thickness = 0

        painter.setPen(QtGui.QPen(color, thickness, QtCore.Qt.SolidLine))
        painter.drawRect(self._rect)

        if not self.transparent:
            rect = self._innerRect
            if rect.width() > 0 and rect.height() != 0:
                # normalize negative widths and heights, during resizing
                x1, y1 = rect.x(), rect.y()
                x2, y2 = rect.x() + rect.width(), rect.y() + rect.height()
                rect = QtCore.QRectF(min(x1, x2), min(y1, y2),
                                     abs(rect.width()), abs(rect.height()))
                target_rect = self.map_rect_to_scene(rect)
                painter.drawPixmap(rect, self.scene().image.pixmap(),
                                   target_rect)

        radius = self._scene.width() / 150
        for seed in self.seeds:
            x, y = seed
            rect = self._innerRect
            painter.drawEllipse(QtCore.QPointF(x + rect.x(), y + rect.y()),
                                radius, radius)

        painter.setPen(QtGui.QPen(color, 0, QtCore.Qt.SolidLine))
        # If mouse is over, draw handles
        if self.get_mouse_state('over'):
            painter.drawRect(self.top_left_handle)
            painter.drawRect(self.top_right_handle)
            painter.drawRect(self.bottom_left_handle)
            painter.drawRect(self.bottom_right_handle)