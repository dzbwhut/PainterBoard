from PyQt5 import QtWidgets
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.Qt import QPixmap, QPainter, QPoint, QPaintEvent, QMouseEvent, QPen, \
    QColor, QSize
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
import functools
import math
import gc

from PyQt5.uic import loadUiType
painter, _ = loadUiType('Painter.ui')

# 画板弹窗界面
class PaintBoard(QWidget, painter):
    save_signal = pyqtSignal(object)

    def __init__(self, parent):
        super().__init__()
        self.setupUi(self)
        self.copiedItem = QByteArray()
        # self.parentWin = parent
        self.undoStack = QUndoStack()
        self.undoStack.createUndoAction(self, '撤消')
        self.undoStack.createRedoAction(self, '恢复')
        undoView = QUndoView(self.undoStack)
        undoView.setMaximumSize(300, 16777215)
        self.verticalLayout.addWidget(undoView)
        self.undoAction = self.undoStack.createUndoAction(self, "Undo")
        self.undoAction.setShortcut(QKeySequence.Undo)
        self.redoAction = self.undoStack.createRedoAction(self, "Redo")
        self.redoAction.setShortcut(QKeySequence.Redo)
        self.addAction(self.undoAction)
        self.addAction(self.redoAction)

        self.graphics = GraphicView()
        self.scene = self.graphics.scene
        self.graphics.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        # 千万记得用addWidget(self.graphics)，而不是addWidget(addWidget)，不然传参数会有问题
        self.gridLayout_paintbox.addWidget(self.graphics)

        self.scene.itemClicked.connect(self.wc)
        self.scene.itemScaled.connect(self.itemscaled)

        self.pix = None
        self.pixfixed = None
        self.pw = None
        self.ph = None
        self.item = None

        # 这里是将自定义类装进QtDesigner里面的GridLayout（"set_gridLayout"）
        self.colorbox = ColorCombox()
        self.set_gridLayout.addWidget(self.colorbox, 0, 1, 0, 1)

        self.colorbox.signal.connect(self.colorbox.createColorToolButtonIcon)
        self.colorbox.signal.connect(self.on_PenColorChange)
        self.colorbox.signal.connect(self.item_pen_color_changed)
        self.colorbox.thick_signal.connect(self.on_PenThicknessChange)
        self.colorbox.thick_signal.connect(self.item_pen_width_changed)
        self.colorbox.style_signal.connect(self.on_PenStyleChange)
        self.colorbox.style_signal.connect(self.item_pen_style_changed)

        self.scene.itemClicked.connect(self.itemcolorshow)

        self.fillcolorbox = FillColorCombox()
        self.set_gridLayout.addWidget(self.fillcolorbox, 0, 2, 0, 1)
        self.fillcolorbox.signal.connect(self.fillcolorbox.createColorToolButtonIcon)
        self.fillcolorbox.signal.connect(self.on_BrushColorChange)
        self.fillcolorbox.signal.connect(self.item_brush_color_changed)

        # 裁剪功能
        self.tailor = QPushButton("裁剪")
        self.tailor.setIcon(QIcon("ICon/crop.png"))
        self.tailor.setIconSize(QSize(35, 35))
        self.tailor.setCheckable(True)
        self.tailor.setAutoExclusive(True)
        self.tailor.setStyleSheet("background-color:white;font:bold")
        self.tailor.setMinimumSize(30, 40)
        self.tailor.setFlat(True)
        self.set_gridLayout.addWidget(self.tailor, 0, 3, 0, 1)
        self.tailor.toggled.connect(self.item_tailor)
        self.tailor.setEnabled(False)
        self.scene.itemClicked.connect(self.item_islike_PItem)

        # 信号与槽
        self.Openfile_btn.clicked.connect(self.on_btn_Open_Clicked)
        self.Quit_btn.clicked.connect(self.on_btn_Quit_Clicked)
        self.Clear_btn.clicked.connect(self.clean_all)
        self.Save_btn.clicked.connect(self.on_btn_Save_Clicked)
        self.circle_btn.clicked.connect(self.on_circle_btn_clicked1)
        self.Free_pen_btn.clicked.connect(self.on_Free_pen_btn_clicked1)
        self.line_btn.clicked.connect(self.line_btn_clicked1)
        self.rect_btn.clicked.connect(self.on_rect_btn_clicked1)
        self.text_btn.clicked.connect(self.addText)
        self.pic_move_btn.clicked.connect(self.on_pic_move_btn_clicked)
        self.drawback_btn.clicked.connect(self.drawback)
        self.set_upper_btn.clicked.connect(self.item_up)
        self.set_lower_btn.clicked.connect(self.item_down)
        self.test.clicked.connect(self.item_rect_change)
        self.reload_btn.clicked.connect(self.reload_size)
        self.del_items_btn.clicked.connect(self.delete)
        self.width_lineEdit.returnPressed.connect(self.wh_change)
        self.height_lineEdit.returnPressed.connect(self.wh_change)
        self.test_save_btn.clicked.connect(self.test_save)
        self.test_open_btn.clicked.connect(self.test_open)
        self.print_btn.clicked.connect(self.my_paint_print)
        self.cut_btn.clicked.connect(self.cutitem)
        self.copy_btn.clicked.connect(self.copyitem)
        self.center()
        self.history_btn.clicked.connect(self.MyUndostackClear)

        self.scene.itemMoved.connect(self.onItemMoved)
        self.scene.itemAdded.connect(self.onAddItem)
        self.scene.itemResized.connect(self.onResizeItem)
        self.scene.itemRotated.connect(self.onItemRotated)
        self.scene.itemDeled.connect(self.onDelItem)

        self.wrapped = []
        menu = QMenu(self)
        for text, arg in (
                ("左排列", Qt.AlignLeft),
                ("右排列", Qt.AlignRight),
                ("顶排列", Qt.AlignTop),
                ("底排列", Qt.AlignBottom)):
            wrapper = functools.partial(self.setAlignment, arg)
            self.wrapped.append(wrapper)
            menu.addAction(text, wrapper)
        self.alignment_btn.setMenu(menu)

    def MyUndostackClear(self):
        self.undoStack.clear()

    def onResizeItem(self, item, oldRect, delta):
        self.undoStack.push(itemResizeCommand(item, oldRect, delta))

    def onAddItem(self, scene, item):
        self.undoStack.push(itemAddCommand(scene, item))

    def onItemMoved(self, item, pos):
        self.undoStack.push(itemMoveCommand(item, pos))

    def onItemRotated(self, item, angle):
        self.undoStack.push(itemRotateCommand(item, angle))

    def onDelItem(self, scene, item):
        self.undoStack.push(itemDelCommand(scene, item))

    def setAlignment(self, alignment):
        items = self.scene.selectedItems()
        if len(items) <= 1:
            return
        leftXs, rightXs, topYs, bottomYs = [], [], [], []
        for item in items:
            rect = item.sceneBoundingRect()
            leftXs.append(rect.x())
            rightXs.append(rect.x() + rect.width())
            topYs.append(rect.y())
            bottomYs.append(rect.y() + rect.height())
        if alignment == Qt.AlignLeft:
            xAlignment = min(leftXs)
            for i, item in enumerate(items):
                item.moveBy(xAlignment - leftXs[i], 0)
        elif alignment == Qt.AlignRight:
            xAlignment = max(rightXs)
            for i, item in enumerate(items):
                item.moveBy(xAlignment - rightXs[i], 0)
        elif alignment == Qt.AlignTop:
            yAlignment = min(topYs)
            for i, item in enumerate(items):
                item.moveBy(0, yAlignment - topYs[i])
        elif alignment == Qt.AlignBottom:
            yAlignment = max(bottomYs)
            for i, item in enumerate(items):
                item.moveBy(0, yAlignment - bottomYs[i])

    def cutitem(self):
        try:
            item = self.selectedItem()
            if len(item) >= 1:
                for i in item:
                    self.copyitem()
                    self.scene.removeItem(i)
                    del i
        except Exception as e:
            print(e)

    def center(self):
        cp = QDesktopWidget().availableGeometry().center()
        qr = self.frameGeometry()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def on_open(self, filename):
        self.undoStack.clear()
        self.filename = filename
        fh = None
        try:
            fh = QFile(self.filename)
            if not fh.open(QIODevice.ReadOnly):
                raise IOError(str(fh.errorString()))
            items = self.scene.items()
            while items:
                item = items.pop()
                self.scene.removeItem(item)
                del item
            self.scene.clear()
            stream = QDataStream(fh)
            stream.setVersion(QDataStream.Qt_5_7)
            while not fh.atEnd():
                self.readItemFromStream(stream)

            self.undoStack.clear()

        except IOError as e:
            QMessageBox.warning(self, "打开出错",
                                "打开失败： {0}: {1}".format(self.filename, e))
        finally:
            if fh is not None:
                fh.close()
            try:
                del fh
                del items
                del stream
                del self.filename
                gc.collect()
            except Exception as e:
                print(e)

    def on_save(self, filename):
        self.filename = filename
        initial = self.scene.items()
        fh = None
        try:
            fh = QFile(self.filename)
            if not fh.open(QIODevice.WriteOnly):
                raise IOError(str(fh.errorString()))
            self.scene.clearSelection()
            stream = QDataStream(fh)
            stream.setVersion(QDataStream.Qt_5_7)
            if initial != []:
                for item in self.scene.items():
                    self.writeItemToStream(stream, item)
            else:
                item = None
        except IOError as e:
            QMessageBox.warning(self, "保存失败",
                                "保存失败： {0}: {1}".format(self.filename, e))
        finally:
            if fh is not None:
                fh.close()
        del t
        del t1
        del fh
        del self.filename
        del stream
        del item
        gc.collect()

    def copyitem(self):

        item = self.selectedItem()
        # print(item)
        if item == []:
            return
        else:
            item = item[0]
            self.copiedItem.clear()
            self.pasteOffset = 10
            stream = QDataStream(self.copiedItem, QIODevice.WriteOnly)
            stream.setVersion(QDataStream.Qt_5_7)
            self.writeItemToStream(stream, item)
            # for i in item:
            #     self.copiedItem.clear()
            #     self.pasteOffset = 10
            #     stream = QDataStream(self.copiedItem, QIODevice.WriteOnly)
            #     stream.setVersion(QDataStream.Qt_5_7)
            #     self.writeItemToStream(stream, i)

    def pasteitem(self):
        try:
            stream = QDataStream(self.copiedItem, QIODevice.ReadOnly)
            self.readItemFromStream(stream, self.pasteOffset)
            self.pasteOffset += 10
        except Exception as e:
            print(e)

    def writeItemToStream(self, stream, item):
        # print("PaintBoard1:writeItemtostream")
        if isinstance(item, ArrowItem):
            stream.writeQString("ArrowItem")
            stream << item.pos() << QPointF(item.pos_src[0], item.pos_src[1]) << QPointF(item.pos_dst[0],
                                                                                         item.pos_dst[1]) << QColor(
                item.pen_color)
            stream.writeInt32(item.pen_style)
            stream.writeInt(item.pen_width)
        elif isinstance(item, RectItem):
            stream.writeQString("Rect")
            stream << item.pos() << item.rect() << QColor(item.brush_color) << QColor(item.pen_color)
            stream.writeInt32(item.pen_style)
            stream.writeInt(item.pen_width)
            stream.writeFloat(item.rotation())
        elif isinstance(item, EllipseItem):
            stream.writeQString("Ellipse")
            stream << item.pos() << item.rect() << QColor(item.brush_color) << QColor(item.pen_color)
            stream.writeInt32(item.pen_style)
            stream.writeInt(item.pen_width)
            stream.writeFloat(item.rotation())
        elif isinstance(item, PItem):
            stream.writeQString("PItem")
            stream << item.pos() << item.rect() << item.pix
            stream.writeFloat(item.rotation())
        elif isinstance(item, PItem_paste):
            stream.writeQString("PItem_paste")
            stream << item.pos() << item.rect() << item.pix
            stream.writeFloat(item.rotation())
        elif isinstance(item, TextItem):
            stream.writeQString("TextItem")
            stream << item.pos()
            stream.writeQString(item.toPlainText())
            stream << item.font()

    def readItemFromStream(self, stream, offset=0):
        # print("PaintBoard1:readItemtostream")
        position = QPointF()
        rect = QRectF()
        begin = QPointF()
        end = QPointF()
        brush_color = QColor()
        pen_color = QColor()
        type = stream.readQString()
        font = QFont()

        if type == "ArrowItem":
            stream >> position >> begin >> end >> pen_color
            style = stream.readInt32()
            width = stream.readInt()
            Ar = ArrowItem(self.scene, pen_color, width, style)
            Ar.set_src(begin.x() + offset, begin.y() + offset)
            Ar.set_dst(end.x() + offset, end.y() + offset)
            Ar.update()
            Ar.setPos(position)
            Ar.setZValue(0.1)
            self.scene.itemAdded.emit(self.scene, Ar)
            # self.scene.addItem(Ar)

        elif type == "Rect":
            stream >> position >> rect >> brush_color >> pen_color
            if offset:
                position += QPointF(offset, offset)
            style = stream.readInt32()
            width = stream.readInt()
            rotateangle = stream.readFloat()
            bx = RectItem(brush_color, style, pen_color, width, None, rect)
            bx.setTransformOriginPoint(rect.center())
            bx.setRotation(rotateangle)
            bx.setPos(position)
            bx.setZValue(0.1)
            self.scene.itemAdded.emit(self.scene, bx)
            # self.scene.addItem(bx)

        elif type == "Ellipse":
            stream >> position >> rect >> brush_color >> pen_color
            if offset:
                position += QPointF(offset, offset)
            style = stream.readInt32()
            width = stream.readInt()
            rotateangle = stream.readFloat()
            ex = EllipseItem(brush_color, style, pen_color, width, rect)
            ex.setTransformOriginPoint(rect.center())
            ex.setRotation(rotateangle)
            ex.setPos(position)
            ex.setZValue(0.1)
            self.scene.itemAdded.emit(self.scene, ex)
            # self.scene.addItem(ex)

        elif type == "PItem":
            pixmap1 = QPixmap()
            stream >> position >> rect >> pixmap1
            pic = pixmap1
            PI = PItem_paste(pic, position)
            rotateangle = stream.readFloat()
            if offset:
                position += QPointF(offset, offset)
            PI.setRect(rect)
            PI.setTransformOriginPoint(rect.center())
            PI.setRotation(rotateangle)
            PI.setPos(position)
            PI.setSelected(True)
            self.scene.itemAdded.emit(self.scene, PI)
            # self.scene.addItem(PI)

        elif type == "PItem_paste":
            pixmap1 = QPixmap()
            stream >> position >> rect >> pixmap1
            pic = pixmap1
            Ps = PItem_paste(pic, position)
            rotateangle = stream.readFloat()
            if offset:
                position += QPointF(offset, offset)
            Ps.setRect(rect)
            Ps.setTransformOriginPoint(rect.center())
            Ps.setRotation(rotateangle)
            Ps.setPos(position)
            Ps.setSelected(True)
            self.scene.itemAdded.emit(self.scene, Ps)
            # self.scene.addItem(Ps)


        else:
            stream >> position
            text = stream.readQString()
            stream >> font
            # print(text, font)
            ti = TextItemDlg()
            if offset:
                position += QPointF(offset, offset)
            ti.position = position
            ti.scene = self.scene
            ti.font = font
            ti.editor.setText(text)
            ti.accept()

    def test_open(self):
        self.filename = "./"
        path = (QFileInfo(self.filename).path()
                if self.filename else ".")
        fname, filetype = QFileDialog.getOpenFileName(self,
                                                      "打开文件", path,
                                                      "打开pgd文件 (*.pgd)")
        if not fname:
            return
        self.filename = fname
        fh = None
        try:
            fh = QFile(self.filename)
            if not fh.open(QIODevice.ReadOnly):
                raise IOError(str(fh.errorString()))
            items = self.scene.items()
            while items:
                item = items.pop()
                self.scene.removeItem(item)
                del item

            stream = QDataStream(fh)
            stream.setVersion(QDataStream.Qt_5_7)
            # magic = stream.readInt32()
            # if magic != MagicNumber:
            #     raise IOError("not a valid .pgd file")
            # fileVersion = stream.readInt16()
            # if fileVersion != FileVersion:
            #     raise IOError("unrecognised .pgd file version")
            while not fh.atEnd():
                self.readItemFromStream(stream)
        except IOError as e:
            QMessageBox.warning(self, "打开出错",
                                "打开失败： {0}: {1}".format(self.filename, e))
        finally:
            if fh is not None:
                fh.close()

    def test_save(self):
        path = "."
        fname, filetype = QFileDialog.getSaveFileName(self,
                                                      "文件保存", path,
                                                      "pgd文件 (*.pgd)")
        if not fname:
            return
        self.filename = fname
        fh = None
        try:
            fh = QFile(self.filename)
            if not fh.open(QIODevice.WriteOnly):
                raise IOError(str(fh.errorString()))
            self.scene.clearSelection()
            stream = QDataStream(fh)
            stream.setVersion(QDataStream.Qt_5_7)
            # stream.writeInt32(0x70616765)
            # stream.writeInt16(1)
            for item in self.scene.items():
                self.writeItemToStream(stream, item)
        except IOError as e:
            QMessageBox.warning(self, "保存失败",
                                "保存失败： {0}: {1}".format(self.filename, e))
        finally:
            if fh is not None:
                fh.close()

    def itemscaled(self, scaled):
        self.horizontalSlider.setValue(scaled * 100)
        self.scaled_label.setText(str("{}%".format(int(scaled * 100))))

    def item_islike_PItem(self, item):
        if item.type() == 4:
            self.tailor.setEnabled(True)
        else:
            self.tailor.setEnabled(False)

    def itemcolorshow(self, item):
        # print(item.pen_color,item.brush_color)
        if isinstance(item, QGraphicsRectItem) == True and item.type() != 4:
            self.colorbox.createColorToolButtonIcon(item.pen_color)
            self.fillcolorbox.createColorToolButtonIcon(item.brush_color)

    def item_tailor(self):
        try:
            if self.selectedItem() != None:
                # print(self.tailor.isChecked())
                if self.tailor.isChecked():
                    self.selectedItem()[0].tailor = True
                else:
                    self.selectedItem()[0].tailor = False
        except Exception as e:
            print(e)

    def item_brush_color_changed(self, color):
        if self.selectedItem() != None:
            for i in self.selectedItem():
                i.brush_color = color
                i.update()

    def item_pen_width_changed(self, width):
        if self.selectedItem() != None:
            for i in self.selectedItem():
                i.pen_width = width
                i.update()

    def item_pen_color_changed(self, color):
        if self.selectedItem() != None:
            for i in self.selectedItem():
                i.pen_color = color
                i.update()

    def item_pen_style_changed(self, style):
        if self.selectedItem() != None:
            for i in self.selectedItem():
                i.pen_style = style
                i.update()

    def wh_change(self):
        # print(self.selectedItem())
        if self.selectedItem() != None:
            for i in self.selectedItem():
                if isinstance(i, QGraphicsRectItem) == True:
                    oldRect = i.rect()
                    # print("old",oldRect)
                    if isinstance(i, QGraphicsRectItem) == True:
                        origin_w = int(i.rect().width())  # + 12
                        origin_h = int(i.rect().height())  # + 12
                        modified_w = int(float(self.width_lineEdit.text()))
                        modified_h = int(float(self.height_lineEdit.text()))
                        diff_w = modified_w - origin_w
                        diff_h = modified_h - origin_h
                        if diff_h == 0:
                            final_w = modified_w
                            final_h = final_w * (origin_h / origin_w)
                        else:
                            final_h = modified_h
                            final_w = final_h * (origin_w / origin_h)

                        self.width_lineEdit.setText(str(final_w))
                        self.height_lineEdit.setText(str(final_h))
                        # i.setRect(0, 0, final_w - 12, final_h - 12)

                        newRect = QRectF(oldRect.x(), oldRect.y(), final_w, final_h)
                        pointO = i.mapToScene(oldRect.center())
                        pointC = i.mapToScene(newRect.center())
                        self.delta = pointO - pointC

                        w = newRect.width()
                        h = newRect.height()
                        # self.scene.itemResized.emit(i, oldRect, delta)
                        self.m_localRect = QRectF(-w / 2, -h / 2, w, h)
                        i.setRect(self.m_localRect)
                        self.scene.itemResized.emit(i, oldRect, self.delta)
                        i.setTransformOriginPoint(self.m_localRect.center())
                        # i.moveBy(-self.delta.x(), -self.delta.y())
                        # i.setRect(0, 0, final_w, final_h)
                        # print("new",i.rect())

                        # self.scene.itemResized.emit(i, oldRect, delta)

    def keyPressEvent(self, event):
        # print(self.selectedItem()[0])
        if event.key() == Qt.Key_Delete:
            self.delete()
        if len(self.selectedItem()) >= 1 and isinstance(self.selectedItem()[0], QGraphicsRectItem) == True:
            if event.modifiers() == Qt.ShiftModifier:
                self.selectedItem()[0].keepratio = True
            else:
                self.keepratio = False

        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_C:
            self.copyitem()

        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_V:
            self.pasteitem()

        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_A:
            for it in self.scene.items():
                it.setSelected(True)
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_S:
            self.on_btn_Save_Clicked()
            self.parentWin.save_picture_to_table()
        if event.key() == Qt.Key_Escape:
            self.scene.clearSelection()

    def keyReleaseEvent(self, event):
        if len(self.selectedItem()) >= 1 and isinstance(self.selectedItem()[0], QGraphicsRectItem) == True:
            self.selectedItem()[0].keepratio = False

    def delete(self):
        items = self.scene.selectedItems()
        # if (len(items) and QMessageBox.question(self,
        # "删除",
        # "删除{0}个元素?".format(len(items)
        # ),
        # QMessageBox.Yes | QMessageBox.No) ==
        # QMessageBox.Yes):
        while items:
            item = items.pop()
            self.scene.itemDeled.emit(self.scene, item)
            # self.scene.removeItem(item)
            del item

    def my_paint_print(self):
        self.printer = QPrinter(QPrinter.HighResolution)
        self.printer.setPageSize(QPrinter.Letter)
        dialog = QPrintDialog(self.printer)
        if dialog.exec_():
            painter = QPainter(self.printer)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            self.scene.clearSelection()
            self.scene.render(painter)

    def reload_size(self):
        item = self.graphics.scene.selectedItems()
        if item == []:
            pass
        else:
            # if item[0].type() == 7:
            #     self.graphics.reload_size(item[0])
            # else:
            self.graphics.remove_to_origin(item[0])

    # 图片保存功能
    def on_btn_Save_Clicked(self):
        try:
            # savePath = QFileDialog.getSaveFileName(self, '保存图片', '.\\', '*.jpg;*.png')
            #
            # if savePath[0] == "":
            #     print("取消保存")
            #     return
            # pm=QPixmap(self.pixfixed.width(), self.pixfixed.height())
            self.scene.clearSelection()
            pm = QPixmap(900, 600)  # 注意，设置画布的大小为Myscene的大小，下边保存时才不会产生黑边

            pm.fill(Qt.white)  # 当区域没有Item时，保存图片不产生黑色区域

            # 设置绘图工具
            painter1 = QPainter(pm)
            painter1.setRenderHint(QPainter.Antialiasing)
            painter1.setRenderHint(QPainter.SmoothPixmapTransform)

            # 使打印长和宽与导入的Pixmap图片长宽匹配，不会产生黑边
            # self.graphics.render(painter1,QRectF(0,0,self.pixfixed.width(),self.pixfixed.height()),QRect(0,0,self.pixfixed.width(),self.pixfixed.height()))

            # 注意，大小设置与Myscene的大小一致，画布大小一致时，才真的不会产生黑边,原始：600,500
            self.graphics.render(painter1, QRectF(0, 0, 900, 600), QRect(0, 0, 900, 600))
            # QRect(0, 0, 600, 500))
            painter1.end()
            # pm.save(savePath[0])

            self.item = QTableWidgetItem()
            self.item.setFlags(Qt.ItemIsEnabled)  # 用户点击时表格时，图片被选中
            icon = QIcon(pm)
            self.item.setIcon(QIcon(icon))


        except Exception as e:
            print(e)

    def line_btn_clicked1(self, *type):
        type = "line"
        self.graphics.Shape(type)

    def wc(self, item):
        if item:
            width = int(item.boundingRect().width() - 12)
            height = int(item.boundingRect().height() - 12)
            self.width_lineEdit.setText(str(width))
            self.height_lineEdit.setText(str(height))

    # 记录鼠标选择的items
    def selectedItem(self):
        items = self.scene.selectedItems()
        if len(items) == 1:
            # return items[0]
            return items
        else:
            return items

    # 添加可变矩形
    def item_rect_change(self):

        self.scene.addItem(Rectangle(200, 150, 100, 100))

    # 上移一层(实际为置顶)
    def item_up(self):
        try:
            selected = self.scene.selectedItems()[0]
            overlapItems = selected.collidingItems()
            if self.selectedItem() == None:
                print("no item selected")
            else:
                zValue = 0
                for item in overlapItems:
                    if item.zValue() >= zValue:
                        zValue = item.zValue() + 0.1
                # print(zValue)
                selected.setZValue(zValue)
        except Exception as e:
            print(e)

    # 下移一层(实际为置底)
    def item_down(self):
        try:
            selected = self.scene.selectedItems()[0]
            overlapItems = selected.collidingItems()
            if self.selectedItem() == None:
                print("no item selected")
            else:
                zValue = 0
                for item in overlapItems:
                    if item.zValue() <= zValue:
                        zValue = item.zValue() - 0.1
                # print(zValue)
                selected.setZValue(zValue)
        except Exception as e:
            print(e)

    # 撤销上一个绘图的图元
    def drawback(self, *item):
        try:
            self.undoStack.undo()
        except Exception as e:
            print(e)

    # 设置图片移动
    def on_pic_move_btn_clicked(self, *type):
        type = "move"
        self.graphics.Shape(type)
        self.scene.clearSelection()

    # 添加文本
    def addText(self):
        try:
            dialog = TextItemDlg(position=QPoint(200, 200),
                                 scene=self.scene, parent=None)
            dialog.exec_()
        except Exception as e:
            print(e)

    # def on_Scene_size_clicked(self):
    #     w = self.scene.width()
    #     h = self.scene.height()
    #     p = self.width()
    #     q = self.height()
    #     s = self.size()

    def on_Free_pen_btn_clicked1(self, *shape):
        shape = "Free pen"
        self.graphics.Shape(shape)

    # 设置画圆圈
    def on_circle_btn_clicked1(self, *shape):  # 注意传入参数为文字时，为*加上变量，即“*变量”
        try:
            shape = "circle"
            self.graphics.Shape(shape)
        except Exception as e:
            print(e)

    def on_rect_btn_clicked1(self, *shape):
        shape = "rect"
        self.graphics.Shape(shape)

    # 打开图片功能
    def on_btn_Open_Clicked(self):
        try:
            openPath = QFileDialog.getOpenFileName(self, '打开图片', '', '*.png;*.jpg')
            # print(openPath)
            if openPath[0] == "":
                print("已取消")
                return
            filename = openPath[0]
            # print(filename)
            self.pix = QPixmap()
            self.pix.load(filename)
            # print(self.pix.width(),self.pix.height())
            # 对于图片长宽超过800,600的，缩放后完全显示
            self.pixfixed = self.pix.scaled(900, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            # self.scene.addPixmap(self.pixfixed)
            # print(self.pixfixed.width(),self.pixfixed.height())
            item1 = PItem(filename, 0, 0, 900, 600)
            item1.updateCoordinate()
            item1.moveBy(item1.rect().width() / 2, item1.rect().height() / 2)
            self.scene.itemAdded.emit(self.scene, item1)
            # self.scene.addItem(item1)

            item = QGraphicsPixmapItem(self.pixfixed)
            # item.setFlag(QGraphicsItem.ItemIsSelectable)
            item.setFlag(QGraphicsItem.ItemIsMovable)
            item.setZValue(-1)
            # self.pixrect=item.boundingRect()
            # self.scene.addItem(item)
            self.pw = self.pixfixed.width()
            self.ph = self.pixfixed.height()
        except Exception as e:
            print(e)

    # 退出画板主窗口
    def on_btn_Quit_Clicked(self):
        self.close()

    # combobox填充颜色序列
    def __fillColorList(self, comboBox):
        index_red = 0
        index = 0
        for color in self.__colorList:
            if color == "red":
                index_red = index
            index += 1
            pix = QPixmap(120, 30)
            pix.fill(QColor(color))
            comboBox.addItem(QIcon(pix), None)
            comboBox.setIconSize(QSize(100, 20))
            comboBox.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        comboBox.setCurrentIndex(index_red)

    def __fillWidthList(self, comboBox):
        color = Qt.black
        set_current_index = 1
        for i in range(15):
            pix = QPixmap(200, i + 2)
            pix.fill(QColor(color))
            comboBox.addItem(QIcon(pix), str(i + 1))
            comboBox.setIconSize(QSize(100, 20))
            comboBox.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        comboBox.setCurrentIndex(set_current_index)

    def on_BrushColorChange(self, color):
        self.graphics.ChangeBrushColor(color)

    # 画笔颜色更改
    def on_PenColorChange(self, color):
        print(color)
        self.graphics.ChangePenColor(color)

    def on_PenStyleChange(self, style):
        print("style:", style)
        self.graphics.ChangePenStyle(style)

    # 画笔粗细调整
    def on_PenThicknessChange(self, thick):
        # penThickness = int(self.Pen_Thickness.currentText())
        print("thick:", thick)
        self.graphics.ChangePenThickness(thick)

    # 橡皮擦粗细调整
    def on_EraserThicknessChange(self):
        EraserThickness = self.Eraser_thickness.value()
        self.scene.ChangeEraserThickness(EraserThickness)
        pm = QPixmap('circle.ico')
        r = self.Eraser_thickness.value()
        pm = pm.scaled(r, r, Qt.KeepAspectRatio)
        cursor = QCursor(pm)
        self.setCursor(cursor)

    # 清除图元
    def clean_all(self):
        try:
            self.scene.clear()
            self.undoStack.clear()
        except Exception as e:
            print(e)

    # def closeEvent(self, QCloseEvent):


class ColorCombox(QWidget):
    # 发送颜色更改信号，类型为Qcolor的object类型
    signal = pyqtSignal(object)
    thick_signal = pyqtSignal(object)
    style_signal = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        # 设置场景颜色，大小是6*10二维列表
        theme_colors = [
            [QColor(255, 255, 255, 255), QColor(0, 0, 0, 255), QColor(231, 230, 230, 255), QColor(64, 84, 106, 255),
             QColor(91, 155, 213, 255), QColor(237, 124, 48, 255), QColor(165, 165, 165, 255), QColor(255, 192, 0, 255),
             QColor(68, 114, 196, 255), QColor(112, 173, 71, 255)],

            [QColor(242, 242, 242, 255), QColor(127, 127, 127, 255), QColor(208, 206, 206, 255),
             QColor(214, 220, 228, 255),
             QColor(222, 235, 246, 255), QColor(251, 229, 213, 255), QColor(237, 237, 237, 237),
             QColor(255, 242, 204, 255), QColor(217, 226, 243, 255), QColor(226, 239, 217, 255)],

            [QColor(216, 216, 216, 255), QColor(89, 89, 89, 255), QColor(174, 171, 171, 255),
             QColor(173, 185, 202, 255),
             QColor(189, 215, 238, 255), QColor(247, 203, 172, 255), QColor(219, 219, 219, 255),
             QColor(254, 229, 153, 255), QColor(180, 198, 231, 255), QColor(197, 224, 179, 255)],

            [QColor(191, 191, 191, 255), QColor(63, 63, 63, 255), QColor(117, 112, 112, 255),
             QColor(132, 150, 176, 255),
             QColor(156, 195, 229, 255), QColor(244, 177, 131, 255), QColor(201, 201, 201, 255),
             QColor(255, 217, 101, 255), QColor(142, 170, 219, 255), QColor(168, 208, 141, 255)],

            [QColor(165, 165, 165, 255), QColor(38, 38, 38, 255), QColor(58, 56, 56, 255), QColor(50, 63, 79, 255),
             QColor(39, 112, 179, 255), QColor(197, 90, 17, 255), QColor(123, 123, 123, 255), QColor(191, 144, 0, 255),
             QColor(47, 84, 150, 255), QColor(83, 129, 53, 255)],

            [QColor(124, 124, 124, 255), QColor(12, 12, 12, 255), QColor(23, 22, 22, 255), QColor(34, 42, 53, 255),
             QColor(34, 81, 123, 255), QColor(124, 48, 2, 255), QColor(82, 82, 82, 255), QColor(127, 96, 0, 255),
             QColor(31, 56, 100, 255), QColor(55, 86, 35, 255)]
        ]

        # 设置基础颜色，大小是1*10一维列表
        basic_colors = [
            QColor(192, 0, 0, 255), QColor(255, 0, 0, 255), QColor(255, 192, 0, 255),
            QColor(255, 255, 0, 255), QColor(146, 208, 80, 255), QColor(0, 176, 80, 255),
            QColor(0, 176, 240, 255), QColor(0, 112, 192, 255), QColor(0, 32, 96, 255),
            QColor(112, 48, 160, 255)
        ]

        # 设置下拉框总按钮
        self.ColorCombox = QToolButton()
        self.ColorCombox.setAutoRaise(True)
        self.ColorCombox.setPopupMode(QToolButton.InstantPopup)  # 设置下拉框按钮按下时弹出菜单窗口
        self.ColorCombox.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # self.ColorCombox.setArrowType(Qt.DownArrow)
        self.ColorCombox.setText("形状轮廓")
        # self.ColorCombox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # self.ColorCombox.setMinimumSize(100, 30)
        self.ColorCombox.setAutoFillBackground(True)
        # 利用setStyleSheet设置QToolButton不显示下箭头
        # self.ColorCombox.setStyleSheet("QToolButton::menu-indicator {image: none;} QToolButton{font:bold 9pt '微软雅黑'}")
        self.ColorCombox.setStyleSheet(
            "QToolButton::menu-indicator {image: url(./down1.ico);} QToolButton{font:bold 9pt '微软雅黑'}")

        # 设置颜色下拉按钮的自定义图标Icon，这里是初始化
        qp = QPixmap(30, 30)  # 设置QPixmap场景大小
        qp.fill(Qt.transparent)
        self.pix = QPixmap()
        self.pix.load("ICon/pen_color.png")  # 这是画笔Icon，请替换成自己的图片或者利用QPainter画出笔也行
        pixfixed = self.pix.scaled(25, 25, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        target = QRect(0, 0, 25, 25)
        source = QRect(0, 0, 25, 25)
        painter = QPainter(qp)  # 设置QPainter在自己设的QPixmap上画
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(target, pixfixed, source)
        painter.fillRect(QRect(0, 22, 24, 5), Qt.red)
        painter.end()
        self.ColorCombox.setIcon(QIcon(qp))
        self.ColorCombox.setIconSize(QSize(30, 40))

        # 设置主题色标签
        title = QLabel(u"主题颜色")
        title.setStyleSheet("QLabel{background:lightgray;color:black;font:bold 8pt '微软雅黑'}")

        # 设置颜色6*10大小的主题颜色框架，利用QGridLayout布局放置颜色块
        pGridLayout = QGridLayout()
        pGridLayout.setAlignment(Qt.AlignCenter)
        pGridLayout.setContentsMargins(0, 0, 0, 0)
        pGridLayout.setSpacing(2)
        for i in range(6):
            for j in range(10):
                action = QAction()
                action.setData(theme_colors[i][j])
                action.setIcon(self.createColorIcon(theme_colors[i][j]))
                pBtnColor = QToolButton()
                pBtnColor.setFixedSize(QSize(20, 20))
                pBtnColor.setAutoRaise(True)
                pBtnColor.setDefaultAction(action)
                action.triggered.connect(self.OnColorChanged)
                pBtnColor.setToolTip(str(theme_colors[i][j].getRgb()))
                pGridLayout.addWidget(pBtnColor, i, j)

        # 设置标准色标签
        btitle = QLabel(u"标准色")
        btitle.setStyleSheet("QLabel{background:lightgray;color:black;font:bold 8pt '微软雅黑'}")

        # 设置颜色1*10大小的标准色框架，利用QGridLayout布局放置颜色块
        bGridLayout = QGridLayout()
        bGridLayout.setAlignment(Qt.AlignCenter)
        bGridLayout.setContentsMargins(0, 0, 0, 0)
        bGridLayout.setSpacing(2)
        for m in range(10):
            baction = QAction()
            baction.setData(basic_colors[m])
            baction.setIcon(self.createColorIcon(basic_colors[m]))
            bBtnColor = QToolButton()
            bBtnColor.setFixedSize(QSize(20, 20))
            bBtnColor.setAutoRaise(True)
            bBtnColor.setDefaultAction(baction)
            baction.triggered.connect(self.OnColorChanged)
            bBtnColor.setToolTip(str(basic_colors[m].getRgb()))
            bGridLayout.addWidget(bBtnColor, 0, m)

        # 设置分割水平线，利用QFrame
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)

        # 设置“无边框（透明色）”按钮功能
        pBtnTransparent = QToolButton()
        pBtnTransparent.setArrowType(Qt.NoArrow)
        pBtnTransparent.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        pBtnTransparent.setFixedSize(218, 20)
        pBtnTransparent.setAutoRaise(True)
        pBtnTransparent.setStyleSheet("QToolButton{font:bold 8pt '微软雅黑'}")
        pBtnTransparent.setText("无轮廓")
        pBtnTransparent.setIcon(QIcon("ICon/Frame.png"))
        pBtnTransparent.setIconSize(QSize(20, 20))
        pBtnTransparent.clicked.connect(self.set_pen_Transparent)

        # 设置“选择其他颜色”按钮功能
        othercolor_btn = QToolButton()
        othercolor_btn.setArrowType(Qt.NoArrow)
        othercolor_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        othercolor_btn.setFixedSize(218, 20)
        othercolor_btn.setAutoRaise(True)
        othercolor_btn.setIcon(QIcon("ICon/color.png"))
        othercolor_btn.setText(u"选择其他颜色")
        othercolor_btn.setIconSize(QSize(15, 15))
        othercolor_btn.setStyleSheet("QToolButton{font:bold 8pt '微软雅黑'}")
        othercolor_btn.clicked.connect(self.on_colorboard_show)

        # 将设置好的颜色框架，用QWidget包装好
        widget = QWidget()
        widget.setLayout(pGridLayout)
        bwidget = QWidget()
        bwidget.setLayout(bGridLayout)

        #  将上述设置的这些所有颜色框架，小组件窗口，用QVBoxLayout包装好
        pVLayout = QVBoxLayout()
        pVLayout.setSpacing(1)
        pVLayout.addWidget(title)
        pVLayout.addWidget(widget)
        pVLayout.addWidget(btitle)
        pVLayout.addWidget(bwidget)
        pVLayout.addWidget(line)
        pVLayout.addWidget(pBtnTransparent)
        pVLayout.addWidget(othercolor_btn)

        # 设置分割水平线，利用QFrame
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Plain)
        pVLayout.addWidget(line2)

        # 画笔粗细按钮
        self.thicknessbtn = QToolButton(self, text="粗细")
        self.thicknessbtn.setFixedSize(218, 20)
        self.thicknessbtn.setAutoRaise(True)
        self.thicknessbtn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # 自定义画笔粗细的QIcon
        thickIcon = QPixmap(30, 30)
        thickIcon.fill(Qt.white)
        thickpainter = QPainter(thickIcon)
        d = 5
        for k in range(4):
            thickpainter.setPen(QPen(Qt.black, k + 1, Qt.SolidLine))
            thickpainter.drawLine(0, (d + 1) * k + 5, 30, (d + 1) * k + 5)
        thickpainter.end()
        self.thicknessbtn.setIcon(QIcon(thickIcon))

        self.thicknessbtn.setPopupMode(QToolButton.InstantPopup)
        self.thicknessbtn.setArrowType(Qt.NoArrow)
        self.thicknessbtn.setStyleSheet(
            "QToolButton::menu-indicator {image: none;} QToolButton{font:bold 8pt '微软雅黑'}")

        tLayout = QVBoxLayout()
        tLayout.setSpacing(0)
        self.thicknessmenu = QMenu(self)
        for i in range(10):
            action = QAction(parent=self.thicknessmenu)
            action.setData(i)
            action.setIcon(self.set_width_Icon(i + 1))
            action.setText("{}磅".format(i + 1))
            pBtnWidth = QToolButton()
            pBtnWidth.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            pBtnWidth.setIconSize(QSize(100, 10))
            pBtnWidth.setStyleSheet(
                "QToolButton::menu-indicator {image: none;}")
            pBtnWidth.setAutoRaise(True)
            pBtnWidth.setDefaultAction(action)
            action.triggered.connect(self.OnWidthChanged)
            pBtnWidth.setToolTip(str("粗细:{}磅".format(i + 1)))
            tLayout.addWidget(pBtnWidth, i)
        self.twidget = QWidget()
        self.twidget.setLayout(tLayout)
        tVLayout = QVBoxLayout()
        tVLayout.setSpacing(1)
        tVLayout.setContentsMargins(1, 1, 1, 1)
        tVLayout.addWidget(self.twidget)
        self.thicknessmenu.setLayout(tVLayout)
        self.thicknessbtn.setMenu(self.thicknessmenu)
        self.thicknessmenu.showEvent = self.thickness_show
        pVLayout.addWidget(self.thicknessbtn)

        # 画笔虚线设定
        style = [Qt.NoPen, Qt.SolidLine, Qt.DashLine, Qt.DotLine,
                 Qt.DashDotLine, Qt.DashDotDotLine, Qt.CustomDashLine]
        name = ["无", "实线", "虚线", "点线", "点虚线", "点点虚线", "自定义"]

        # 画笔虚线按钮
        self.stylebtn = QToolButton(self, text="虚线")
        self.stylebtn.setFixedSize(218, 20)
        self.stylebtn.setAutoRaise(True)
        self.stylebtn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # 自定义画笔虚线的QIcon
        styleIcon = QPixmap(30, 30)
        styleIcon.fill(Qt.white)
        stylepainter = QPainter(styleIcon)
        f = 5
        for k in range(4):
            stylepainter.setPen(style[k + 1])
            stylepainter.drawLine(0, (f + 1) * k + 5, 30, (f + 1) * k + 5)
        stylepainter.end()
        self.stylebtn.setIcon(QIcon(styleIcon))
        self.stylebtn.setPopupMode(QToolButton.InstantPopup)
        self.stylebtn.setArrowType(Qt.NoArrow)
        self.stylebtn.setStyleSheet(
            "QToolButton::menu-indicator {image: none;} QToolButton{font:bold 8pt '微软雅黑'}")

        sLayout = QVBoxLayout()
        sLayout.setSpacing(0)
        self.stylemenu = QMenu(self)
        for j in range(7):
            saction = QAction(parent=self.stylemenu)
            saction.setData(style[j])
            saction.setIcon(self.set_style_Icon(style[j]))
            saction.setText(name[j])
            sBtnStyle = QToolButton()
            sBtnStyle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            sBtnStyle.setIconSize(QSize(100, 10))
            sBtnStyle.setStyleSheet(
                "QToolButton::menu-indicator {image: none;}")
            sBtnStyle.setAutoRaise(True)
            sBtnStyle.setDefaultAction(saction)
            saction.triggered.connect(self.OnStyleChanged)
            sBtnStyle.setToolTip(str(style[j]))
            sLayout.addWidget(sBtnStyle, j)

        self.swidget = QWidget()
        self.swidget.setLayout(sLayout)
        sVLayout = QVBoxLayout()
        sVLayout.setSpacing(1)
        sVLayout.setContentsMargins(1, 1, 1, 1)
        sVLayout.addWidget(self.swidget)
        self.stylemenu.setLayout(sVLayout)
        self.stylebtn.setMenu(self.stylemenu)
        self.stylemenu.showEvent = self.style_show
        pVLayout.addWidget(self.stylebtn)

        # 设置弹出菜单，菜单打上上述打包好所有颜色框架、窗口的pVLayout内容
        self.colorMenu = QMenu(self)
        self.colorMenu.setLayout(pVLayout)

        # 设置下拉框按钮菜单为上述菜单
        self.ColorCombox.setMenu(self.colorMenu)

        ### 将所有上述打包好的内，用本类设置的QWidget打包成窗口控件 ###
        alLayout = QVBoxLayout()
        alLayout.setSpacing(0)
        alLayout.addWidget(self.ColorCombox)
        self.setLayout(alLayout)

    ### ——以下为本类所用到的函数—— ###

    # 重设画笔粗细按钮按下后菜单出现在右侧
    def thickness_show(self, e):
        parent = self.colorMenu.pos()
        pos = self.thicknessbtn.geometry()
        m = self.thicknessmenu.geometry()
        w = pos.width()
        self.thicknessmenu.move(parent.x() + w + 13, m.y() - pos.height())

    # 重设画笔虚线按钮按下后菜单出现在右侧
    def style_show(self, e):
        parent = self.colorMenu.pos()
        pos = self.stylebtn.geometry()
        m = self.stylemenu.geometry()
        w = pos.width()
        self.stylemenu.move(parent.x() + w + 13, m.y() - pos.height())

    # 设置画笔粗细菜单栏中的所有Icon图标
    def set_width_Icon(self, width):
        color = Qt.black
        pix = QPixmap(100, width)
        pix.fill(QColor(color))
        return QIcon(pix)

    # 设置画笔粗细选中时的操作
    def OnWidthChanged(self):
        width = self.sender().data() + 1
        # print(width)
        self.thicknessmenu.close()
        self.colorMenu.close()
        self.thick_signal.emit(width)

    # 设置画笔虚线菜单栏中的所有Icon图标
    def set_style_Icon(self, style):
        # print(style)
        color = Qt.black
        pix = QPixmap(100, 6)
        pix.fill(Qt.white)
        painter = QPainter(pix)
        pp = QPen()
        pp.setStyle(style)
        pp.setColor(color)
        pp.setWidth(3)
        painter.setPen(pp)
        painter.drawLine(0, 3, 100, 3)
        painter.end()
        return QIcon(pix)

    # 设置画笔虚线形状选中时的操作
    def OnStyleChanged(self):
        style = self.sender().data()
        # print(Qt.PenStyle(style))
        self.stylemenu.close()
        self.colorMenu.close()
        self.style_signal.emit(style)

    # 用于设置QAction颜色块的槽函数
    def createColorIcon(self, color):
        pixmap = QPixmap(18, 18)
        pixmap.fill(QColor(color))
        return QIcon(pixmap)

    # 当透明色设置按钮按下后的槽函数
    def set_pen_Transparent(self):
        color = Qt.transparent
        self.colorMenu.close()
        self.signal.emit(color)

    # 设置颜色下拉按钮的自定义图标Icon，这里是颜色变化时改变图标下层矩形填充颜色
    def createColorToolButtonIcon(self, color):
        # print(color)
        qp = QPixmap(30, 30)
        qp.fill(Qt.transparent)
        self.pix = QPixmap()
        self.pix.load("ICon/pen_color.png")
        pixfix = self.pix.scaled(25, 25, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        target = QRect(0, 0, 25, 25)
        source = QRect(0, 0, 25, 25)
        painter = QPainter(qp)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(target, pixfix, source)
        painter.fillRect(QRect(0, 22, 24, 5), color)
        painter.end()
        self.ColorCombox.setIcon(QIcon(qp))
        self.ColorCombox.setIconSize(QSize(30, 40))

    # 当颜色色块QAction按下后的槽函数
    def OnColorChanged(self):
        color = self.sender().data()
        self.colorMenu.close()
        self.signal.emit(color)

    # 当其他颜色按钮按下时弹出Qt自带的颜色选择器
    def on_colorboard_show(self):
        color = QColorDialog.getColor(Qt.black, self)
        if color.isValid():
            self.signal.emit(color)
            return color


class FillColorCombox(QWidget):
    # 发送颜色更改信号，类型为Qcolor的object类型
    signal = pyqtSignal(object)
    thick_signal = pyqtSignal(object)
    style_signal = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        # 设置场景颜色，大小是6*10二维列表
        theme_colors = [
            [QColor(255, 255, 255, 255), QColor(0, 0, 0, 255), QColor(231, 230, 230, 255), QColor(64, 84, 106, 255),
             QColor(91, 155, 213, 255), QColor(237, 124, 48, 255), QColor(165, 165, 165, 255), QColor(255, 192, 0, 255),
             QColor(68, 114, 196, 255), QColor(112, 173, 71, 255)],

            [QColor(242, 242, 242, 255), QColor(127, 127, 127, 255), QColor(208, 206, 206, 255),
             QColor(214, 220, 228, 255),
             QColor(222, 235, 246, 255), QColor(251, 229, 213, 255), QColor(237, 237, 237, 237),
             QColor(255, 242, 204, 255), QColor(217, 226, 243, 255), QColor(226, 239, 217, 255)],

            [QColor(216, 216, 216, 255), QColor(89, 89, 89, 255), QColor(174, 171, 171, 255),
             QColor(173, 185, 202, 255),
             QColor(189, 215, 238, 255), QColor(247, 203, 172, 255), QColor(219, 219, 219, 255),
             QColor(254, 229, 153, 255), QColor(180, 198, 231, 255), QColor(197, 224, 179, 255)],

            [QColor(191, 191, 191, 255), QColor(63, 63, 63, 255), QColor(117, 112, 112, 255),
             QColor(132, 150, 176, 255),
             QColor(156, 195, 229, 255), QColor(244, 177, 131, 255), QColor(201, 201, 201, 255),
             QColor(255, 217, 101, 255), QColor(142, 170, 219, 255), QColor(168, 208, 141, 255)],

            [QColor(165, 165, 165, 255), QColor(38, 38, 38, 255), QColor(58, 56, 56, 255), QColor(50, 63, 79, 255),
             QColor(39, 112, 179, 255), QColor(197, 90, 17, 255), QColor(123, 123, 123, 255), QColor(191, 144, 0, 255),
             QColor(47, 84, 150, 255), QColor(83, 129, 53, 255)],

            [QColor(124, 124, 124, 255), QColor(12, 12, 12, 255), QColor(23, 22, 22, 255), QColor(34, 42, 53, 255),
             QColor(34, 81, 123, 255), QColor(124, 48, 2, 255), QColor(82, 82, 82, 255), QColor(127, 96, 0, 255),
             QColor(31, 56, 100, 255), QColor(55, 86, 35, 255)]
        ]

        # 设置基础颜色，大小是1*10一维列表
        basic_colors = [
            QColor(192, 0, 0, 255), QColor(255, 0, 0, 255), QColor(255, 192, 0, 255),
            QColor(255, 255, 0, 255), QColor(146, 208, 80, 255), QColor(0, 176, 80, 255),
            QColor(0, 176, 240, 255), QColor(0, 112, 192, 255), QColor(0, 32, 96, 255),
            QColor(112, 48, 160, 255)
        ]

        # 设置下拉框总按钮
        self.ColorCombox = QToolButton()
        self.ColorCombox.setAutoRaise(True)
        self.ColorCombox.setPopupMode(QToolButton.InstantPopup)  # 设置下拉框按钮按下时弹出菜单窗口
        self.ColorCombox.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # self.ColorCombox.setArrowType(Qt.DownArrow)
        self.ColorCombox.setText("形状填充")
        # self.ColorCombox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # self.ColorCombox.setMinimumSize(100, 30)
        self.ColorCombox.setAutoFillBackground(True)
        # 利用setStyleSheet设置QToolButton不显示下箭头
        # self.ColorCombox.setStyleSheet("QToolButton::menu-indicator {image: none;} QToolButton{font:bold 9pt '微软雅黑'}")
        self.ColorCombox.setStyleSheet(
            "QToolButton::menu-indicator {image: url(./down1.ico);} QToolButton{font:bold 9pt '微软雅黑'}")

        # 设置颜色下拉按钮的自定义图标Icon，这里是初始化
        qp = QPixmap(30, 30)  # 设置QPixmap场景大小
        qp.fill(Qt.transparent)
        self.pix = QPixmap()
        self.pix.load("ICon/filled.png")  # 这是填充Icon，请替换成自己的图片或者利用QPainter画出笔也行
        pixfix = self.pix.scaled(25, 25, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        target = QRect(0, 0, 25, 25)
        source = QRect(0, 0, 25, 25)
        painter = QPainter(qp)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(target, pixfix, source)
        painter.fillRect(QRect(0, 22, 24, 5), Qt.transparent)
        painter.end()
        self.ColorCombox.setIcon(QIcon(qp))
        self.ColorCombox.setIconSize(QSize(30, 40))

        # 设置主题色标签
        title = QLabel(u"主题颜色")
        title.setStyleSheet("QLabel{background:lightgray;color:black;font:bold 8pt '微软雅黑'}")

        # 设置颜色6*10大小的主题颜色框架，利用QGridLayout布局放置颜色块
        pGridLayout = QGridLayout()
        pGridLayout.setAlignment(Qt.AlignCenter)
        pGridLayout.setContentsMargins(0, 0, 0, 0)
        pGridLayout.setSpacing(2)
        for i in range(6):
            for j in range(10):
                action = QAction()
                action.setData(theme_colors[i][j])
                action.setIcon(self.createColorIcon(theme_colors[i][j]))
                pBtnColor = QToolButton()
                pBtnColor.setFixedSize(QSize(20, 20))
                pBtnColor.setAutoRaise(True)
                pBtnColor.setDefaultAction(action)
                action.triggered.connect(self.OnColorChanged)
                pBtnColor.setToolTip(str(theme_colors[i][j].getRgb()))
                pGridLayout.addWidget(pBtnColor, i, j)

        # 设置标准色标签
        btitle = QLabel(u"标准色")
        btitle.setStyleSheet("QLabel{background:lightgray;color:black;font:bold 8pt '微软雅黑'}")

        # 设置颜色1*10大小的标准色框架，利用QGridLayout布局放置颜色块
        bGridLayout = QGridLayout()
        bGridLayout.setAlignment(Qt.AlignCenter)
        bGridLayout.setContentsMargins(0, 0, 0, 0)
        bGridLayout.setSpacing(2)
        for m in range(10):
            baction = QAction()
            baction.setData(basic_colors[m])
            baction.setIcon(self.createColorIcon(basic_colors[m]))
            bBtnColor = QToolButton()
            bBtnColor.setFixedSize(QSize(20, 20))
            bBtnColor.setAutoRaise(True)
            bBtnColor.setDefaultAction(baction)
            baction.triggered.connect(self.OnColorChanged)
            bBtnColor.setToolTip(str(basic_colors[m].getRgb()))
            bGridLayout.addWidget(bBtnColor, 0, m)

        # 设置分割水平线，利用QFrame
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)

        # 设置“无边框（透明色）”按钮功能
        pBtnTransparent = QToolButton()
        pBtnTransparent.setArrowType(Qt.NoArrow)
        pBtnTransparent.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        pBtnTransparent.setFixedSize(218, 20)
        pBtnTransparent.setAutoRaise(True)
        pBtnTransparent.setStyleSheet("QToolButton{font:bold 8pt '微软雅黑'}")
        pBtnTransparent.setText("无填充")
        pBtnTransparent.setIcon(QIcon("ICon/Frame.png"))
        pBtnTransparent.setIconSize(QSize(20, 20))
        pBtnTransparent.clicked.connect(self.set_pen_Transparent)

        # 设置“选择其他颜色”按钮功能
        othercolor_btn = QToolButton()
        othercolor_btn.setArrowType(Qt.NoArrow)
        othercolor_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        othercolor_btn.setFixedSize(218, 20)
        othercolor_btn.setAutoRaise(True)
        othercolor_btn.setIcon(QIcon("ICon/color.png"))
        othercolor_btn.setText(u"选择其他颜色")
        othercolor_btn.setIconSize(QSize(15, 15))
        othercolor_btn.setStyleSheet("QToolButton{font:bold 8pt '微软雅黑'}")
        othercolor_btn.clicked.connect(self.on_colorboard_show)

        # 将设置好的颜色框架，用QWidget包装好
        widget = QWidget()
        widget.setLayout(pGridLayout)
        bwidget = QWidget()
        bwidget.setLayout(bGridLayout)

        #  将上述设置的这些所有颜色框架，小组件窗口，用QVBoxLayout包装好
        pVLayout = QVBoxLayout()
        pVLayout.setSpacing(1)
        pVLayout.addWidget(title)
        pVLayout.addWidget(widget)
        pVLayout.addWidget(btitle)
        pVLayout.addWidget(bwidget)
        pVLayout.addWidget(line)
        pVLayout.addWidget(pBtnTransparent)
        pVLayout.addWidget(othercolor_btn)

        # 设置弹出菜单，菜单打上上述打包好所有颜色框架、窗口的pVLayout内容
        self.colorMenu = QMenu(self)
        self.colorMenu.setLayout(pVLayout)

        # 设置下拉框按钮菜单为上述菜单
        self.ColorCombox.setMenu(self.colorMenu)

        ### 将所有上述打包好的内，用本类设置的QWidget打包成窗口控件 ###
        alLayout = QVBoxLayout()
        alLayout.setSpacing(0)
        alLayout.addWidget(self.ColorCombox)
        self.setLayout(alLayout)

    ### ——以下为本类所用到的函数—— ###

    # 重设画笔粗细按钮按下后菜单出现在右侧
    def thickness_show(self, e):
        parent = self.colorMenu.pos()
        pos = self.thicknessbtn.geometry()
        m = self.thicknessmenu.geometry()
        w = pos.width()
        self.thicknessmenu.move(parent.x() + w + 16, m.y() - pos.height())

    # 重设画笔虚线按钮按下后菜单出现在右侧
    def style_show(self, e):
        parent = self.colorMenu.pos()
        pos = self.stylebtn.geometry()
        m = self.stylemenu.geometry()
        w = pos.width()
        self.stylemenu.move(parent.x() + w + 16, m.y() - pos.height())

    # 设置画笔粗细菜单栏中的所有Icon图标
    def set_width_Icon(self, width):
        color = Qt.black
        pix = QPixmap(100, width)
        pix.fill(QColor(color))
        return QIcon(pix)

    # 设置画笔粗细选中时的操作
    def OnWidthChanged(self):
        width = self.sender().data() + 1
        # print(width)
        self.thicknessmenu.close()
        self.colorMenu.close()
        self.thick_signal.emit(width)

    # 设置画笔虚线菜单栏中的所有Icon图标
    def set_style_Icon(self, style):
        # print(style)
        color = Qt.black
        pix = QPixmap(100, 6)
        pix.fill(Qt.white)
        painter = QPainter(pix)
        pp = QPen()
        pp.setStyle(style)
        pp.setColor(color)
        pp.setWidth(3)
        painter.setPen(pp)
        painter.drawLine(0, 3, 100, 3)
        painter.end()
        return QIcon(pix)

    # 设置画笔虚线形状选中时的操作
    def OnStyleChanged(self):
        style = self.sender().data()
        # print(Qt.PenStyle(style))
        self.stylemenu.close()
        self.colorMenu.close()
        self.style_signal.emit(style)

    # 用于设置QAction颜色块的槽函数
    def createColorIcon(self, color):
        pixmap = QPixmap(18, 18)
        pixmap.fill(QColor(color))
        return QIcon(pixmap)

    # 当透明色设置按钮按下后的槽函数
    def set_pen_Transparent(self):
        color = Qt.transparent
        self.colorMenu.close()
        self.signal.emit(color)

    # 设置颜色下拉按钮的自定义图标Icon，这里是颜色变化时改变图标下层矩形填充颜色
    def createColorToolButtonIcon(self, color):
        # print(color)
        qp = QPixmap(30, 30)
        qp.fill(Qt.transparent)
        self.pix = QPixmap()
        self.pix.load("ICon/filled.png")
        pixfix = self.pix.scaled(25, 25, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        target = QRect(0, 0, 25, 25)
        source = QRect(0, 0, 25, 25)
        painter = QPainter(qp)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(target, pixfix, source)
        painter.fillRect(QRect(0, 22, 24, 5), color)
        painter.end()
        self.ColorCombox.setIcon(QIcon(qp))
        self.ColorCombox.setIconSize(QSize(30, 40))

    # 当颜色色块QAction按下后的槽函数
    def OnColorChanged(self):
        color = self.sender().data()
        self.colorMenu.close()
        self.signal.emit(color)

    # 当其他颜色按钮按下时弹出Qt自带的颜色选择器
    def on_colorboard_show(self):
        color = QColorDialog.getColor(Qt.black, self)
        if color.isValid():
            self.signal.emit(color)
            return color


# 本案例是利用QtDesigner拉出的控件，然后赋予控件功能为自定义的本类功能 #
class ThicknessCombox(QWidget):
    thick_signal = pyqtSignal(object)
    style_signal = pyqtSignal(object)

    def __init__(self, parent):  # 利用传入QtDesigner创建好的控件，把他的名字用“parent”名义传进来，代替self
        super().__init__()
        # 本案例是利用QtDesigner拉出的控件，然后赋予控件功能为自定义的本类功能

        # self.ThicknessCombox = QToolButton()
        # self.ThicknessCombox.setPopupMode(QToolButton.InstantPopup)  # 设置下拉框按钮按下时弹出菜单窗口
        # self.ThicknessCombox.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # self.ThicknessCombox.setArrowType(Qt.NoArrow)
        # self.ThicknessCombox.setText("画笔形状")
        # self.ThicknessCombox.setIcon(QIcon("noun_line weight.png"))
        # # self.ThicknessCombox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # # self.ThinknessCombox.setMinimumSize(100, 30)
        # self.ThicknessCombox.setAutoFillBackground(True)
        # # 利用setStyleSheet设置QToolButton不显示下箭头
        # self.ThicknessCombox.setStyleSheet(
        #     "QToolButton::menu-indicator {image: none;} QToolButton{font:bold 9pt '微软雅黑'}")
        # self.ThicknessCombox.setIconSize(QSize(30, 30))

        pLayout = QVBoxLayout()
        # pGridLayout.setAlignment(Qt.AlignCenter)
        pLayout.setSpacing(0)
        for i in range(10):
            action = QAction()
            action.setData(i)
            action.setIcon(self.set_width_Icon(i + 1))
            action.setText("{}磅".format(i + 1))
            pBtnWidth = QToolButton()
            pBtnWidth.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            pBtnWidth.setIconSize(QSize(100, 10))
            pBtnWidth.setStyleSheet(
                "QToolButton::menu-indicator {image: none;}")

            pBtnWidth.setAutoRaise(True)
            pBtnWidth.setDefaultAction(action)
            action.triggered.connect(self.OnWidthChanged)
            pBtnWidth.setToolTip(str("粗细:{}磅".format(i + 1)))
            pLayout.addWidget(pBtnWidth, i)

        style = [Qt.NoPen, Qt.SolidLine, Qt.DashLine, Qt.DotLine,
                 Qt.DashDotLine, Qt.DashDotDotLine, Qt.CustomDashLine]
        name = ["无", "实线", "虚线", "点线", "点虚线", "点点虚线", "自定义"]

        sLayout = QVBoxLayout()
        sLayout.setSpacing(0)

        for j in range(7):
            saction = QAction()
            saction.setData(style[j])
            saction.setIcon(self.set_style_Icon(style[j]))
            saction.setText(name[j])
            sBtnStyle = QToolButton()
            sBtnStyle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            sBtnStyle.setIconSize(QSize(100, 10))
            sBtnStyle.setStyleSheet(
                "QToolButton::menu-indicator {image: none;}")
            sBtnStyle.setAutoRaise(True)
            sBtnStyle.setDefaultAction(saction)
            saction.triggered.connect(self.OnStyleChanged)
            sBtnStyle.setToolTip(name[j])
            sLayout.addWidget(sBtnStyle, j)

        widget = QWidget()
        widget.setLayout(pLayout)

        swidget = QWidget()
        swidget.setLayout(sLayout)

        pVLayout = QVBoxLayout()
        pVLayout.setSpacing(1)
        pVLayout.setContentsMargins(1, 1, 1, 1)
        pVLayout.addWidget(widget)

        sVLayout = QVBoxLayout()
        sVLayout.setSpacing(1)
        sVLayout.setContentsMargins(1, 1, 1, 1)
        sVLayout.addWidget(swidget)

        # 设置弹出菜单，菜单打上上述打包好所有颜色框架、窗口的pVLayout内容
        self.thicknessmenu = QMenu(self)
        thick = QMenu(self.thicknessmenu)
        thick.setTitle("粗细")
        thick.setIcon(QIcon('ICon/noun_line weight.png'))
        self.thicknessmenu.addMenu(thick)
        thick.setLayout(pVLayout)
        style = QMenu(self.thicknessmenu)
        style.setTitle("画笔样式")
        style.setIcon(QIcon('ICon/noun_line weight.png'))
        self.thicknessmenu.addMenu(style)
        style.setLayout(sVLayout)

        # 设置下拉框按钮菜单为上述菜单
        # self.ThicknessCombox.setMenu(self.thicknessmenu)

        ### 将所有上述打包好的内，用本类设置的QWidget打包成窗口控件 ###
        alLayout = QVBoxLayout()
        alLayout.setSpacing(0)
        parent.setMenu(self.thicknessmenu)
        parent.setPopupMode(QToolButton.InstantPopup)
        parent.setLayout(alLayout)
        parent.setStyleSheet(
            "QToolButton::menu-indicator {image: none;}")

    def set_width_Icon(self, width):
        color = Qt.black
        pix = QPixmap(100, width)
        pix.fill(QColor(color))
        return QIcon(pix)

    def set_style_Icon(self, style):
        color = Qt.black
        pix = QPixmap(100, 6)
        pix.fill(Qt.white)
        painter = QPainter(pix)
        pp = QPen()
        pp.setStyle(style)
        pp.setColor(color)
        pp.setWidth(3)
        painter.setPen(pp)
        painter.drawLine(0, 3, 100, 3)
        painter.end()
        return QIcon(pix)

    def OnWidthChanged(self):
        width = self.sender().data() + 1
        self.thicknessmenu.close()
        self.thick_signal.emit(width)

    def OnStyleChanged(self):
        style = self.sender().data()
        self.thicknessmenu.close()
        self.style_signal.emit(style)


class MyScene(QGraphicsScene):  # 自定场景
    itemClicked = pyqtSignal(object)
    itemScaled = pyqtSignal(object)
    itemAdded = pyqtSignal(QGraphicsScene, QGraphicsItem)
    itemMoved = pyqtSignal(object, QPointF)
    itemResized = pyqtSignal(object, object, object)
    itemRotated = pyqtSignal(QGraphicsItem, float)
    itemDeled = pyqtSignal(QGraphicsScene, QGraphicsItem)

    def __init__(self):  # 初始函数
        super(MyScene, self).__init__(parent=None)  # 实例化QGraphicsScene
        self.setSceneRect(0, 0, 900, 600)  # 设置场景起始及大小，默认场景是中心为起始，不方便后面的代码

    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.drawRect(0, 0, 900, 600)


class GraphicView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)  # 去除箭头类图元撤销重做残影
            self.scene = MyScene()  # 设置管理QgraphicsItems的场景
            self.shape = "move"  # 预设为鼠标而不是画笔
            self.Shape(self.shape)
            self.brush_color = Qt.transparent  # 预设画刷颜色为透明
            self.pen_color = Qt.red  # 预设笔的颜色
            self.pen_width = 2  # 预设笔的宽度
            self.pen_style = 1  # 预设笔迹为实线
            self.value = 1

            # 预设以下参数的值，以防画板打开第一时间操作导入图片后self.wx-self.x=None-None而出错
            self.x = 0
            self.y = 0
            self.wx = 0
            self.wy = 0

            self.a = None  # 初始化箭头类图元
            self.tempPath = None  # 初始化双缓冲绘图辅助路径

            self.setScene(self.scene)  # Qgraphicsview设置场景MyScene()
            self.setAcceptDrops(True)  # 设置可支持拖拽功能

            self.r_last = None
            self.item = None
            self.oldPos = []  # 用于记录所点击的Item的上一次位置信息
            self.ItemsSelected = []  # 用于记录所点击的Items的顺序
            self.handle = None  # 初始化所选Item的控制点为空

        except Exception as e:
            print(e)

    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()

    # 必须重写这个函数，不然dragMoveEvent中默认是event.ignore，导致dropEvent无法响应！！！
    def dragMoveEvent(self, event):
        """拖拽移动事件"""
        event.accept()

    def dragLeaveEvent(self, event):
        """拖拽离开事件"""
        event.ignore()

    def dropEvent(self, event):
        """拖拽后放置事件"""
        pos = event.pos()
        if event.mimeData().hasUrls():
            file = event.mimeData().urls()[0].toLocalFile()
            pixmap = QPixmap()
            pixmap.load(file)
            itemp = PItem_paste(pixmap, pos)
            itemp.updateCoordinate()
            itemp.moveBy(itemp.rect().width() / 2, itemp.rect().height() / 2)
            itemp.setPos(pos)
            self.scene.itemAdded.emit(self.scene, itemp)
        elif event.mimeData().hasImage():
            file = event.mimeData().imageData()
            pixmap = QPixmap()
            temp = pixmap.fromImage(file)
            itemp = PItem_paste(temp, pos)
            itemp.updateCoordinate()
            itemp.moveBy(itemp.rect().width() / 2, itemp.rect().height() / 2)
            itemp.setPos(pos)
            self.scene.itemAdded.emit(self.scene, itemp)

    def Shape(self, s):
        """返回画笔属性状态"""
        self.shape = s
        if self.shape == "move":
            self.viewport().unsetCursor()  # 注意：需要使用viewport().setCursor()而不是直接setCursor()，这样才能真正改变视觉上的鼠标形状
            self.setDragMode(QGraphicsView.RubberBandDrag)  # 设置为支持橡皮筋框选模式
        else:
            self.viewport().setCursor(Qt.CrossCursor)  # 注意：需要使用viewport().setCursor()而不是直接setCursor()，这样才能真正改变视觉上的鼠标形状
            self.setDragMode(QGraphicsView.NoDrag)  # 其他情况设置为不可拖拽模式
        return self.shape

    def ChangeBrushColor(self, color):
        """返回变更的填充颜色"""
        self.brush_color = QColor(color)
        return self.brush_color

    def ChangePenColor(self, color):
        """返回变更的画笔颜色"""
        self.pen_color = QColor(color)  # 当画笔颜色变化时，设置画笔颜色
        return self.pen_color

    def ChangePenThickness(self, thickness):
        """返回变更的画笔粗细"""
        self.pen_width = thickness  # 当画笔颜色变化时，设置画笔粗细

    def ChangePenStyle(self, style):
        """返回变更的画笔粗细"""
        self.pen_style = style  # 当画笔形状变化时，设置画笔形状

    def get_item_at_click(self, event):
        """ 返回鼠标位置所涉及的QgraphicsItem """
        pos = event.pos()  # 注意此时是Qgraphicsview的鼠标点击位置
        # x=self.graphicsView.mapFromParent(pos)
        # y=self.graphicsView.mapFromScene(pos)
        # z=self.graphicsView.mapFromGlobal(pos)
        # print(pos,x,y,z)
        # print(pos)
        item = self.itemAt(pos)
        return item

    def get_items_at_rubber(self):
        """ 返回选择区域内的Items"""
        area = self.graphicsView.rubberBandRect()
        return self.graphicsView.items(area)

    def remove_to_origin(self, item):
        """ 重置QgraphicsItem缩放比例和旋转角度为0"""
        item = item
        if item != None:
            item.setScale(1)
            item.setPos(item.x(), item.y())
            last = item.rotation()
            item.setRotation(0)
            self.scene.itemRotated.emit(item, last)
            self.value = 1
            self.scene.itemScaled.emit(self.value)

    def mousePressEvent(self, event):
        """重载鼠标按下事件"""
        super(GraphicView, self).mousePressEvent(event)  # 此重置句必须要有，目的是为了画完Item后Item可被选择

        try:
            self.lastPoint = event.pos()  # 记录鼠标在Qgraphicsview按下的位置点
            self.x = self.lastPoint.x()
            self.y = self.lastPoint.y()

            pos = event.pos()
            self.t = self.mapToScene(pos)  # 此句让在鼠标在Qgraphicsview按下的位置点投影到QgraphicScene上

            item = self.get_item_at_click(event)  # 记录鼠标掠过Item上的信息，若无Item，此函数返回None

            s_item = self.scene.selectedItems()  # 记录QgraphicScene上已选择的Items

            if s_item != []:
                self.r_degree = s_item[0].rotation()  # 记录鼠标点击的QgraphicsItem的初始旋转角度
                if isinstance(s_item[0], QGraphicsPathItem) or isinstance(s_item[0], QGraphicsItemGroup):
                    self.handle = None
                else:
                    self.handle = s_item[0].handleSelected  # 记录鼠标点击的QgraphicsItem当前所选择的控制点


            """触发鼠标左件事件"""
            if event.button() == Qt.LeftButton:
                if s_item != [] and len(s_item) == 1:  # 当鼠标点击Item数只有1个时...
                    self.oldPos.append(s_item[0].pos())
                elif s_item != [] and len(s_item) != 1:  # 当鼠标点击Item数有n个时...
                    for item in s_item:
                        self.ItemsSelected.append(item)
                        self.oldPos.append(item.pos())

                self.tempPath = QGraphicsPathItem()  # 设置一个内存上的QGraphicsPathItem，方便MouseMoveEvent画图时有双缓冲绘图效果
                self.tempPath.setFlags(QtWidgets.QGraphicsItem.ItemIsSelectable
                                       | QtWidgets.QGraphicsItem.ItemIsMovable
                                       | QtWidgets.QGraphicsItem.ItemIsFocusable
                                       | QtWidgets.QGraphicsItem.ItemSendsGeometryChanges
                                       | QtWidgets.QGraphicsItem.ItemSendsScenePositionChanges)

                self.path1 = QPainterPath()  # 实例路径函数，用于自由画笔风格
                self.path1.moveTo(pos)  # 设置路径开始点

                # 若选择形状为line，即箭头类图形时，初始化箭头图元
                if self.shape == "line":
                    self.a = ArrowItem(self.scene, self.pen_color, self.pen_width,
                                       self.pen_style)  # 设置实例化自定义的箭头类，但不传入起始点位置参数
                    self.a.set_src(self.x, self.y)  # 设置自定义箭头类的箭头线起始点

                # 千万不要再初始化__init__那里设置画笔Qpen，这里采用点击后的局部变量，不然笔颜色，大小无法修改
                pp = QPen()  # 实例QPen
                pp.setStyle(self.pen_style)
                pp.setColor(self.pen_color)  # 设置颜色
                pp.setWidth(self.pen_width)  # 设置宽度

                self.tempPath.setPen(pp)  # self.tempPath应用笔

            """此处主要用于能在其他图元上继续画图，不然图元有自身边界，画图时无法越过这些边界"""
            if self.shape != "move" and item != None:
                item.setSelected(False)
                item.setFlag(QGraphicsItem.ItemIsMovable, enabled=False)
                item.setFlag(QGraphicsItem.ItemIsSelectable, enabled=False)

        except Exception as e:
            print(e)

    def mouseMoveEvent(self, event):
        """重载鼠标移动事件"""
        super(GraphicView, self).mouseMoveEvent(event)  # 此重置句必须要有，目的是为了画完Item后Item可被移动，可放在MouseMoveEvent最后

        self.endPoint = event.pos()  # 记录鼠标移动时的点位置
        self.wx = self.endPoint.x()
        self.wy = self.endPoint.y()

        self.w = self.wx - self.x  # 用于绘画矩形Rect和Ellipse图形时的宽（长）
        self.h = self.wy - self.y  # 用于绘画矩形Rect和Ellipse图形时的高（宽）

        self.m = self.mapFromScene(event.pos())
        item = self.get_item_at_click(event)

        s_item = self.scene.selectedItems()
        condition = PItem.r_s(s_item)
        if condition != None and condition[0] == 1:  # 若Item选择的为控制点，且为旋转的控制点时...执行旋转操作
            PItem.r_e(s_item, self.r_degree, condition[2], condition[3], condition[1], self.t, self.m)

        elif s_item != [] and s_item[0].type() != 5:  # 若Item的type属性不为5，即不为图片图元时...
            self.other_condition = RectItem.item_based_info(s_item)
            other_condition = self.other_condition
            if other_condition != None and other_condition[0] == 0:  # 若Item选择的为控制点，且为旋转的控制点时...执行旋转操作
                RectItem.handle_rotation(s_item, self.r_degree, other_condition[2], other_condition[3],
                                         other_condition[1], self.t, self.m)

        if event.buttons() & Qt.LeftButton:  # 仅左键时触发，event.button返回notbutton，需event.buttons()判断，这应是对象列表，用&判断

            try:
                if self.shape == "circle":  # 圆形的item.type()=3
                    self.path2 = QPainterPath()  # 为了实现双缓冲的效果，另设一个QPainterPath
                    self.path2.addEllipse(self.t.x(), self.t.y(), self.w, self.h)  # 添加绘图路径
                    self.tempPath.setBrush(self.brush_color)
                    self.tempPath.setPath(self.path2)  # 由于self.path2是在内存上一直刷新，并销毁之前的绘图路径，此时tempath设置路径就能在绘图时有双缓冲效果
                    self.scene.addItem(self.tempPath)  # Myscene()场景中添加图元

                elif self.shape == "rect":  # 矩形的item.type()=3
                    self.path3 = QPainterPath()
                    self.path3.addRect(self.x, self.y, self.w, self.h)
                    self.tempPath.setBrush(self.brush_color)
                    self.tempPath.setPath(self.path3)
                    self.scene.addItem(self.tempPath)

                elif self.shape == "Free pen":  # 自由风格画笔绘图的图元item.type()==2
                    if self.path1:  # 即self.path1==True
                        self.path1.lineTo(event.pos())  # 移动并连接点
                        self.tempPath.setPath(self.path1)  # self.QGraphicsPath添加路径，如果写在上面的函数，是没线显示的，写在下面则在松键才出现线
                        self.scene.addItem(self.tempPath)

                elif self.shape == "line":  # 箭头类图元item.type()==2
                    self.a.set_dst(self.wx, self.wy)  # 更新箭头类线条的末端点位置
                    self.a.update()  # 自定义箭头类图元刷新，不然没有双缓冲绘图效果
                    self.scene.addItem(self.a)

                elif self.shape == "move":  # 设置当self.shape=="Move"时，不做其他附加操作
                    if item == None:
                        pass
                    else:
                        item.setFlag(QGraphicsItem.ItemIsSelectable, enabled=True)
                        item.setFlag(QGraphicsItem.ItemIsMovable, enabled=True)

            except Exception as e:
                print(e)
        # super().mouseMoveEvent(event)  # 该重置鼠标移动事件语句也可以写在这里

    def mouseReleaseEvent(self, event):
        """重载鼠标释放事件"""
        super().mouseReleaseEvent(event)  # 此重置句必须要有，目的是为了画完Item后Item，Item不会出现移动bug
        item = self.get_item_at_click(event)
        try:
            if self.shape == "rect":
                self.scene.removeItem(self.tempPath)
                self.tempPath.boundingRect()
                self.Q = QRectF(-self.tempPath.boundingRect().width() / 2, -self.tempPath.boundingRect().height() / 2,
                                self.tempPath.boundingRect().width(), self.tempPath.boundingRect().height())
                self.r_last = QPointF(self.tempPath.boundingRect().x() + self.tempPath.boundingRect().width() / 2,
                                      self.tempPath.boundingRect().y() + self.tempPath.boundingRect().height() / 2)
                self.r = RectItem(self.brush_color, self.pen_style, self.pen_color, self.pen_width, self.r_last, self.Q)
                self.r.moveBy(self.r_last.x(), self.r_last.y())
                self.scene.itemAdded.emit(self.scene, self.r)

            elif self.shape == "circle":
                self.scene.removeItem(self.tempPath)
                self.Q = QRectF(-self.tempPath.boundingRect().width() / 2, -self.tempPath.boundingRect().height() / 2,
                                self.tempPath.boundingRect().width(), self.tempPath.boundingRect().height())
                self.r_last = QPointF(self.tempPath.boundingRect().x() + self.tempPath.boundingRect().width() / 2,
                                      self.tempPath.boundingRect().y() + self.tempPath.boundingRect().height() / 2)
                self.e = EllipseItem(self.brush_color, self.pen_style, self.pen_color, self.pen_width, self.Q)
                self.e.moveBy(self.r_last.x(), self.r_last.y())
                self.scene.itemAdded.emit(self.scene, self.e)

            elif self.shape == "line" and self.a != None:
                self.a.setSelected(True)
                self.scene.itemAdded.emit(self.scene, self.a)

            elif self.shape == "Free pen" and self.tempPath != None:
                self.tempPath.setSelected(True)
                self.scene.itemAdded.emit(self.scene, self.tempPath)

            if self.shape != "Free pen":  # 当画笔是自由风格时，可保持继续画图
                self.shape = "move"
            self.Shape(self.shape)

            s_item = self.scene.selectedItems()
            if s_item != [] and self.oldPos != []:
                self.item = s_item[0]
                if len(s_item) == 1 and self.oldPos[
                    0] != self.item.pos() and self.shape == "move" and self.handle == None:
                    self.scene.itemMoved.emit(self.item, self.oldPos[0])
                elif len(s_item) != 1 and self.shape == "move" and self.handle == None:
                    for i, item in enumerate(self.ItemsSelected):
                        if self.oldPos[i] != self.item.pos():
                            self.scene.itemMoved.emit(item, self.oldPos[i])

            # 重置上一个位置和Item序列的记录列表
            self.oldPos = []
            self.ItemsSelected = []

        except Exception as e:
            print(e)
        # super().mouseReleaseEvent(event)  # 该重置鼠标移动事件语句也可以写在这里

    def wheelEvent(self, event):  # 可以利用鼠标滚轮进行Item的缩放或旋转，目前缩放后清晰度低，不太建议使用
        """ 重载鼠标滚轮事件"""
        try:
            item = self.scene.selectedItems()
            if len(item) >= 1:
                item = item[0]
            else:
                item = None
            if event.modifiers() == Qt.ControlModifier:
                cursorPoint = event.pos()
                scenePos = self.mapToScene(QPoint(cursorPoint.x(), cursorPoint.y()))
                viewWidth = self.viewport().width()
                viewHeight = self.viewport().height()
                hScale = cursorPoint.x() / viewWidth
                vScale = cursorPoint.y() / viewHeight
                scaleFactor = self.transform().m11()
                if event.angleDelta().y() > 0:
                    self.scale(1.2, 1.2)

                elif event.angleDelta().y() < 0:
                    self.scale(1.0 / 1.2, 1.0 / 1.2)
                viewPoint = self.transform().map(scenePos)
                self.horizontalScrollBar().setValue(int(viewPoint.x() - viewWidth * hScale))
                self.verticalScrollBar().setValue(int(viewPoint.y() - viewHeight * vScale))
            else:
                if item != None:
                    if event.angleDelta().y() > 0 and self.value >= 10:
                        self.value = 10
                    elif event.angleDelta().y() < 0 and self.value <= 0.2:
                        self.value = 0.2
                    else:
                        angle = event.angleDelta().y()
                        if angle > 0:
                            self.value += 0.1
                        else:  # 滚轮下滚
                            self.value -= 0.1
                        self.scene.itemScaled.emit(self.value)
                        item.setScale(self.value)
        except Exception as e:
            print(e)


#### 以下是重写一些QGraphicsItem的基类，以此实现可自由控制的矩形、圆形、箭头和可编辑的文本图元等 ####
class PItem_paste(QGraphicsRectItem):
    """ 导入图片可缩放的自定义图片类，实际是重写QGraphicsRectItem类"""
    handleTopLeft = 1
    handleTopMiddle = 2
    handleTopRight = 3
    handleMiddleLeft = 4
    handleMiddleRight = 5
    handleBottomLeft = 6
    handleBottomMiddle = 7
    handleBottomRight = 8

    handleSize = +10.0
    handleSpace = -4.0

    # 设置鼠标形状
    handleCursors = {
        handleTopLeft: Qt.SizeFDiagCursor,
        handleTopMiddle: Qt.SizeVerCursor,
        handleTopRight: Qt.SizeBDiagCursor,
        handleMiddleLeft: Qt.SizeHorCursor,
        handleMiddleRight: Qt.SizeHorCursor,
        handleBottomLeft: Qt.SizeBDiagCursor,
        handleBottomMiddle: Qt.SizeVerCursor,
        handleBottomRight: Qt.SizeFDiagCursor,
    }

    beginPosition = None
    endPosition = None
    isMousePressLeft = None
    originTailorRect = None
    pickRect = None

    def __init__(self, pic, point, *args):
        """初始化图形类基础信息"""
        super().__init__(*args)
        self.pix = pic  # 记录导入的图片存储路径
        # print("PItem_Paste:",self.pix.width(),self.pix.height(),self.rect())
        # print(self.pix.isNull())
        self.setSelected(True)

        self.tailor = False
        self.keepratio = False
        self.isDrag = False
        self.state = None
        self.setRect(0, 0, self.pix.width(), self.pix.height())

        self.setZValue(0)  # 使插入的图片在Myscene()的0层
        # self.pix = QPixmap(filename)  # 设置Pixmap为导入的图片

        self.handles = {}

        self.handleSelected = None
        self.mousePressPos = None
        self.mousePressRect = None

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)

        self.w = self.pix.width()
        self.h = self.pix.height()
        # self.pixfixed = self.pix.scaled(self.w, self.h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        # s_w = self.pixfixed.width()
        # s_h = self.pixfixed.height()
        # self.c = QRectF(0, 0, s_w, s_h)

        if self.w >= 600 or self.h >= 500:
            self.setRect(0, 0, self.w / self.h * (312 - 12), 312 - 12)
        self.updateHandlesPos()

        # self.setTransformOriginPoint(self.rect().center())
        self.oldRect = QRectF()
        self.oldAngle = None

    def type(self):
        type = 4  # 重写本次自定义图片类的Item.type()的值为4
        return type

    def handleAt(self, point):  # point为鼠标的点位置信息
        """返回自设定的小handle是否包含鼠标所在的点位置，若是，则返回鼠标在第几个handle上"""
        for k, v, in self.handles.items():  # k为数值1~8，辨别是handleTopLeft=1还是其他；v则是返回小handle的QRectF
            if v.contains(point):
                return k
        return None

    def hoverMoveEvent(self, moveEvent):
        """执行鼠标在图片上移动的事件（非鼠标点击事件）"""
        if self.isSelected():
            handle = self.handleAt(moveEvent.pos())
            if handle is None:
                cursor = Qt.SizeAllCursor
            elif handle == 1:
                pm = QPixmap("rotate_icon.ico")
                pm = pm.scaled(30, 30)
                cursor = QCursor(pm)
            else:
                cursor = self.handleCursors[handle]
            self.setCursor(cursor)
        else:
            cursor = Qt.SizeAllCursor
            self.setCursor(cursor)
        super().hoverMoveEvent(moveEvent)

    def hoverLeaveEvent(self, moveEvent):
        """执行鼠标移动到图片外边的事件（非鼠标点击事件）"""
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(moveEvent)

    def mousePressEvent(self, mouseEvent):
        """执行鼠标在图片上点击事件"""
        self.oldRect = self.rect()
        self.oldAngle = self.rotation()
        self.scene().itemClicked.emit(self)
        self.handleSelected = self.handleAt(mouseEvent.pos())
        if self.isSelected():
            self.beginPosition = mouseEvent.pos()
            if self.tailor == True:
                self.originTailorRect = self.rect()

        if self.handleSelected:
            if mouseEvent.button() == Qt.LeftButton:
                self.isDrag = True
            self.mousePressPos = mouseEvent.pos()
            self.mousePressRect = self.boundingRect()  # 返回点击的Rect的boundingRect虚函数
        super().mousePressEvent(mouseEvent)

    def mouseMoveEvent(self, mouseEvent):
        """执行鼠标在图片上点击后按住鼠标移动的事件"""
        if self.handleSelected is not None:
            self.interactiveResize(mouseEvent.pos())  # 此句鼠标点击图片并移动时返回None值
        elif self.tailor == True:
            self.isMousePressLeft = True
            self.endPosition = mouseEvent.pos()
        else:
            super().mouseMoveEvent(mouseEvent)

    def mouseReleaseEvent(self, mouseEvent):
        """执行鼠标在图片上释放事件"""
        super().mouseReleaseEvent(mouseEvent)
        # 重设以下参数
        if self.handleSelected != None:
            # print(self.handleSelected)
            if self.handleSelected != 1:
                pointO = self.mapToScene(self.oldRect.center())
                pointC = self.mapToScene(self.rect().center())
                self.delta = pointO - pointC
                self.updateCoordinate()
                self.scene().itemResized.emit(self, self.oldRect, self.delta)
            else:
                self.scene().itemRotated.emit(self, self.oldAngle)

        self.handleSelected = None
        self.mousePressPos = None
        self.mousePressRect = None
        self.update()
        self.isDrag = False
        self.state = None
        # self.isMousePressLeft = False

    def updateCoordinate(self):
        """图形大小变化时更新图元的坐标原点（旋转中心）"""
        self.prepareGeometryChange()
        pointO = self.mapToScene(self.oldRect.center())
        pointC = self.mapToScene(self.rect().center())
        self.delta = pointO - pointC
        w = self.rect().width()
        h = self.rect().height()
        self.m_localRect = QRectF(-w / 2, -h / 2, w, h)
        self.setRect(self.m_localRect)
        self.setTransformOriginPoint(self.m_localRect.center())
        # self.moveBy(-self.delta.x(), -self.delta.y())

    def boundingRect(self):
        """返回图形的boundingRect，其中包含resize handles的boundingRect"""
        o = self.handleSize + self.handleSpace
        return self.rect().adjusted(-o, -o, o, o)

    def updateHandlesPos(self):
        """基于图形的形状尺寸和位置，更新现有的resize handles位置"""
        s = self.handleSize
        b = self.boundingRect()
        o = self.handleSize + self.handleSpace
        r = self.rect().adjusted(-o, -o, o, o)

        self.handles[self.handleTopLeft] = QRectF(r.left(), r.top(), s, s)
        self.handles[self.handleTopMiddle] = QRectF(r.center().x() - s / 2, r.top(), s, s)
        self.handles[self.handleTopRight] = QRectF(r.right() - s, r.top(), s, s)
        self.handles[self.handleMiddleLeft] = QRectF(r.left(), r.center().y() - s / 2, s, s)
        self.handles[self.handleMiddleRight] = QRectF(r.right() - s, r.center().y() - s / 2, s, s)
        self.handles[self.handleBottomLeft] = QRectF(r.left(), r.bottom() - s, s, s)
        self.handles[self.handleBottomMiddle] = QRectF(r.center().x() - s / 2, r.bottom() - s, s, s)
        self.handles[self.handleBottomRight] = QRectF(r.right() - s, r.bottom() - s, s, s)

    def interactiveResize(self, mousePos):
        """用于交互式的矩形变换，如重设点位置"""
        offset = self.handleSize + self.handleSpace
        boundingRect = self.boundingRect()
        rect = self.rect()
        self.c = self.rect()
        self.state = 0
        diff = QPointF(0, 0)

        self.prepareGeometryChange()

        # if self.handleSelected == self.handleTopLeft:
        #
        #     fromX = self.mousePressRect.left()
        #     fromY = self.mousePressRect.top()
        #     toX = fromX + mousePos.x() - self.mousePressPos.x()
        #     toY = fromY + mousePos.y() - self.mousePressPos.y()
        #     diff.setX(toX - fromX)
        #     diff.setY(toY - fromY)
        #     boundingRect.setLeft(toX)
        #     boundingRect.setTop(toY)
        #     rect.setLeft(boundingRect.left() + offset)
        #     rect.setTop(boundingRect.top() + offset)
        #     self.setRect(rect)
        #     self.state = 0

        if self.handleSelected == self.handleTopMiddle:

            fromY = self.mousePressRect.top()
            toY = fromY + mousePos.y() - self.mousePressPos.y()
            diff.setY(toY - fromY)
            boundingRect.setTop(toY)
            rect.setTop(boundingRect.top() + offset)
            self.setRect(rect)

        elif self.handleSelected == self.handleTopRight:

            fromX = self.mousePressRect.right()
            fromY = self.mousePressRect.top()
            toX = fromX + mousePos.x() - self.mousePressPos.x()
            toY = fromY + mousePos.y() - self.mousePressPos.y()
            diff.setX(toX - fromX)
            diff.setY(toY - fromY)
            boundingRect.setRight(toX)
            boundingRect.setTop(toY)
            rect.setRight(boundingRect.right() - offset)
            rect.setTop(boundingRect.top() + offset)
            self.setRect(rect)

        elif self.handleSelected == self.handleMiddleLeft:

            fromX = self.mousePressRect.left()
            toX = fromX + mousePos.x() - self.mousePressPos.x()
            diff.setX(toX - fromX)
            boundingRect.setLeft(toX)
            rect.setLeft(boundingRect.left() + offset)
            self.setRect(rect)

        elif self.handleSelected == self.handleMiddleRight:

            fromX = self.mousePressRect.right()
            toX = fromX + mousePos.x() - self.mousePressPos.x()
            diff.setX(toX - fromX)
            boundingRect.setRight(toX)
            rect.setRight(boundingRect.right() - offset)
            self.setRect(rect)

        elif self.handleSelected == self.handleBottomLeft:

            fromX = self.mousePressRect.left()
            fromY = self.mousePressRect.bottom()
            toX = fromX + mousePos.x() - self.mousePressPos.x()
            toY = fromY + mousePos.y() - self.mousePressPos.y()
            diff.setX(toX - fromX)
            diff.setY(toY - fromY)
            boundingRect.setLeft(toX)
            boundingRect.setBottom(toY)
            rect.setLeft(boundingRect.left() + offset)
            rect.setBottom(boundingRect.bottom() - offset)
            self.setRect(rect)

        elif self.handleSelected == self.handleBottomMiddle:

            fromY = self.mousePressRect.bottom()
            toY = fromY + mousePos.y() - self.mousePressPos.y()
            diff.setY(toY - fromY)
            boundingRect.setBottom(toY)
            rect.setBottom(boundingRect.bottom() - offset)
            self.setRect(rect)

        elif self.handleSelected == self.handleBottomRight:

            fromX = self.mousePressRect.right()
            fromY = self.mousePressRect.bottom()
            toX = fromX + mousePos.x() - self.mousePressPos.x()
            toY = fromY + mousePos.y() - self.mousePressPos.y()
            diff.setX(toX - fromX)
            diff.setY(toY - fromY)
            boundingRect.setRight(toX)
            boundingRect.setBottom(toY)
            rect.setRight(boundingRect.right() - offset)
            rect.setBottom(boundingRect.bottom() - offset)
            self.setRect(rect)

        self.updateHandlesPos()

    def shape(self):
        """返回Item的shape形状，并在local coordinates添加到QPainterPath上"""
        path = QPainterPath()
        path.addRect(self.rect())
        if self.isSelected():  # 当该自定义图形类被选中时
            for shape in self.handles.values():  # 在每个handles点上加上小圆圈
                path.addEllipse(shape)
        return path

    def getRectangle(self, beginPoint, endPoint):
        # print(beginPoint, endPoint)
        pickRectWidth = int(qAbs(beginPoint.x() - endPoint.x()))
        pickRectHeight = int(qAbs(beginPoint.y() - endPoint.y()))
        pickRectTop = beginPoint.x() if beginPoint.x() < endPoint.x() else endPoint.x()
        pickRectLeft = beginPoint.y() if beginPoint.y() < endPoint.y() else endPoint.y()
        # print(pickRectTop,pickRectLeft,self.rect())
        pickRect = QRect(pickRectTop, pickRectLeft, pickRectWidth, pickRectHeight)
        # 避免高度宽度为0时候报错
        if pickRectWidth == 0:
            pickRect.setWidth(2)
        if pickRectHeight == 0:
            pickRect.setHeight(2)

        # 这里由于矩形控制点操作后，Pixmap的坐标原点会发生改变，因此Pixmap复制前，它的坐标也要对应改变，这样copy出来的坐标才能对应上
        self.pickRect1 = QRect(pickRectTop - self.rect().x(), pickRectLeft - self.rect().y(), pickRectWidth,
                               pickRectHeight)  # 用于后续Pixmap.copy()
        return pickRect

    def paint(self, painter, option, widget=None):
        """在Qgraphicview上绘制边框的选择小圆圈"""
        if self.isSelected():
            self.scene().itemClicked.emit(self)

        self.point = QPointF(0, 0)  # 插入的图片的左上角位置
        self.w = self.rect().width()
        self.h = self.rect().height()

        if self.pix.isNull():
            return None
        else:
            if self.keepratio == True and self.isDrag == True:
                self.pixfixed = self.pix.scaled(self.w, self.h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                self.setRect(self.rect().topLeft().x(), self.rect().topLeft().y(), self.pixfixed.width(),
                             self.pixfixed.height())

            elif self.keepratio == False and self.isDrag == True:
                self.pixfixed = self.pix.scaled(self.w, self.h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

            elif self.tailor == True:
                # print("ratio3:裁剪拉伸")
                self.pixfixed = self.pix.scaled(self.w, self.h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

            else:
                # print("ratio4:其他拉伸")
                self.pixfixed = self.pix.scaled(self.w, self.h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

            if self.state == 0 and self.tailor == False and self.originTailorRect == None:
                # print("Case1:图片拉伸",self.tailor)
                self.point = QPointF(self.rect().topLeft().x(), self.rect().topLeft().y())
                self.ot = QRectF(0, 0, self.rect().width(), self.rect().height())
                painter.drawPixmap(self.point, self.pixfixed, self.ot)

            elif self.tailor == True:
                # print("Case2:裁剪开始",self.tailor)
                shadowColor = QColor(0, 0, 0, 100)  # 黑色半透明
                oa = QPoint(self.rect().topLeft().x(), self.rect().topLeft().y())
                ob = QRectF(0, 0, self.rect().width(), self.rect().height())
                painter.drawPixmap(oa, self.pixfixed, ob)
                painter.fillRect(self.rect(), shadowColor)
                if self.isMousePressLeft == True:
                    # print("PItem-paint:",self.beginPosition, self.endPosition)
                    self.pickRect = self.getRectangle(self.beginPosition, self.endPosition)  # 获得要截图的矩形框
                    # print(self.pixfixed.rect(),self.pickRect,self.rect())
                    self.captureImage = self.pixfixed.copy(self.pickRect1)  # 捕获截图矩形框内的图片
                    # self.captureImage.save("captureImage.png")
                    painter.drawPixmap(self.pickRect.topLeft(), self.captureImage)  # 填充截图的图片
                    painter.setPen(QPen(QColor(0, 0, 255, 255), 2, Qt.SolidLine))
                    painter.drawRect(self.pickRect)  # 画矩形边框


            elif self.tailor == False and self.isMousePressLeft == True and self.state == None:
                # print("Case3:裁剪结束",self.state)
                painter.drawPixmap(self.pickRect.topLeft(), self.captureImage)
                self.setRect(self.pickRect.x(), self.pickRect.y(), self.pickRect.width(), self.pickRect.height())

            elif self.tailor == False and self.state != None:
                # print("Case3x:裁剪结束")
                tempRect = QRect(self.rect().x(), self.rect().y(), self.rect().width(), self.rect().height())
                tempPixmap = self.pixfixed
                painter.drawPixmap(self.rect().topLeft(), tempPixmap)
                self.pickRect = tempRect
                self.captureImage = tempPixmap

            else:
                # print("Case4:其他",self.tailor)
                self.point = QPointF(self.rect().topLeft().x(), self.rect().topLeft().y())
                self.ot = QRectF(0, 0, self.rect().width(), self.rect().height())
                painter.drawPixmap(self.point, self.pixfixed, self.ot)

            self.updateHandlesPos()

        if self.isSelected():
            painter.setPen(QPen(QColor(150, 150, 150, 255), 0.5, Qt.SolidLine))
            painter.drawRect(self.boundingRect().adjusted(6, 6, -7, -7))

            painter.setRenderHint(QPainter.HighQualityAntialiasing)
            painter.setRenderHint(QPainter.Antialiasing)
            # painter.setBrush(QBrush(QColor(255, 0, 0, 255)))
            painter.setPen(QPen(QColor(0, 0, 0, 255), 1.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            for i, shape in enumerate(self.handles.values()):
                if self.isSelected():
                    if i == 0:
                        painter.setBrush(QBrush(QColor(Qt.blue)))
                        painter.drawRect(shape)
                    else:
                        painter.setBrush(QBrush(QColor(Qt.red)))
                        painter.drawEllipse(shape)


class PItem(QGraphicsRectItem):
    """ 导入图片可缩放的自定义图片类，实际是重写QGraphicsRectItem类"""
    handleTopLeft = 1
    handleTopMiddle = 2
    handleTopRight = 3
    handleMiddleLeft = 4
    handleMiddleRight = 5
    handleBottomLeft = 6
    handleBottomMiddle = 7
    handleBottomRight = 8

    handleSize = +10.0
    handleSpace = -4.0

    # 设置鼠标形状
    handleCursors = {
        handleTopLeft: Qt.SizeFDiagCursor,
        handleTopMiddle: Qt.SizeVerCursor,
        handleTopRight: Qt.SizeBDiagCursor,
        handleMiddleLeft: Qt.SizeHorCursor,
        handleMiddleRight: Qt.SizeHorCursor,
        handleBottomLeft: Qt.SizeBDiagCursor,
        handleBottomMiddle: Qt.SizeVerCursor,
        handleBottomRight: Qt.SizeFDiagCursor,
    }

    beginPosition = None
    endPosition = None
    isMousePressLeft = None
    originTailorRect = None
    lastpickRectPoint = None
    pickRect = None

    def __init__(self, filename, *args):
        """初始化图形类基础信息"""
        super().__init__(*args)
        self.filename = filename  # 记录导入的图片存储路径

        self.pix = QPixmap(filename)  # 设置Pixmap为导入的图片
        self.o_w = self.pix.width()
        self.o_h = self.pix.height()
        self.setRect(0, 0, self.pix.width(), self.pix.height())

        self.tailor = False
        self.keepratio = False
        self.isDrag = False
        self.state = None
        self.other_pix = None
        self.setZValue(-0.1)  # 使插入的图片在Myscene()的-1层

        self.handles = {}

        self.handleSelected = None
        self.mousePressPos = None
        self.mousePressRect = None

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)

        # self.w = self.rect().width()
        # self.h = self.rect().height()
        # self.pixfixed = self.pix.scaled(self.w, self.h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        # s_w = self.pixfixed.width()
        # s_h = self.pixfixed.height()

        # if self.o_w <= 900 or self.o_h <= 600:
        # self.setRect(0, 0, s_w, s_h)
        # self.c = QRectF(0, 0, s_w, s_h)
        # elif self.o_w >= 900 or self.o_h >= 600:
        # self.setRect(0, 0, s_w, 600)
        # self.c = QRectF(0, 0, s_w, 600)

        self.updateHandlesPos()
        self.setSelected(True)
        self.oldRect = QRectF()
        self.oldAngle = None
        # self.updateCoordinate()

    # def keyPressEvent(self, event):
    # if event.modifiers() == Qt.ShiftModifier:
    # self.keepratio = True
    # else:
    # self.keepratio = False
    # if event.key() == Qt.Key_Delete:
    # MyScene().removeItem(self)
    # elif event.key() == Qt.Key_Up:
    # self.moveBy(0, -1)
    # elif event.key() == Qt.Key_Down:
    # self.moveBy(0, 1)
    # elif event.key() == Qt.Key_Right:
    # self.moveBy(1, 0)
    # elif event.key() == Qt.Key_Left:
    # self.moveBy(-1, 0)

    def keyReleaseEvent(self, event):
        self.keepratio = False

    def type(self):
        type = 4  # 重写本次自定义图片类的Item.type()的值为4
        return type

    def handleAt(self, point):  # point为鼠标的点位置信息
        """返回自设定的小handle是否包含鼠标所在的点位置，若是，则返回鼠标在第几个handle上"""
        for k, v, in self.handles.items():  # k为数值1~8，辨别是handleTopLeft=1还是其他；v则是返回小handle的QRectF
            if v.contains(point):
                return k
        return None

    def hoverMoveEvent(self, moveEvent):
        """执行鼠标在图片上移动的事件（非鼠标点击事件）"""
        if self.isSelected():
            handle = self.handleAt(moveEvent.pos())
            if handle is None:
                cursor = Qt.SizeAllCursor
            elif handle == 1:
                pm = QPixmap("rotate_icon.ico")
                pm = pm.scaled(30, 30)
                cursor = QCursor(pm)
            else:
                cursor = self.handleCursors[handle]
            self.setCursor(cursor)
        else:
            cursor = Qt.SizeAllCursor
            self.setCursor(cursor)
        super().hoverMoveEvent(moveEvent)

    def hoverLeaveEvent(self, moveEvent):
        """执行鼠标移动到图片外边的事件（非鼠标点击事件）"""
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(moveEvent)

    def r_s(self):
        try:
            if self != [] and self[0].type() == 4:
                # print(self[0].type())
                hand_selected = self[0].handleSelected
                x = self[0].x()
                y = self[0].y()
                rr = self[0].rotation()
                # self[0].setTransformOriginPoint(self[0].rect().topLeft().x() +self[0].rect().width() / 2, self[0].rect().topLeft().y()+self[0].rect().height() / 2)
                o = QPointF(self[0].rect().topLeft().x() + self[0].rect().width() / 2,
                            self[0].rect().topLeft().y() + self[0].rect().height() / 2)
                return hand_selected, o, x, y, rr

        except Exception as e:
            print(e)

    def r_e(self, rr, x, y, origin, start, end):
        if self != []:
            # p2 = QPointF(origin.x(), origin.y())
            # print(p2,"p2")
            # self[0].setTransformOriginPoint(p2)
            o = QPointF(origin.x() + x, origin.y() + y)
            v1 = start - o
            v2 = end - o
            angle = math.atan2(v2.y(), v2.x()) - math.atan2(v1.y(), v1.x())
            angle = int(angle * 180 / math.pi)
            angle = angle + rr
            self[0].setRotation(angle)

    def mousePressEvent(self, mouseEvent):
        """执行鼠标在图片上点击事件"""
        self.oldRect = self.rect()
        self.oldAngle = self.rotation()
        self.scene().itemClicked.emit(self)

        if self.isSelected():
            self.beginPosition = mouseEvent.pos()
            if self.tailor == True:
                self.originTailorRect = self.rect()

        self.handleSelected = self.handleAt(mouseEvent.pos())
        if self.handleSelected:
            if mouseEvent.button() == Qt.LeftButton:
                self.isDrag = True
            self.mousePressPos = mouseEvent.pos()
            self.mousePressRect = self.boundingRect()  # 返回点击的Rect的boundingRect虚函数
        super().mousePressEvent(mouseEvent)

    def mouseMoveEvent(self, mouseEvent):
        """执行鼠标在图片上点击后按住鼠标移动的事件"""
        if self.handleSelected is not None:
            self.interactiveResize(mouseEvent.pos())  # 此句鼠标点击图片并移动时返回None值
        elif self.tailor == True:
            self.isMousePressLeft = True
            self.endPosition = mouseEvent.pos()
        else:
            super().mouseMoveEvent(mouseEvent)

    def mouseReleaseEvent(self, mouseEvent):
        """执行鼠标在图片上释放事件"""
        super().mouseReleaseEvent(mouseEvent)
        # 重设以下参数
        if self.handleSelected != None:
            if self.handleSelected != 1:
                pointO = self.mapToScene(self.oldRect.center())
                pointC = self.mapToScene(self.rect().center())
                self.delta = pointO - pointC
                self.updateCoordinate()
                self.scene().itemResized.emit(self, self.oldRect, self.delta)

            else:
                self.scene().itemRotated.emit(self, self.oldAngle)

        self.handleSelected = None
        self.mousePressPos = None
        self.mousePressRect = None
        self.update()
        self.isDrag = False
        self.state = None
        # self.isMousePressLeft = False

    def updateCoordinate(self):
        """图形大小变化时更新图元的坐标原点（旋转中心）"""
        self.prepareGeometryChange()
        pointO = self.mapToScene(self.oldRect.center())
        pointC = self.mapToScene(self.rect().center())
        self.delta = pointO - pointC
        w = self.rect().width()
        h = self.rect().height()
        self.m_localRect = QRectF(-w / 2, -h / 2, w, h)
        self.setRect(self.m_localRect)
        self.setTransformOriginPoint(self.m_localRect.center())
        # self.moveBy(-self.delta.x(), -self.delta.y())

    def boundingRect(self):
        """返回图形的boundingRect，其中包含resize handles的boundingRect"""
        o = self.handleSize + self.handleSpace
        return self.rect().adjusted(-o, -o, o, o)

    def updateHandlesPos(self):
        """基于图形的形状尺寸和位置，更新现有的resize handles位置"""
        s = self.handleSize
        b = self.boundingRect()
        o = self.handleSize + self.handleSpace
        r = self.rect().adjusted(-o, -o, o, o)

        self.handles[self.handleTopLeft] = QRectF(r.left(), r.top(), s, s)
        self.handles[self.handleTopMiddle] = QRectF(r.center().x() - s / 2, r.top(), s, s)
        self.handles[self.handleTopRight] = QRectF(r.right() - s, r.top(), s, s)
        self.handles[self.handleMiddleLeft] = QRectF(r.left(), r.center().y() - s / 2, s, s)
        self.handles[self.handleMiddleRight] = QRectF(r.right() - s, r.center().y() - s / 2, s, s)
        self.handles[self.handleBottomLeft] = QRectF(r.left(), r.bottom() - s, s, s)
        self.handles[self.handleBottomMiddle] = QRectF(r.center().x() - s / 2, r.bottom() - s, s, s)
        self.handles[self.handleBottomRight] = QRectF(r.right() - s, r.bottom() - s, s, s)

    def interactiveResize(self, mousePos):
        """用于交互式的矩形变换，如重设点位置"""
        offset = self.handleSize + self.handleSpace
        boundingRect = self.boundingRect()
        rect = self.rect()
        self.c = self.rect()
        diff = QPointF(0, 0)
        self.state = 0

        self.prepareGeometryChange()

        # if self.handleSelected == self.handleTopLeft:
        #
        #     fromX = self.mousePressRect.left()
        #     fromY = self.mousePressRect.top()
        #     toX = fromX + mousePos.x() - self.mousePressPos.x()
        #     toY = fromY + mousePos.y() - self.mousePressPos.y()
        #     diff.setX(toX - fromX)
        #     diff.setY(toY - fromY)
        #     boundingRect.setLeft(toX)
        #     boundingRect.setTop(toY)
        #     rect.setLeft(boundingRect.left() + offset)
        #     rect.setTop(boundingRect.top() + offset)
        #     self.setRect(rect)

        if self.handleSelected == self.handleTopMiddle:

            fromY = self.mousePressRect.top()
            toY = fromY + mousePos.y() - self.mousePressPos.y()
            diff.setY(toY - fromY)
            boundingRect.setTop(toY)
            rect.setTop(boundingRect.top() + offset)
            self.setRect(rect)

        elif self.handleSelected == self.handleTopRight:

            fromX = self.mousePressRect.right()
            fromY = self.mousePressRect.top()
            toX = fromX + mousePos.x() - self.mousePressPos.x()
            toY = fromY + mousePos.y() - self.mousePressPos.y()
            diff.setX(toX - fromX)
            diff.setY(toY - fromY)
            boundingRect.setRight(toX)
            boundingRect.setTop(toY)
            rect.setRight(boundingRect.right() - offset)
            rect.setTop(boundingRect.top() + offset)
            self.setRect(rect)

        elif self.handleSelected == self.handleMiddleLeft:

            fromX = self.mousePressRect.left()
            toX = fromX + mousePos.x() - self.mousePressPos.x()
            diff.setX(toX - fromX)
            boundingRect.setLeft(toX)
            rect.setLeft(boundingRect.left() + offset)
            self.setRect(rect)

        elif self.handleSelected == self.handleMiddleRight:

            fromX = self.mousePressRect.right()
            toX = fromX + mousePos.x() - self.mousePressPos.x()
            diff.setX(toX - fromX)
            boundingRect.setRight(toX)
            rect.setRight(boundingRect.right() - offset)
            self.setRect(rect)

        elif self.handleSelected == self.handleBottomLeft:

            fromX = self.mousePressRect.left()
            fromY = self.mousePressRect.bottom()
            toX = fromX + mousePos.x() - self.mousePressPos.x()
            toY = fromY + mousePos.y() - self.mousePressPos.y()
            diff.setX(toX - fromX)
            diff.setY(toY - fromY)
            boundingRect.setLeft(toX)
            boundingRect.setBottom(toY)
            rect.setLeft(boundingRect.left() + offset)
            rect.setBottom(boundingRect.bottom() - offset)
            self.setRect(rect)

        elif self.handleSelected == self.handleBottomMiddle:

            fromY = self.mousePressRect.bottom()
            toY = fromY + mousePos.y() - self.mousePressPos.y()
            diff.setY(toY - fromY)
            boundingRect.setBottom(toY)
            rect.setBottom(boundingRect.bottom() - offset)
            self.setRect(rect)

        elif self.handleSelected == self.handleBottomRight:

            fromX = self.mousePressRect.right()
            fromY = self.mousePressRect.bottom()
            toX = fromX + mousePos.x() - self.mousePressPos.x()
            toY = fromY + mousePos.y() - self.mousePressPos.y()
            diff.setX(toX - fromX)
            diff.setY(toY - fromY)
            boundingRect.setRight(toX)
            boundingRect.setBottom(toY)
            rect.setRight(boundingRect.right() - offset)
            rect.setBottom(boundingRect.bottom() - offset)
            self.setRect(rect)

        self.updateHandlesPos()

    def shape(self):
        """返回Item的shape形状，并在local coordinates添加到QPainterPath上"""
        path = QPainterPath()
        path.addRect(self.rect())
        if self.isSelected():  # 当该自定义图形类被选中时
            for shape in self.handles.values():  # 在每个handles点上加上小圆圈
                path.addEllipse(shape)
        return path

    def getRectangle(self, beginPoint, endPoint):
        # print(beginPoint, endPoint)
        pickRectWidth = int(qAbs(beginPoint.x() - endPoint.x()))
        pickRectHeight = int(qAbs(beginPoint.y() - endPoint.y()))
        pickRectTop = beginPoint.x() if beginPoint.x() < endPoint.x() else endPoint.x()
        pickRectLeft = beginPoint.y() if beginPoint.y() < endPoint.y() else endPoint.y()
        # print(pickRectTop,pickRectLeft,self.rect())
        pickRect = QRect(pickRectTop, pickRectLeft, pickRectWidth, pickRectHeight)
        # 避免高度宽度为0时候报错
        if pickRectWidth == 0:
            pickRect.setWidth(2)
        if pickRectHeight == 0:
            pickRect.setHeight(2)

        # 这里由于矩形控制点操作后，Pixmap的坐标原点会发生改变，因此Pixmap复制前，它的坐标也要对应改变，这样copy出来的坐标才能对应上
        self.pickRect1 = QRect(pickRectTop - self.rect().x(), pickRectLeft - self.rect().y(), pickRectWidth,
                               pickRectHeight)  # 用于后续Pixmap.copy()
        self.lastpickRectPoint = QPoint(self.pickRect1.x(), self.pickRect1.y())
        return pickRect

    def paint(self, painter, option, widget=None):
        """在Qgraphicview上绘制边框的选择小圆圈"""
        self.point = QPointF(0, 0)  # 插入的图片的左上角位置
        painter.setRenderHint(QPainter.HighQualityAntialiasing)
        # print("PItem-paint:", self.state,self.handleSelected)
        self.w = self.rect().width()
        self.h = self.rect().height()

        if self.keepratio == True and self.isDrag == True:
            # print("ratio1:等比例拉伸")
            self.pixfixed = self.pix.scaled(self.w, self.h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setRect(self.rect().topLeft().x(), self.rect().topLeft().y(), self.pixfixed.width(),
                         self.pixfixed.height())

        elif self.keepratio == False and self.isDrag == True:
            # print("ratio2:任意拉伸")
            self.pixfixed = self.pix.scaled(self.w, self.h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

        elif self.tailor == True:
            # print("ratio3:裁剪拉伸")
            self.pixfixed = self.pix.scaled(self.w, self.h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

        else:
            # print("ratio4:其他拉伸")
            self.pixfixed = self.pix.scaled(self.w, self.h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

        if self.state == 0 and self.tailor == False and self.originTailorRect == None:
            # print("Case1:图片拉伸")
            self.point = QPointF(self.rect().topLeft().x(), self.rect().topLeft().y())
            self.ot = QRectF(0, 0, self.rect().width(), self.rect().height())
            painter.drawPixmap(self.point, self.pixfixed, self.ot)

        elif self.tailor == True:
            # print("Case2:裁剪开始")
            shadowColor = QColor(0, 0, 0, 100)  # 黑色半透明
            oa = QPoint(self.rect().topLeft().x(), self.rect().topLeft().y())
            ob = QRectF(0, 0, self.rect().width(), self.rect().height())
            painter.drawPixmap(oa, self.pixfixed, ob)
            painter.fillRect(self.rect(), shadowColor)
            if self.isMousePressLeft == True:
                # print("PItem-paint:",self.beginPosition, self.endPosition)
                self.pickRect = self.getRectangle(self.beginPosition, self.endPosition)  # 获得要截图的矩形框
                # print(self.pixfixed.rect(),self.pickRect,self.rect())
                self.captureImage = self.pixfixed.copy(self.pickRect1)  # 捕获截图矩形框内的图片
                painter.drawPixmap(self.pickRect.topLeft(), self.captureImage)  # 填充截图的图片
                painter.setPen(QPen(QColor(0, 0, 255, 255), 1.5, Qt.SolidLine))
                painter.drawRect(self.pickRect)  # 画矩形边框

        elif self.tailor == False and self.isMousePressLeft == True and self.state == None:
            # print("Case3:裁剪结束",self.handleSelected)
            painter.drawPixmap(self.pickRect.topLeft(), self.captureImage)
            self.setRect(self.pickRect.x(), self.pickRect.y(), self.pickRect.width(), self.pickRect.height())

        elif self.tailor == False and self.state != None:
            # print("Case3x:裁剪结束", self.tailor)
            tempRect = QRect(self.rect().x(), self.rect().y(), self.rect().width(), self.rect().height())
            tempPixmap = self.pixfixed
            painter.drawPixmap(self.rect().topLeft(), tempPixmap)
            self.pickRect = tempRect
            self.captureImage = tempPixmap

        else:
            # print("Case4:其他")
            self.point = QPointF(self.rect().topLeft().x(), self.rect().topLeft().y())
            self.ot = QRectF(0, 0, self.rect().width(), self.rect().height())
            painter.drawPixmap(self.point, self.pixfixed, self.ot)

        self.updateHandlesPos()
        # if self.originTailorRect != None and self.isMousePressLeft == True:
        #     print("原始轮廓:",self.originTailorRect)
        #     print("选择框:",self.pickRect, "矩形轮廓:",self.rect())
        #     print("图片：",self.pixfixed.rect())

        if self.isSelected():
            self.scene().itemClicked.emit(self)
            painter.setPen(QPen(QColor(150, 150, 150, 255), 0.5, Qt.SolidLine))
            painter.drawRect(self.boundingRect().adjusted(5, 5, -6, -6))

        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(0, 0, 0, 255), 1.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for i, shape in enumerate(self.handles.values()):
            if self.isSelected():
                if i == 0:
                    painter.setBrush(QBrush(QColor(Qt.blue)))
                    painter.drawRect(shape)
                else:
                    painter.setBrush(QBrush(QColor(Qt.red)))
                    painter.drawEllipse(shape)


class RectHandle(QGraphicsRectItem):  # QGraphicsRectItem
    """ 自定义小handles的名称、序号、控制点位置"""
    # handles 按照顺时针排列
    handle_names = ('left_top', 'middle_top', 'right_top', 'right_middle',
                    'right_bottom', 'middle_bottom', 'left_bottom', 'left_middle')
    # 设定在控制点上的光标形状
    handle_cursors = {
        0: Qt.SizeFDiagCursor,
        1: Qt.SizeVerCursor,
        2: Qt.SizeBDiagCursor,
        3: Qt.SizeHorCursor,
        4: Qt.SizeFDiagCursor,
        5: Qt.SizeVerCursor,
        6: Qt.SizeBDiagCursor,
        7: Qt.SizeHorCursor
    }
    offset = 6.0  # 外边界框相对于内边界框的偏移量，也是控制点的大小

    # min_size = 8 * offset  # 矩形框的最小尺寸

    def update_handles_pos(self):
        """
        更新控制点的位置
        """
        o = self.offset  # 偏置量
        s = o * 2  # handle 的大小
        b = self.rect()  # 获取内边框
        x1, y1 = b.left(), b.top()  # 左上角坐标
        offset_x = b.width() / 2
        offset_y = b.height() / 2
        # 设置 handles 的位置
        self.handles[0] = QRectF(x1 - o, y1 - o, s, s)
        self.handles[1] = self.handles[0].adjusted(offset_x, 0, offset_x, 0)
        self.handles[2] = self.handles[1].adjusted(offset_x, 0, offset_x, 0)
        self.handles[3] = self.handles[2].adjusted(0, offset_y, 0, offset_y)
        self.handles[4] = self.handles[3].adjusted(0, offset_y, 0, offset_y)
        self.handles[5] = self.handles[4].adjusted(-offset_x, 0, -offset_x, 0)
        self.handles[6] = self.handles[5].adjusted(-offset_x, 0, -offset_x, 0)
        self.handles[7] = self.handles[6].adjusted(0, -offset_y, 0, -offset_y)

        # self.handles[8] = QRectF(-50-o, 100-o, s, s)


class RectItem(RectHandle):
    """ 自定义可变矩形类"""

    def __init__(self, brushcolor, style, color, width, r_last, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.handles = {}  # 控制点的字典
        self.setAcceptHoverEvents(True)  # 设定为接受 hover 事件
        self.setFlags(QGraphicsItem.ItemIsSelectable |  # 设定矩形框为可选择的
                      QGraphicsItem.ItemSendsGeometryChanges |  # 追踪图元改变的信息
                      QGraphicsItem.ItemIsFocusable |  # 可聚焦
                      QGraphicsItem.ItemIsMovable)  # 可移动
        self.update_handles_pos()  # 初始化控制点
        self.reset_Ui()  # 初始化 UI 变量
        self.brush_color = brushcolor
        self.pen_style = style
        self.pen_color = color
        self.pen_width = width
        self.r_last = r_last
        self.setZValue(0)
        self.setSelected(True)
        self.oldRect = QRectF()
        self.oldAngle = 0
        self.opposite_ = QPointF()
        self.origin = QRectF()
        self.delta = QPointF()

    def reset_Ui(self):
        '''初始化 UI 变量'''
        self.handleSelected = None  # 被选中的控制点
        self.mousePressPos = None  # 鼠标按下的位置
        # self.mousePressRect = None  # 鼠标按下的位置所在的图元的外边界框

    def boundingRect(self):
        """
        限制图元的可视化区域，且防止出现图元移动留下残影的情况
        """
        o = self.offset
        # 添加一个间隔为 o 的外边框
        return self.rect().adjusted(-o, -o, o, o)

    def item_based_info(self):
        try:
            if self != [] and self[0].type() == 3:
                hand_selected = self[0].handleSelected
                rr = self[0].rotation()
                o_site = self[0].data(0)
                x = self[0].x()
                y = self[0].y()
                oo = 0
                # self[0].setTransformOriginPoint(self[0].rect().topLeft().x() +self[0].rect().width() / 2, self[0].rect().topLeft().y()+self[0].rect().height() / 2)
                o = QPointF(self[0].rect().topLeft().x() + self[0].rect().width() / 2,
                            self[0].rect().topLeft().y() + self[0].rect().height() / 2)
                # print(o_site,self[0].rect(),o)
                return hand_selected, o, x, y, rr
        except Exception as e:
            print(e)

    def handle_rotation(self, rr, x, y, origin, start, end):
        if self != []:
            # print(self, rr, x, y, origin, start, end)

            # p2 = QPointF(0, 0)
            # self[0].setTransformOriginPoint(p2)
            o = QPointF(origin.x() + x, origin.y() + y)
            v1 = start - o
            v2 = end - o
            angle = math.atan2(v2.y(), v2.x()) - math.atan2(v1.y(), v1.x())
            angle = int(angle * 180 / math.pi)
            angle = angle + rr
            self[0].setRotation(angle)

    def mouseDoubleClickEvent(self, event):
        myColorDialog = QColorDialog(parent=None)
        myColorDialog.setOption(QColorDialog.ShowAlphaChannel)
        myColorDialog.exec_()
        self.pen_color = myColorDialog.currentColor()

    def handle_at(self, point):
        """
        返回给定 point 下的控制点 handle
        """
        for k, v, in self.handles.items():
            if v.contains(point):
                return k
        return

    def hoverMoveEvent(self, event):
        """
        当鼠标移到该 item（未按下）上时执行
        """
        super().hoverMoveEvent(event)
        if self.isSelected():
            handle = self.handle_at(event.pos())
            if handle is None:
                cursor = Qt.SizeAllCursor
            elif handle == 0:
                pm = QPixmap("rotate_icon.ico")
                pm = pm.scaled(30, 30)
                cursor = QCursor(pm)
            else:
                cursor = self.handle_cursors[handle]
            self.setCursor(cursor)
        else:
            cursor = Qt.SizeAllCursor
            self.setCursor(cursor)

    def hoverLeaveEvent(self, event):
        """
        当鼠标离开该形状（未按下）上时执行。
        """
        super().hoverLeaveEvent(event)
        self.setCursor(Qt.ArrowCursor)  # 设定鼠标光标形状

    def mousePressEvent(self, event):
        """
        当在 item 坐标内部按下鼠标时执行
        """
        super().mousePressEvent(event)

        self.oldRect = self.rect()
        self.oldAngle = self.rotation()
        self.scene().itemClicked.emit(self)
        self.handleSelected = self.handle_at(event.pos())
        if self.handleSelected in self.handles:
            self.mousePressPos = event.pos()

    def mouseReleaseEvent(self, event):
        """
        当在 item 坐标内部鼠标释放时执行
        """
        super().mouseReleaseEvent(event)
        if self.handleSelected != None:
            if self.handleSelected != 0:
                pointO = self.mapToScene(self.oldRect.center())
                pointC = self.mapToScene(self.rect().center())
                self.delta = pointO - pointC
                # print(self.oldRect,self.rect())
                # self.scene().itemResized.emit(self, self.oldRect,self.delta)
                self.updateCoordinate()
                self.scene().itemResized.emit(self, self.oldRect, self.delta)


            else:
                self.scene().itemRotated.emit(self, self.oldAngle)

        self.update()
        self.reset_Ui()
        self.opposite_ = self.rect().center()

    def mouseMoveEvent(self, event):
        """
        当在 item 坐标内部鼠标移动时执行
        """
        if self.handleSelected in self.handles:
            self.interactiveResize(event.pos())
        else:
            super().mouseMoveEvent(event)

    def updateCoordinate(self):
        """图形大小变化时更新图元的坐标原点（旋转中心）"""
        self.prepareGeometryChange()
        pointO = self.mapToScene(self.oldRect.center())
        pointC = self.mapToScene(self.rect().center())
        self.delta = pointO - pointC
        w = self.rect().width()
        h = self.rect().height()
        self.m_localRect = QRectF(-w / 2, -h / 2, w, h)
        self.setRect(self.m_localRect)
        self.setTransformOriginPoint(self.m_localRect.center())
        # self.moveBy(-self.delta.x(), -self.delta.y())

    def interactiveResize(self, mousePos):
        """用于交互式的矩形变换，如重设点位置"""
        rect = self.rect()
        self.prepareGeometryChange()
        # self.setTransformOriginPoint(0,0)
        #   rect.setTopLeft(mousePos)
        if self.handleSelected == 1:
            rect.setTop(mousePos.y())
        elif self.handleSelected == 2:
            rect.setTopRight(mousePos)
        elif self.handleSelected == 3:
            rect.setRight(mousePos.x())
        elif self.handleSelected == 4:
            opposite = self.oldRect.topLeft()
            self.opposite_ = opposite
            rect.setBottomRight(mousePos)
        elif self.handleSelected == 5:
            rect.setBottom(mousePos.y())
        elif self.handleSelected == 6:
            rect.setBottomLeft(mousePos)
        elif self.handleSelected == 7:
            rect.setLeft(mousePos.x())
        self.setRect(rect)
        self.update_handles_pos()

    def paint(self, painter, option, widget=None):
        """
        利用QPainter画出自定义的内容
        """

        painter.setPen(QPen(self.pen_color, self.pen_width, self.pen_style))
        painter.setBrush(self.brush_color)
        o = self.pen_width / 2 + 6
        # painter.translate(self.opposite_)
        painter.drawRect(self.boundingRect().adjusted(o, o, -o, -o))
        # painter.drawRect(self.rect())
        # painter.rotate(self.oldAngle)

        self.update_handles_pos()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(0, 0, 0, 255), 0,
                            Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for i, shape in enumerate(self.handles.values()):
            if self.isSelected():
                self.scene().itemClicked.emit(self)

                if i == 0:
                    painter.setBrush(QBrush(QColor(Qt.blue)))
                    painter.drawRect(shape)
                else:
                    painter.setBrush(QBrush(QColor(255, 255, 0, 200)))
                    painter.drawEllipse(shape)

                    # painter.drawLine(
                    #     QLine(QPoint(self.opposite_.x() - 6, self.opposite_.y()), QPoint(self.opposite_.x() + 6, self.opposite_.y())))
                    # painter.drawLine(
                    #     QLine(QPoint(self.opposite_.x(), self.opposite_.y() - 6), QPoint(self.opposite_.x(), self.opposite_.y() + 6)))
                    # painter.drawLine(
                    #     QLine(QPoint(self.origin.x() - 6, self.origin.y()), QPoint(self.origin.x() + 6, self.origin.y())))
                    # painter.drawLine(
                    #     QLine(QPoint(self.origin.x(), self.origin.y() - 6), QPoint(self.origin.x(), self.origin.y() + 6)))


class EllipseItem(RectHandle):
    """ 自定义可变椭圆类"""

    def __init__(self, brushcolor, style, color, width, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.handles = {}  # 控制点的字典
        self.setAcceptHoverEvents(True)  # 设定为接受 hover 事件
        self.setFlags(QGraphicsItem.ItemIsSelectable |  # 设定矩形框为可选择的
                      QGraphicsItem.ItemSendsGeometryChanges |  # 追踪图元改变的信息
                      QGraphicsItem.ItemIsFocusable |  # 可聚焦
                      QGraphicsItem.ItemIsMovable)  # 可移动
        self.update_handles_pos()  # 初始化控制点
        self.reset_Ui()  # 初始化 UI 变量
        self.brush_color = brushcolor
        self.pen_style = style
        self.pen_color = color
        self.pen_width = width
        self.setZValue(0)
        self.setSelected(True)
        self.oldRect = QRectF()
        self.oldAngle = None

    def reset_Ui(self):
        '''初始化 UI 变量'''
        self.handleSelected = None  # 被选中的控制点
        self.mousePressPos = None  # 鼠标按下的位置
        # self.mousePressRect = None  # 鼠标按下的位置所在的图元的外边界框

    def boundingRect(self):
        """
        限制图元的可视化区域，且防止出现图元移动留下残影的情况
        """
        o = self.offset
        # 添加一个间隔为 o 的外边框
        return self.rect().adjusted(-o, -o, o, o)

    def mouseDoubleClickEvent(self, event):
        myColorDialog = QColorDialog(parent=None)
        myColorDialog.setOption(QColorDialog.ShowAlphaChannel)
        myColorDialog.exec_()
        self.pen_color = myColorDialog.currentColor()

    def paint(self, painter, option, widget=None):
        """
        利用QPainter画出自定义的内容
        """
        # painter.setBrush(QBrush(QColor(255, 0, 0, 100)))
        painter.setPen(QPen(self.pen_color, self.pen_width, self.pen_style))
        painter.setBrush(self.brush_color)
        o = self.pen_width / 2 + 6
        painter.drawEllipse(self.boundingRect().adjusted(o, o, -o, -o))
        self.update_handles_pos()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(0, 0, 0, 255), 0,
                            Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for i, shape in enumerate(self.handles.values()):
            if self.isSelected():
                self.scene().itemClicked.emit(self)
                if i == 0:
                    painter.setBrush(QBrush(QColor(Qt.blue)))
                    painter.drawRect(shape)
                else:
                    painter.setBrush(QBrush(QColor(255, 255, 0, 200)))
                    painter.drawEllipse(shape)

    def handle_at(self, point):
        """
        返回给定 point 下的控制点 handle
        """
        for k, v, in self.handles.items():
            if v.contains(point):
                return k
        return

    def hoverMoveEvent(self, event):
        """
        当鼠标移到该 item（未按下）上时执行。
        """
        super().hoverMoveEvent(event)
        if self.isSelected():
            handle = self.handle_at(event.pos())
            if handle is None:
                cursor = Qt.SizeAllCursor
            elif handle == 0:
                pm = QPixmap("rotate_icon.ico")
                pm = pm.scaled(30, 30)
                cursor = QCursor(pm)
            else:
                cursor = self.handle_cursors[handle]
            self.setCursor(cursor)
        else:
            cursor = Qt.SizeAllCursor
            self.setCursor(cursor)

    def hoverLeaveEvent(self, event):
        """
        当鼠标离开该形状（未按下）上时执行。
        """
        super().hoverLeaveEvent(event)
        self.setCursor(Qt.ArrowCursor)  # 设定鼠标光标形状

    def mousePressEvent(self, event):
        """
        当在 item 上按下鼠标时执行
        """
        super().mousePressEvent(event)
        self.oldRect = self.rect()
        self.oldAngle = self.rotation()
        self.scene().itemClicked.emit(self)
        self.handleSelected = self.handle_at(event.pos())
        if self.handleSelected in self.handles:
            self.mousePressPos = event.pos()

    def mouseReleaseEvent(self, event):
        """
        当在 item 坐标内部鼠标释放时执行
        """
        super().mouseReleaseEvent(event)
        if self.handleSelected != None:
            if self.handleSelected != 0:
                pointO = self.mapToScene(self.oldRect.center())
                pointC = self.mapToScene(self.rect().center())
                self.delta = pointO - pointC
                # self.scene().itemResized.emit(self, self.oldRect,self.delta)

                self.updateCoordinate()
                self.scene().itemResized.emit(self, self.oldRect, self.delta)
            else:
                self.scene().itemRotated.emit(self, self.oldAngle)
        self.update()
        self.reset_Ui()

    def mouseMoveEvent(self, event):
        """
        当在 item 坐标内部鼠标移动时执行
        """
        if self.handleSelected in self.handles:
            self.interactiveResize(event.pos())
        else:
            super().mouseMoveEvent(event)

    def updateCoordinate(self):
        """图形大小变化时更新图元的坐标原点（旋转中心）"""
        self.prepareGeometryChange()
        pointO = self.mapToScene(self.oldRect.center())
        pointC = self.mapToScene(self.rect().center())
        self.delta = pointO - pointC
        w = self.rect().width()
        h = self.rect().height()
        self.m_localRect = QRectF(-w / 2, -h / 2, w, h)
        self.setRect(self.m_localRect)
        self.setTransformOriginPoint(self.m_localRect.center())
        # self.moveBy(-self.delta.x(), -self.delta.y())

    def interactiveResize(self, mousePos):
        """用于交互式的矩形变换，如重设点位置"""
        rect = self.rect()
        self.prepareGeometryChange()
        # print(mousePos)
        # movePos = mousePos - self.mousePressPos
        # move_x, move_y = movePos.x(), movePos.y()
        # if self.handleSelected == 0:
        #     rect.setTopLeft(mousePos)
        if self.handleSelected == 1:
            rect.setTop(mousePos.y())
        elif self.handleSelected == 2:
            rect.setTopRight(mousePos)
        elif self.handleSelected == 3:
            rect.setRight(mousePos.x())
        elif self.handleSelected == 4:
            rect.setBottomRight(mousePos)
        elif self.handleSelected == 5:
            rect.setBottom(mousePos.y())
        elif self.handleSelected == 6:
            rect.setBottomLeft(mousePos)
        elif self.handleSelected == 7:
            rect.setLeft(mousePos.x())
        self.setRect(rect)
        self.update_handles_pos()


class ArrowItem(QGraphicsPathItem):
    """ 自定义箭头类，类重写的是QGraphicsPathItem"""

    handleTopLeft = 1
    handleTopMiddle = 2
    handleTopRight = 3
    handleMiddleLeft = 4
    handleMiddleRight = 5
    handleBottomLeft = 6
    handleBottomMiddle = 7
    handleBottomRight = 8

    handleSize = +10.0
    handleSpace = -4.0

    # 设置鼠标形状
    handleCursors = {
        handleTopLeft: Qt.SizeFDiagCursor,
        handleTopMiddle: Qt.SizeVerCursor,
        handleTopRight: Qt.SizeBDiagCursor,
        handleMiddleLeft: Qt.SizeHorCursor,
        handleMiddleRight: Qt.SizeHorCursor,
        handleBottomLeft: Qt.SizeBDiagCursor,
        handleBottomMiddle: Qt.SizeVerCursor,
        handleBottomRight: Qt.SizeFDiagCursor,
    }

    def __init__(self, scene, color, penwidth, style, parent=None):
        super().__init__(parent)
        self.pen_color = color  # 从Qgraphicsview导入笔的颜色
        self.pen_width = penwidth  # 从Qgraphicsview导入笔的宽度
        self.pen_style = style  # 从Qgraphicsview导入笔的宽度
        self.scene = scene  # 从Qgraphicsview导入Myscene()这个场景，并设置为它
        # self.setSelected(True)

        self.pos_src = [0, 0]
        self.pos_dst = [0, 0]

        self.setFlags(QGraphicsItem.ItemIsSelectable |  # 设定矩形框为可选择的
                      QGraphicsItem.ItemSendsGeometryChanges |  # 追踪图元改变的信息
                      QGraphicsItem.ItemIsFocusable |  # 可聚焦
                      QGraphicsItem.ItemIsMovable)  # 可移动

        self.handles = {}
        self.isDrag = False
        self.handleSelected = None
        self.mousePressPos = None
        self.mousePressRect = None
        self.setAcceptHoverEvents(True)
        self.setZValue(0)
        self.updateHandlesPos()
        self.setSelected(True)
        self.oldPath = None

    def handleAt(self, point):  # point为鼠标的点位置信息
        """返回自设定的小handle是否包含鼠标所在的点位置，若是，则返回鼠标在第几个handle上"""
        for k, v, in self.handles.items():  # k为数值1~8，辨别是handleTopLeft=1还是其他；v则是返回小handle的QRectF
            if v.contains(point):
                # print(k)
                return k
        return None

    def hoverMoveEvent(self, moveEvent):
        """执行鼠标在图片上移动的事件（非鼠标点击事件）"""
        # print("hoverMoveEvent",moveEvent.pos())
        cursor = Qt.SizeAllCursor
        self.setCursor(cursor)
        if self.isSelected():
            handle = self.handleAt(moveEvent.pos())
            # print("hoverMoveEvent",handle)
            if handle is None:
                cursor = Qt.SizeAllCursor
            elif handle == 1:
                cursor = Qt.CrossCursor
            elif handle == 2:
                cursor = Qt.CrossCursor
            else:
                cursor = self.handleCursors[handle]
            self.setCursor(cursor)
        super().hoverMoveEvent(moveEvent)

    def hoverLeaveEvent(self, moveEvent):
        """执行鼠标移动到图片外边的事件（非鼠标点击事件）"""
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(moveEvent)

    def mousePressEvent(self, mouseEvent):
        """执行鼠标在图片上点击事件"""

        # self.scene().itemClicked.emit(self)
        self.handleSelected = self.handleAt(mouseEvent.pos())
        if self.handleSelected == 1:
            self.oldPath = self.pos_src
        else:
            self.oldPath = self.pos_dst

        if self.handleSelected:
            if mouseEvent.button() == Qt.LeftButton:
                self.isDrag = True
            self.mousePressPos = mouseEvent.pos()
            # self.mousePressRect = self.boundingRect()  # 返回点击的Rect的boundingRect虚函数
        super().mousePressEvent(mouseEvent)

    def mouseMoveEvent(self, mouseEvent):
        """执行鼠标在图片上点击后按住鼠标移动的事件"""
        if self.handleSelected is not None:
            self.interactiveResize(mouseEvent.pos())  # 此句鼠标点击图片并移动时返回None值
        else:
            self.update()
            super().mouseMoveEvent(mouseEvent)

    def mouseReleaseEvent(self, mouseEvent):
        """执行鼠标在图片上释放事件"""
        super().mouseReleaseEvent(mouseEvent)
        # 重设以下参数
        if self.handleSelected != None:
            self.scene.itemResized.emit(self, self.oldPath, None)
        self.handleSelected = None
        self.mousePressPos = None
        self.mousePressRect = None
        self.update()
        self.isDrag = False

    def updateHandlesPos(self):
        """基于图形的形状尺寸和位置，更新现有的resize handles位置"""
        s = self.handleSize
        sa = self.shape().currentPosition()
        info = self.shape().controlPointRect()
        b = self.shape().boundingRect()
        # o = self.handleSize + self.handleSpace
        o = 8
        r = b.adjusted(-o, -o, o, o)
        # print(s,sa,info,b,o,r)
        # print(self.pos_src[0],self.pos_src[1])

        self.handles[self.handleTopLeft] = QRectF(self.pos_src[0] - o / 2, self.pos_src[1] - o / 2, o, o)
        self.handles[self.handleTopMiddle] = QRectF(self.pos_dst[0] - o / 2, self.pos_dst[1] - o / 2, o, o)
        # self.handles[self.handleTopRight] = QRectF(r.right() - s, r.top(), s, s)
        # self.handles[self.handleMiddleLeft] = QRectF(r.left(), r.center().y() - s / 2, s, s)
        # self.handles[self.handleMiddleRight] = QRectF(r.right() - s, r.center().y() - s / 2, s, s)
        # self.handles[self.handleBottomLeft] = QRectF(r.left(), r.bottom() - s, s, s)
        # self.handles[self.handleBottomMiddle] = QRectF(r.center().x() - s / 2, r.bottom() - s, s, s)
        # self.handles[self.handleBottomRight] = QRectF(r.right() - s, r.bottom() - s, s, s)

    def interactiveResize(self, mousePos):
        """用于交互式的矩形变换，如重设点位置"""
        diff = QPointF(0, 0)
        self.mousePos = mousePos
        self.prepareGeometryChange()
        if self.handleSelected == 1:
            self.set_src(mousePos.x(), mousePos.y())
            self.calc_path()
            self.update()
        if self.handleSelected == 2:
            self.set_dst(mousePos.x(), mousePos.y())
            self.calc_path()
            self.update()

    def set_src(self, x, y):
        """设置箭头起始点"""
        self.pos_src = [x, y]

    def set_dst(self, x, y):
        """设置箭头末尾点"""
        self.pos_dst = [x, y]

    def calc_path(self):
        """连接起始点和末尾点，构成箭头线的路径"""
        path = QPainterPath(QPointF(self.pos_src[0], self.pos_src[1]))
        path.lineTo(self.pos_dst[0], self.pos_dst[1])
        return path

    def boundingRect(self):
        # o = self.offset = self.pen_width * 10
        o = self.pen_width * 10
        x1, y1 = self.pos_src
        x2 = self.shape().boundingRect().width() + 10
        y2 = self.shape().boundingRect().height() + 10
        self.QF = QRectF(x1, y1, x2, y2)
        return self.shape().boundingRect().adjusted(-o, -o, o, o)

    def shape(self):
        """返回箭头类的形状，这里设置了比实际画出来的宽度+10，目的是使鼠标更好点选中箭头图元（当画笔比较细的时候）"""
        stroker = QPainterPathStroker()
        stroker.setWidth(10)
        path = self.calc_path()
        path_r = stroker.createStroke(path)
        # print("ArrowItemshape:",path_r)
        return path_r

    def paint(self, painter, option, widget=None):

        self.updateHandlesPos()
        self.setPath(self.calc_path())

        path = self.path()
        painter.setPen(QPen(self.pen_color, self.pen_width, self.pen_style))
        painter.drawPath(path)

        x1, y1 = self.pos_src
        x2, y2 = self.pos_dst

        self.source = QPointF(x1, y1)
        self.dest = QPointF(x2, y2)
        self.line = QLineF(self.source, self.dest)
        # 设置垂直向量
        v = self.line.unitVector()
        v.setLength(self.pen_width * 4)
        v.translate(QPointF(self.line.dx(), self.line.dy()))
        # 设置水平向量
        n = v.normalVector()
        n.setLength(n.length() * 0.5)
        n2 = n.normalVector().normalVector()
        # 设置箭头三角形的三个点
        p1 = v.p2()
        p2 = n.p2()
        p3 = n2.p2()
        # 以下用于绘制箭头，外边框粗为1.0
        painter.setPen(QPen(self.pen_color, 1.0, Qt.SolidLine))
        painter.setBrush(self.pen_color)
        painter.drawPolygon(p1, p2, p3)
        for i, shape in enumerate(self.handles.values()):
            if self.isSelected():
                painter.setBrush(QBrush(QColor(Qt.blue)))
                painter.drawRect(shape)


class TextItemDlg(QDialog):
    """ 自定义文本类所用到的窗口，用的是类似QDialog"""

    def __init__(self, item=None, position=None, scene=None, parent=None):
        super(QDialog, self).__init__(parent)
        try:
            self.item = item

            self.position = position

            self.scene = scene
            self.font = None

            self.background_color_str = "transparent"
            self.booltext = False
            self.boolItalic = False
            self.boolunderline = False
            self.bo = ''
            self.it = ''
            self.ud = ''
            self.list = [0, 0, 0]

            self.editor = QTextEdit()
            self.editor.setAcceptRichText(False)
            self.editor.setTabChangesFocus(True)
            editorLabel = QLabel("文字输入框:")
            editorLabel.setBuddy(self.editor)
            self.fontComboBox = QFontComboBox()
            self.fontComboBox.setCurrentFont(QFont("Times", PointSize))
            fontLabel = QLabel("&字体：")
            fontLabel.setBuddy(self.fontComboBox)
            self.fontSpinBox = QSpinBox()
            self.fontSpinBox.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.fontSpinBox.setRange(5, 300)
            self.fontSpinBox.setValue(PointSize)
            fontSizeLabel = QLabel("&字体大小：")
            fontSizeLabel.setBuddy(self.fontSpinBox)
            self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
            self.textcolorlabel = QLabel("字体颜色：")
            self.textcolor = QComboBox()
            self.backgroundcolorlabel = QLabel("文本框颜色:")
            self.backgroundcolorlabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.backgroundcolor = QComboBox()
            # 获取颜色列表(字符串类型)
            self.__colorList = QColor.colorNames()
            # 用各种颜色填充下拉列表
            self.__fillColorList(self.textcolor)
            self.__fillColorList1(self.backgroundcolor)

            self.bold_btn = QPushButton("B/加粗")
            self.bold_btn.setCheckable(True)
            self.Italic_btn = QPushButton("I/斜体")
            self.Italic_btn.setCheckable(True)
            self.underline_btn = QPushButton("U/下划线")
            self.underline_btn.setCheckable(True)

            if self.item is not None:
                self.editor.setPlainText(self.item.toPlainText())
                self.fontComboBox.setCurrentFont(self.item.font())
                self.fontSpinBox.setValue(self.item.font().pointSize())
                self.booltext = self.item.font().bold()
                self.bold_btn.setChecked(self.booltext)
                self.boolItalic = self.item.font().italic()
                self.Italic_btn.setChecked(self.boolItalic)
                self.boolunderline = self.item.font().underline()
                self.underline_btn.setChecked(self.boolunderline)
                self.color_str = self.item.data(1)
                self.textcolor.setCurrentIndex(self.item.data(0))
                pl = QPalette()
                pl.setColor(QPalette.Text, QColor(self.color_str))
                self.editor.setPalette(pl)
                self.backgroundcolor.setCurrentIndex(self.item.data(3))
                self.background_color_str = self.item.data(2)

            layout = QGridLayout()
            layout.addWidget(editorLabel, 0, 0)
            layout.addWidget(self.bold_btn, 0, 1)
            layout.addWidget(self.Italic_btn, 0, 2)
            layout.addWidget(self.underline_btn, 0, 3)
            layout.addWidget(self.editor, 1, 0, 1, 6)
            layout.addWidget(fontLabel, 2, 0)
            layout.addWidget(self.fontComboBox, 2, 1, 1, 2)
            layout.addWidget(fontSizeLabel, 2, 3)
            layout.addWidget(self.fontSpinBox, 2, 4, 1, 2)
            layout.addWidget(self.buttonBox, 4, 0, 1, 6)
            layout.addWidget(self.textcolor, 3, 1, 1, 1)
            layout.addWidget(self.textcolorlabel, 3, 0)
            layout.addWidget(self.backgroundcolorlabel, 3, 2)
            layout.addWidget(self.backgroundcolor, 3, 3, 1, 1)
            self.setLayout(layout)

            self.fontComboBox.currentFontChanged.connect(self.updateUi)
            self.fontSpinBox.valueChanged.connect(self.updateUi)
            self.editor.textChanged.connect(self.updateUi)
            self.buttonBox.accepted.connect(self.accept)
            self.buttonBox.rejected.connect(self.reject)
            # self.textcolor.currentIndexChanged.connect(self.on_textcolorChange)
            self.textcolor.currentIndexChanged.connect(self.updateUi)
            self.backgroundcolor.currentIndexChanged.connect(self.on_backgroundcolorChange)
            self.setWindowTitle("添加文本")
            self.setWindowIcon(QIcon("q.ico"))
            self.updateUi()
            self.bold_btn.clicked.connect(self.on_bold_btn_clicked)
            self.Italic_btn.clicked.connect(self.Italic_btn_clicked)
            self.underline_btn.clicked.connect(self.underline_btn_clicked)

        except Exception as e:
            print(e)

    # 设置文本加粗
    def on_bold_btn_clicked(self):
        self.booltext = self.bold_btn.isChecked()
        self.updateUi()
        if self.booltext:
            self.list[0] = 1
        else:
            self.list[0] = 0

    # 设置文本斜体
    def Italic_btn_clicked(self):
        self.boolItalic = self.Italic_btn.isChecked()
        self.updateUi()
        if self.boolItalic:
            self.list[1] = 1
        else:
            self.list[1] = 0

    # 设置文本下划线
    def underline_btn_clicked(self):
        self.boolunderline = self.underline_btn.isChecked()
        self.updateUi()
        if self.boolunderline:
            self.list[2] = 1
        else:
            self.list[2] = 0

    # 设置文本颜色变更
    def on_textcolorChange(self):
        self.color_index = self.textcolor.currentIndex()
        self.color_str = self.__colorList[self.color_index]

    # 设置文本背景颜色变更
    def on_backgroundcolorChange(self):
        self.background_color_index = self.backgroundcolor.currentIndex()
        self.background_color_str = self.__colorList[self.background_color_index]

    def __fillColorList(self, comboBox):
        index_red = 0
        index = 0
        for color in self.__colorList:
            if color == "red":
                index_red = index
            index += 1
            pix = QPixmap(120, 30)
            pix.fill(QColor(color))
            comboBox.addItem(QIcon(pix), None)
            comboBox.setIconSize(QSize(100, 20))
            comboBox.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        comboBox.setCurrentIndex(index_red)

    def __fillColorList1(self, comboBox):
        index_transparent = 0
        index = 0
        for color in self.__colorList:
            if color == "transparent":
                index_white = index
            index += 1
            pix = QPixmap(120, 30)
            pix.fill(QColor(color))
            comboBox.addItem(QIcon(pix), None)
            comboBox.setIconSize(QSize(100, 20))
            comboBox.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        comboBox.setCurrentIndex(index_white)

    # 更新文本输入框的文字显示属性
    def updateUi(self):
        try:
            self.font = self.fontComboBox.currentFont()
            self.font.setPointSize(self.fontSpinBox.value())
            self.font.setBold(self.booltext)
            self.font.setItalic(self.boolItalic)
            self.font.setUnderline(self.boolunderline)
            self.editor.document().setDefaultFont(self.font)
            self.color_index = self.textcolor.currentIndex()
            self.color_str = self.__colorList[self.color_index]
            self.background_color_index = self.backgroundcolor.currentIndex()
            self.background_color_str = self.__colorList[self.background_color_index]
            pl = QPalette()
            pl.setColor(QPalette.Text, QColor(self.color_str))
            self.editor.setPalette(pl)
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(bool(self.editor.toPlainText()))
        except Exception as e:
            print(e)

    def accept(self):
        try:
            if self.item is None:
                self.item = TextItem("", self.position, self.scene)
            self.font = self.fontComboBox.currentFont()
            self.font.setPointSize(self.fontSpinBox.value())
            self.font.setBold(self.booltext)
            self.font.setItalic(self.boolItalic)
            self.font.setUnderline(self.boolunderline)

            # self.ud='text-decoration:underline'
            # self.bo='font-weight: bold;'
            # self.it='font-style: italic;'
            """辨别按了多少个和哪些字体属性设置按钮"""
            num = self.list[0] * 2 + self.list[1] * 3 + self.list[2] * 4
            self.item.setData(0, self.color_index)
            self.item.setData(1, self.color_str)
            self.item.setData(2, self.background_color_str)
            self.item.setData(3, self.background_color_index)
            # print(self.background_color_str)
            self.item.setFont(self.font)
            if num == 2:
                self.bo = 'font-weight: bold;'
                text = '<span style="background:' + self.background_color_str + ';"><font color="' + self.color_str + '"><p style=\"' + self.it + self.bo + self.ud + ';background-color:' + self.background_color_str + '\">' + self.editor.toPlainText() + '</font></span>'
            elif num == 3:
                self.it = 'font-style: italic;'
                text = '<span style="background:' + self.background_color_str + ';"><font color="' + self.color_str + '"><p style=\"' + self.it + self.bo + self.ud + ';background-color:' + self.background_color_str + '\">' + self.editor.toPlainText() + '</font></span>'
            elif num == 4:
                self.ud = 'text-decoration:underline'
                text = '<span style="background:' + self.background_color_str + ';"><font color="' + self.color_str + '"><p style=\"' + self.it + self.bo + self.ud + ';background-color:' + self.background_color_str + '\">' + self.editor.toPlainText() + '</font></span>'
            elif num == 5:
                self.bo = 'font-weight: bold;'
                self.it = 'font-style: italic;'
                text = '<span style="background:' + self.background_color_str + ';"><font color="' + self.color_str + '"><p style=\"' + self.it + self.bo + self.ud + ';background-color:' + self.background_color_str + '\">' + self.editor.toPlainText() + '</font></span>'
            elif num == 6:
                self.bo = 'font-weight: bold;'
                self.ud = 'text-decoration:underline'
                text = '<span style="background:' + self.background_color_str + ';"><font color="' + self.color_str + '"><p style=\"' + self.it + self.bo + self.ud + ';background-color:' + self.background_color_str + '\">' + self.editor.toPlainText() + '</font></span>'
            elif num == 7:
                self.it = 'font-style: italic;'
                self.ud = 'text-decoration:underline'
                text = '<span style="background:' + self.background_color_str + ';"><font color="' + self.color_str + '"><p style=\"' + self.it + self.bo + self.ud + ';background-color:' + self.background_color_str + '\">' + self.editor.toPlainText() + '</font></span>'
            elif num == 9:
                self.bo = 'font-weight: bold;'
                self.it = 'font-style: italic;'
                self.ud = 'text-decoration:underline'
                text = '<span style="background:' + self.background_color_str + ';"><font color="' + self.color_str + '"><p style=\"' + self.it + self.bo + self.ud + ';background-color:' + self.background_color_str + '\">' + self.editor.toPlainText() + '</font></span>'
            else:
                text = '<span style="background:' + self.background_color_str + ';"><font color="' + self.color_str + '"><p style=\"' + self.it + self.bo + self.ud + ';background-color:' + self.background_color_str + '\">' + self.editor.toPlainText() + '</font></span>'

            # 测试是否有换行符
            # for i,t in enumerate(text):
            #     if t=="\n":
            #         print("y")
            #         t="<br/>"

            text_fixed = text.replace("\n", "<br/>")
            self.item.setHtml(text_fixed)
            QDialog.accept(self)
        except Exception as e:
            print(e)


PointSize = 20  # 设置初始文字大小


class TextItem(QGraphicsTextItem):
    """ 自定义文本类"""

    def __init__(self, text, position, scene,
                 font=QFont("宋体", PointSize)):
        super(TextItem, self).__init__(text)
        try:
            self.setFlags(QtWidgets.QGraphicsItem.ItemIsSelectable
                          | QtWidgets.QGraphicsItem.ItemIsMovable
                          | QtWidgets.QGraphicsItem.ItemIsFocusable
                          | QtWidgets.QGraphicsItem.ItemSendsGeometryChanges
                          | QtWidgets.QGraphicsItem.ItemSendsScenePositionChanges)
            self.handleSelected = None
            self.setFont(font)
            self.setDefaultTextColor(Qt.red)
            self.setPos(position)
            scene.clearSelection()
            scene.itemAdded.emit(scene, self)
            # scene.addItem(self)
            self.setSelected(True)
            self.setZValue(0)
        except Exception as e:
            print(e)

    def parentWidget(self):
        try:
            return self.scene().views()[0]
        except Exception as e:
            print(e)

    def mouseDoubleClickEvent(self, event):
        dialog = TextItemDlg(self, self.parentWidget())

        dialog.exec_()


class Rectangle(QtWidgets.QGraphicsRectItem):
    """ 自定义可变矩形类，采用鼠标中键动态设置矩形大小"""

    def __init__(self, x, y, w, h):
        super(Rectangle, self).__init__(0, 0, w, h)
        self.setPen(QPen(Qt.red, 5))
        self.setFlags(QtWidgets.QGraphicsItem.ItemIsSelectable
                      | QtWidgets.QGraphicsItem.ItemIsMovable
                      | QtWidgets.QGraphicsItem.ItemIsFocusable
                      | QtWidgets.QGraphicsItem.ItemSendsGeometryChanges
                      | QtWidgets.QGraphicsItem.ItemSendsScenePositionChanges)
        self.setPos(QPointF(x, y))
        self.setZValue(0)
        self.handleSelected = None

    def mouseMoveEvent(self, e):
        # print(self.x,self.y)
        if e.buttons() & Qt.LeftButton:
            super(Rectangle, self).mouseMoveEvent(e)
        if e.buttons() & Qt.MidButton:
            self.setRect(QRectF(QPoint(), e.pos()).normalized())


class itemAddCommand(QUndoCommand):
    def __init__(self, scene, item):
        super(itemAddCommand, self).__init__()
        self.scene = scene
        self.item = item
        if isinstance(self.item, ArrowItem):
            self.setText('添加箭头')
        elif isinstance(self.item, RectItem):
            self.setText('添加矩形')
        elif isinstance(self.item, EllipseItem):
            self.setText('添加圆形')
        elif isinstance(self.item, PItem):
            self.setText('添加图片')
        elif isinstance(self.item, PItem_paste):
            self.setText('添加粘贴图片')
        else:
            self.setText('添加图元')

    def redo(self):
        self.scene.addItem(self.item)
        # self.item.setPos(self.initPos)
        # self.scene.clearSelection()

    def undo(self):
        self.scene.removeItem(self.item)
        self.scene.update()


class itemMoveCommand(QUndoCommand):
    def __init__(self, item, oldPos):
        super(itemMoveCommand, self).__init__()
        self.item = item
        self.oldPos = oldPos
        self.newPos = self.item.pos()

    def redo(self):
        self.item.setPos(self.newPos)
        if isinstance(self.item, ArrowItem):
            self.setText('箭头移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))
        elif isinstance(self.item, RectItem):
            self.setText('矩形移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))
        elif isinstance(self.item, EllipseItem):
            self.setText('圆形移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))
        elif isinstance(self.item, PItem):
            self.setText('图片移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))
        elif isinstance(self.item, PItem_paste):
            self.setText('粘贴图片移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))
        elif isinstance(self.item, TextItem):
            self.setText('文本移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))
        elif isinstance(self.item, QGraphicsItemGroup):
            self.setText('组合图形移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))
        else:
            self.setText('画笔移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))

    def undo(self):
        self.item.setPos(self.oldPos)
        if isinstance(self.item, ArrowItem):
            self.setText('箭头移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))
        elif isinstance(self.item, RectItem):
            self.setText('矩形移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))
        elif isinstance(self.item, EllipseItem):
            self.setText('圆形图元移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))
        elif isinstance(self.item, PItem):
            self.setText('图片移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))
        elif isinstance(self.item, PItem_paste):
            self.setText('粘贴图片移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))
        elif isinstance(self.item, TextItem):
            self.setText('文本移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))
        elif isinstance(self.item, QGraphicsItemGroup):
            self.setText('组合图形移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))
        else:
            self.setText('画笔移动 %d %d' % (self.item.pos().x(), self.item.pos().y()))


class itemResizeCommand(QUndoCommand):
    def __init__(self, item, oldRect, delta):
        super(itemResizeCommand, self).__init__()
        self.item = item
        self.oldRect = oldRect
        self.delta = delta

        if isinstance(self.item, ArrowItem):
            self.s = self.item.handleSelected
            if self.item.handleSelected == 1:
                self.newPath = self.item.pos_src
            else:
                self.newPath = self.item.pos_dst
        else:
            self.h = self.item.handleSelected
            self.newRect = self.item.rect()
        # print(self.oldRect,self.newRect)

    def redo(self):
        if isinstance(self.item, ArrowItem):
            if self.s == 1:
                self.item.set_src(self.newPath[0], self.newPath[1])
                self.item.calc_path()
                self.item.update()
                # GraphicView().update()
                self.setText('箭头调整1 %d %d' % (self.newPath[0], self.newPath[1]))
            elif self.s == 2:
                self.item.set_dst(self.newPath[0], self.newPath[1])
                self.item.calc_path()
                self.item.update()
                # GraphicView().update()
                self.setText('箭头调整2 %d %d' % (self.newPath[0], self.newPath[1]))
        else:
            if isinstance(self.item, RectItem):
                self.item.setRect(self.newRect)
                self.item.updateCoordinate()
                self.item.moveBy(-self.delta.x(), -self.delta.y())
                self.setText('矩形调整(%s) %d %d' % (self.h, self.item.rect().width(), self.item.rect().height()))
            elif isinstance(self.item, EllipseItem):
                self.item.setRect(self.newRect)
                self.item.updateCoordinate()
                self.item.moveBy(-self.delta.x(), -self.delta.y())
                self.setText('圆形调整(%s) %d %d' % (self.h, self.item.rect().width(), self.item.rect().height()))
            elif isinstance(self.item, PItem):
                self.item.setRect(self.newRect)
                self.item.updateCoordinate()
                self.item.moveBy(-self.delta.x(), -self.delta.y())
                self.setText('图片调整(%s) %d %d' % (self.h, self.item.rect().width(), self.item.rect().height()))
            elif isinstance(self.item, PItem_paste):
                self.item.setRect(self.newRect)
                self.item.updateCoordinate()
                self.item.moveBy(-self.delta.x(), -self.delta.y())
                self.setText('粘贴图片调整(%s) %d %d' % (self.h, self.item.rect().width(), self.item.rect().height()))

    def undo(self):
        if isinstance(self.item, ArrowItem):
            if self.s == 1:
                self.item.set_src(self.oldRect[0], self.oldRect[1])
                self.item.calc_path()
                self.item.update()
                # GraphicView().update()
                self.setText('箭头调整1 %d %d' % (self.oldRect[0], self.oldRect[1]))
            elif self.s == 2:
                self.item.set_dst(self.oldRect[0], self.oldRect[1])
                self.item.calc_path()
                self.item.update()
                # GraphicView().update()
                self.setText('箭头调整2 %d %d' % (self.oldRect[0], self.oldRect[1]))
        else:
            if isinstance(self.item, RectItem):
                self.item.setRect(self.oldRect)
                self.item.updateCoordinate()
                self.item.moveBy(+self.delta.x(), +self.delta.y())
                self.setText('矩形调整(%s) %d %d' % (self.h, self.item.rect().width(), self.item.rect().height()))
            elif isinstance(self.item, EllipseItem):
                self.item.setRect(self.oldRect)
                self.item.updateCoordinate()
                self.item.moveBy(+self.delta.x(), +self.delta.y())
                self.setText('圆形调整(%s) %d %d' % (self.h, self.item.rect().width(), self.item.rect().height()))
            elif isinstance(self.item, PItem):
                self.item.setRect(self.oldRect)
                self.item.updateCoordinate()
                self.item.moveBy(+self.delta.x(), +self.delta.y())
                self.setText('图片调整(%s) %d %d' % (self.h, self.item.rect().width(), self.item.rect().height()))
            elif isinstance(self.item, PItem_paste):
                self.item.setRect(self.oldRect)
                self.item.updateCoordinate()
                self.item.moveBy(+self.delta.x(), +self.delta.y())
                self.setText('粘贴图片调整(%s) %d %d' % (self.h, self.item.rect().width(), self.item.rect().height()))


class itemRotateCommand(QUndoCommand):
    def __init__(self, item, oldAngle):
        super(itemRotateCommand, self).__init__()
        self.item = item
        self.oldAngle = oldAngle
        self.newAngle = self.item.rotation()

    def redo(self):
        self.item.setRotation(self.newAngle)
        if isinstance(self.item, ArrowItem):
            self.setText('箭头旋转 %d °' % (self.item.rotation()))
        elif isinstance(self.item, RectItem):
            self.setText('矩形旋转 %d °' % (self.item.rotation()))
        elif isinstance(self.item, EllipseItem):
            self.setText('圆形旋转 %d °' % (self.item.rotation()))
        elif isinstance(self.item, PItem):
            self.setText('图片旋转 %d °' % (self.item.rotation()))
        elif isinstance(self.item, PItem_paste):
            self.setText('粘贴图片旋转 %d °' % (self.item.rotation()))
        elif isinstance(self.item, TextItem):
            self.setText('文本旋转 %d °' % (self.item.rotation()))
        else:
            self.setText('图元旋转 %d °' % (self.item.rotation()))

    def undo(self):
        self.item.setRotation(self.oldAngle)
        if isinstance(self.item, ArrowItem):
            self.setText('箭头旋转 %d °' % (self.item.rotation()))
        elif isinstance(self.item, RectItem):
            self.setText('矩形旋转 %d °' % (self.item.rotation()))
        elif isinstance(self.item, EllipseItem):
            self.setText('圆形旋转 %d °' % (self.item.rotation()))
        elif isinstance(self.item, PItem):
            self.setText('图片旋转 %d °' % (self.item.rotation()))
        elif isinstance(self.item, PItem_paste):
            self.setText('粘贴图片旋转 %d °' % (self.item.rotation()))
        elif isinstance(self.item, TextItem):
            self.setText('文本旋转 %d °' % (self.item.rotation()))
        else:
            self.setText('图元旋转 %d °' % (self.item.rotation()))


class itemDelCommand(QUndoCommand):
    def __init__(self, scene, item):
        super(itemDelCommand, self).__init__()
        self.scene = scene
        self.item = item
        if isinstance(self.item, ArrowItem):
            self.setText('删除箭头')
        elif isinstance(self.item, RectItem):
            self.setText('删除矩形')
        elif isinstance(self.item, EllipseItem):
            self.setText('删除圆形')
        elif isinstance(self.item, PItem):
            self.setText('删除图片')
        elif isinstance(self.item, PItem_paste):
            self.setText('删除粘贴图片')
        elif isinstance(self.item, TextItem):
            self.setText('删除文本')
        else:
            self.setText('删除图元')

    def redo(self):
        self.scene.removeItem(self.item)
        self.scene.update()

    def undo(self):
        self.scene.addItem(self.item)
        self.scene.update()

# 画板弹窗界面
class PaintBoard1(QWidget, painter):
    save_signal = pyqtSignal(object)

    def __init__(self, parent):
        super().__init__()
        self.setupUi(self)
        self.copiedItem = QByteArray()
        self.parentWin = parent
        self.undoStack = QUndoStack()
        self.undoStack.createUndoAction(self, '撤消')
        self.undoStack.createRedoAction(self, '恢复')
        undoView = QUndoView(self.undoStack)
        undoView.setMaximumSize(300, 16777215)
        self.verticalLayout.addWidget(undoView)
        self.undoAction = self.undoStack.createUndoAction(self, "Undo")
        self.undoAction.setShortcut(QKeySequence.Undo)
        self.redoAction = self.undoStack.createRedoAction(self, "Redo")
        self.redoAction.setShortcut(QKeySequence.Redo)
        self.addAction(self.undoAction)
        self.addAction(self.redoAction)

        self.graphics = GraphicView()
        self.scene = self.graphics.scene
        self.graphics.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        # 千万记得用addWidget(self.graphics)，而不是addWidget(addWidget)，不然传参数会有问题
        self.gridLayout_paintbox.addWidget(self.graphics)

        self.scene.itemClicked.connect(self.wc)
        self.scene.itemScaled.connect(self.itemscaled)

        self.pix = None
        self.pixfixed = None
        self.pw = None
        self.ph = None
        self.item = None

        # 获取颜色列表(字符串类型)
        # self.__colorList = QColor.colorNames()
        # 用各种颜色填充下拉列表
        # self.__fillColorList(self.comboBox_penColor)
        # self.comboBox_penColor.setEditable(True)
        # self.comboBox_penColor.setMaxVisibleItems(10)
        # self.comboBox_penColor.resize(4000, 300)

        # self.__fillWidthList(self.Pen_Thickness)

        # self.Pen_Thickness.setEditable(True)
        # self.Pen_Thickness.setMaxVisibleItems(10)
        # self.Pen_Thickness.resize(4000,300)

        ######### 这里是将QtDesigner的控件装载在自定义的类里面，并调用类的方法!!! #########
        ######### 事先应带入另外一个文件QtDesiner_ColorBoard.py ；并创建toolButton控件#########
        # self.stylebox = QtDesiner_ColorBoard.ColorCombox(self.toolButton)
        # # self.set_gridLayout.addWidget(self.stylebox, 0, 0, 0, 1)
        # self.stylebox.signal.connect(self.stylebox.createColorToolButtonIcon)
        # self.stylebox.signal.connect(self.on_PenColorChange)
        # self.stylebox.style_signal.connect(self.on_PenStyleChange)
        # self.stylebox.thick_signal.connect(self.on_PenThicknessChange)

        # 这里是将自定义类装进QtDesigner里面的GridLayout（"set_gridLayout"）
        self.colorbox = ColorCombox()
        self.set_gridLayout.addWidget(self.colorbox, 0, 1, 0, 1)

        self.colorbox.signal.connect(self.colorbox.createColorToolButtonIcon)
        self.colorbox.signal.connect(self.on_PenColorChange)
        self.colorbox.signal.connect(self.item_pen_color_changed)

        self.colorbox.thick_signal.connect(self.on_PenThicknessChange)
        self.colorbox.thick_signal.connect(self.item_pen_width_changed)

        self.colorbox.style_signal.connect(self.on_PenStyleChange)
        self.colorbox.style_signal.connect(self.item_pen_style_changed)

        self.scene.itemClicked.connect(self.itemcolorshow)

        #
        self.fillcolorbox = FillColorCombox()
        self.set_gridLayout.addWidget(self.fillcolorbox, 0, 2, 0, 1)
        self.fillcolorbox.signal.connect(self.fillcolorbox.createColorToolButtonIcon)
        self.fillcolorbox.signal.connect(self.on_BrushColorChange)
        self.fillcolorbox.signal.connect(self.item_brush_color_changed)

        # 裁剪功能
        self.tailor = QPushButton("裁剪")
        self.tailor.setIcon(QIcon("ICon/crop.png"))
        self.tailor.setIconSize(QSize(35, 35))
        self.tailor.setCheckable(True)
        self.tailor.setAutoExclusive(True)
        self.tailor.setStyleSheet("background-color:white;font:bold")
        self.tailor.setMinimumSize(30, 40)
        self.tailor.setFlat(True)
        self.set_gridLayout.addWidget(self.tailor, 0, 3, 0, 1)
        self.tailor.toggled.connect(self.item_tailor)
        self.tailor.setEnabled(False)
        self.scene.itemClicked.connect(self.item_islike_PItem)

        # 下拉菜单改变画笔颜色
        # 关联下拉列表的当前索引变更信号与函数on_PenColorChange
        # self.comboBox_penColor.currentIndexChanged.connect(self.on_PenColorChange)

        # 设置画笔粗细大小
        # self.Pen_Thickness.setMaximum(50)
        # self.Pen_Thickness.setMinimum(0)
        # self.Pen_Thickness.setValue(5)
        # self.Pen_Thickness.setSingleStep(1)
        # 关联spinBox值变化信号和函数on_PenThicknessChange
        # self.Pen_Thickness.currentIndexChanged.connect(self.on_PenThicknessChange)

        # 信号与槽
        self.Openfile_btn.clicked.connect(self.on_btn_Open_Clicked)
        self.Quit_btn.clicked.connect(self.on_btn_Quit_Clicked)
        self.Clear_btn.clicked.connect(self.clean_all)
        # self.Eraser_cbtn.clicked.connect(self.on_cbtn_Eraser_clicked)
        self.Save_btn.clicked.connect(self.on_btn_Save_Clicked)
        self.circle_btn.clicked.connect(self.on_circle_btn_clicked1)
        self.Free_pen_btn.clicked.connect(self.on_Free_pen_btn_clicked1)
        self.line_btn.clicked.connect(self.line_btn_clicked1)
        self.rect_btn.clicked.connect(self.on_rect_btn_clicked1)
        self.text_btn.clicked.connect(self.addText)
        self.pic_move_btn.clicked.connect(self.on_pic_move_btn_clicked)
        self.drawback_btn.clicked.connect(self.drawback)
        self.set_upper_btn.clicked.connect(self.item_up)
        self.set_lower_btn.clicked.connect(self.item_down)
        self.test.clicked.connect(self.item_rect_change)
        self.reload_btn.clicked.connect(self.reload_size)
        self.del_items_btn.clicked.connect(self.delete)
        self.width_lineEdit.returnPressed.connect(self.wh_change)
        self.height_lineEdit.returnPressed.connect(self.wh_change)
        self.test_save_btn.clicked.connect(self.test_save)
        self.test_open_btn.clicked.connect(self.test_open)
        self.print_btn.clicked.connect(self.my_paint_print)
        self.cut_btn.clicked.connect(self.cutitem)
        self.copy_btn.clicked.connect(self.copyitem)
        self.center()
        self.history_btn.clicked.connect(self.MyUndostackClear)

        self.scene.itemMoved.connect(self.onItemMoved)
        self.scene.itemAdded.connect(self.onAddItem)
        self.scene.itemResized.connect(self.onResizeItem)
        self.scene.itemRotated.connect(self.onItemRotated)
        self.scene.itemDeled.connect(self.onDelItem)

        self.wrapped = []
        menu = QMenu(self)
        for text, arg in (
                ("左排列", Qt.AlignLeft),
                ("右排列", Qt.AlignRight),
                ("顶排列", Qt.AlignTop),
                ("底排列", Qt.AlignBottom)):
            wrapper = functools.partial(self.setAlignment, arg)
            self.wrapped.append(wrapper)
            menu.addAction(text, wrapper)
        self.alignment_btn.setMenu(menu)

    def MyUndostackClear(self):
        self.undoStack.clear()

    def onResizeItem(self, item, oldRect, delta):
        self.undoStack.push(itemResizeCommand(item, oldRect, delta))

    def onAddItem(self, scene, item):
        self.undoStack.push(itemAddCommand(scene, item))

    def onItemMoved(self, item, pos):
        self.undoStack.push(itemMoveCommand(item, pos))

    def onItemRotated(self, item, angle):
        self.undoStack.push(itemRotateCommand(item, angle))

    def onDelItem(self, scene, item):
        self.undoStack.push(itemDelCommand(scene, item))

    def setAlignment(self, alignment):
        # Items are returned in arbitrary order
        items = self.scene.selectedItems()
        if len(items) <= 1:
            return
        # Gather coordinate data
        leftXs, rightXs, topYs, bottomYs = [], [], [], []
        for item in items:
            rect = item.sceneBoundingRect()
            leftXs.append(rect.x())
            rightXs.append(rect.x() + rect.width())
            topYs.append(rect.y())
            bottomYs.append(rect.y() + rect.height())
        # Perform alignment
        if alignment == Qt.AlignLeft:
            xAlignment = min(leftXs)
            for i, item in enumerate(items):
                item.moveBy(xAlignment - leftXs[i], 0)
        elif alignment == Qt.AlignRight:
            xAlignment = max(rightXs)
            for i, item in enumerate(items):
                item.moveBy(xAlignment - rightXs[i], 0)
        elif alignment == Qt.AlignTop:
            yAlignment = min(topYs)
            for i, item in enumerate(items):
                item.moveBy(0, yAlignment - topYs[i])
        elif alignment == Qt.AlignBottom:
            yAlignment = max(bottomYs)
            for i, item in enumerate(items):
                item.moveBy(0, yAlignment - bottomYs[i])

    def cutitem(self):
        try:
            item = self.selectedItem()
            if len(item) >= 1:
                for i in item:
                    self.copyitem()
                    self.scene.removeItem(i)
                    del i
        except Exception as e:
            print(e)

    def center(self):
        cp = QDesktopWidget().availableGeometry().center()
        qr = self.frameGeometry()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def on_open(self, filename):
        self.undoStack.clear()
        self.filename = filename
        fh = None
        try:
            fh = QFile(self.filename)
            if not fh.open(QIODevice.ReadOnly):
                raise IOError(str(fh.errorString()))
            items = self.scene.items()
            while items:
                item = items.pop()
                self.scene.removeItem(item)
                del item
            self.scene.clear()
            stream = QDataStream(fh)
            stream.setVersion(QDataStream.Qt_5_7)
            while not fh.atEnd():
                self.readItemFromStream(stream)

            self.undoStack.clear()

        except IOError as e:
            QMessageBox.warning(self, "打开出错",
                                "打开失败： {0}: {1}".format(self.filename, e))
        finally:
            if fh is not None:
                fh.close()
            try:
                del fh
                del items
                del stream
                del self.filename
                gc.collect()
            except Exception as e:
                print(e)

    def on_save(self, filename):
        t = QTime()
        t.start()
        self.filename = filename
        initial = self.scene.items()
        fh = None
        try:
            fh = QFile(self.filename)
            if not fh.open(QIODevice.WriteOnly):
                raise IOError(str(fh.errorString()))
            self.scene.clearSelection()
            stream = QDataStream(fh)
            stream.setVersion(QDataStream.Qt_5_7)
            if initial != []:
                for item in self.scene.items():
                    self.writeItemToStream(stream, item)
            else:
                item = None

            t1 = t.elapsed() / 1000
            # print("on_save:1", t1)
        except IOError as e:
            QMessageBox.warning(self, "保存失败",
                                "保存失败： {0}: {1}".format(self.filename, e))
        finally:
            if fh is not None:
                fh.close()
        del t
        del t1
        del fh
        del self.filename
        del stream
        del item
        gc.collect()

    def copyitem(self):

        item = self.selectedItem()
        # print(item)
        if item == []:
            return
        else:
            item = item[0]
            self.copiedItem.clear()
            self.pasteOffset = 10
            stream = QDataStream(self.copiedItem, QIODevice.WriteOnly)
            stream.setVersion(QDataStream.Qt_5_7)
            self.writeItemToStream(stream, item)
            # for i in item:
            #     self.copiedItem.clear()
            #     self.pasteOffset = 10
            #     stream = QDataStream(self.copiedItem, QIODevice.WriteOnly)
            #     stream.setVersion(QDataStream.Qt_5_7)
            #     self.writeItemToStream(stream, i)

    def pasteitem(self):
        try:
            stream = QDataStream(self.copiedItem, QIODevice.ReadOnly)
            self.readItemFromStream(stream, self.pasteOffset)
            self.pasteOffset += 10
        except Exception as e:
            print(e)

    def writeItemToStream(self, stream, item):
        # print("PaintBoard1:writeItemtostream")
        if isinstance(item, ArrowItem):
            stream.writeQString("ArrowItem")
            stream << item.pos() << QPointF(item.pos_src[0], item.pos_src[1]) << QPointF(item.pos_dst[0],
                                                                                         item.pos_dst[1]) << QColor(
                item.pen_color)
            stream.writeInt32(item.pen_style)
            stream.writeInt(item.pen_width)
        elif isinstance(item, RectItem):
            stream.writeQString("Rect")
            stream << item.pos() << item.rect() << QColor(item.brush_color) << QColor(item.pen_color)
            stream.writeInt32(item.pen_style)
            stream.writeInt(item.pen_width)
            stream.writeFloat(item.rotation())
        elif isinstance(item, EllipseItem):
            stream.writeQString("Ellipse")
            stream << item.pos() << item.rect() << QColor(item.brush_color) << QColor(item.pen_color)
            stream.writeInt32(item.pen_style)
            stream.writeInt(item.pen_width)
            stream.writeFloat(item.rotation())
        elif isinstance(item, PItem):
            stream.writeQString("PItem")
            stream << item.pos() << item.rect() << item.pix
            stream.writeFloat(item.rotation())
        elif isinstance(item, PItem_paste):
            stream.writeQString("PItem_paste")
            stream << item.pos() << item.rect() << item.pix
            stream.writeFloat(item.rotation())
        elif isinstance(item, TextItem):
            stream.writeQString("TextItem")
            stream << item.pos()
            stream.writeQString(item.toPlainText())
            stream << item.font()

    def readItemFromStream(self, stream, offset=0):
        # print("PaintBoard1:readItemtostream")
        position = QPointF()
        rect = QRectF()
        begin = QPointF()
        end = QPointF()
        brush_color = QColor()
        pen_color = QColor()
        type = stream.readQString()
        font = QFont()

        if type == "ArrowItem":
            stream >> position >> begin >> end >> pen_color
            style = stream.readInt32()
            width = stream.readInt()
            Ar = ArrowItem(self.scene, pen_color, width, style)
            Ar.set_src(begin.x() + offset, begin.y() + offset)
            Ar.set_dst(end.x() + offset, end.y() + offset)
            Ar.update()
            Ar.setPos(position)
            Ar.setZValue(0.1)
            self.scene.itemAdded.emit(self.scene, Ar)
            # self.scene.addItem(Ar)

        elif type == "Rect":
            stream >> position >> rect >> brush_color >> pen_color
            if offset:
                position += QPointF(offset, offset)
            style = stream.readInt32()
            width = stream.readInt()
            rotateangle = stream.readFloat()
            bx = RectItem(brush_color, style, pen_color, width, None, rect)
            bx.setTransformOriginPoint(rect.center())
            bx.setRotation(rotateangle)
            bx.setPos(position)
            bx.setZValue(0.1)
            self.scene.itemAdded.emit(self.scene, bx)
            # self.scene.addItem(bx)

        elif type == "Ellipse":
            stream >> position >> rect >> brush_color >> pen_color
            if offset:
                position += QPointF(offset, offset)
            style = stream.readInt32()
            width = stream.readInt()
            rotateangle = stream.readFloat()
            ex = EllipseItem(brush_color, style, pen_color, width, rect)
            ex.setTransformOriginPoint(rect.center())
            ex.setRotation(rotateangle)
            ex.setPos(position)
            ex.setZValue(0.1)
            self.scene.itemAdded.emit(self.scene, ex)
            # self.scene.addItem(ex)

        elif type == "PItem":
            pixmap1 = QPixmap()
            stream >> position >> rect >> pixmap1
            pic = pixmap1
            PI = PItem_paste(pic, position)
            rotateangle = stream.readFloat()
            if offset:
                position += QPointF(offset, offset)
            PI.setRect(rect)
            PI.setTransformOriginPoint(rect.center())
            PI.setRotation(rotateangle)
            PI.setPos(position)
            PI.setSelected(True)
            self.scene.itemAdded.emit(self.scene, PI)
            # self.scene.addItem(PI)

        elif type == "PItem_paste":
            pixmap1 = QPixmap()
            stream >> position >> rect >> pixmap1
            pic = pixmap1
            Ps = PItem_paste(pic, position)
            rotateangle = stream.readFloat()
            if offset:
                position += QPointF(offset, offset)
            Ps.setRect(rect)
            Ps.setTransformOriginPoint(rect.center())
            Ps.setRotation(rotateangle)
            Ps.setPos(position)
            Ps.setSelected(True)
            self.scene.itemAdded.emit(self.scene, Ps)
            # self.scene.addItem(Ps)


        else:
            stream >> position
            text = stream.readQString()
            stream >> font
            # print(text, font)
            ti = TextItemDlg()
            if offset:
                position += QPointF(offset, offset)
            ti.position = position
            ti.scene = self.scene
            ti.font = font
            ti.editor.setText(text)
            ti.accept()

    def test_open(self):
        self.filename = "./"
        path = (QFileInfo(self.filename).path()
                if self.filename else ".")
        fname, filetype = QFileDialog.getOpenFileName(self,
                                                      "打开文件", path,
                                                      "打开pgd文件 (*.pgd)")
        if not fname:
            return
        self.filename = fname
        fh = None
        try:
            fh = QFile(self.filename)
            if not fh.open(QIODevice.ReadOnly):
                raise IOError(str(fh.errorString()))
            items = self.scene.items()
            while items:
                item = items.pop()
                self.scene.removeItem(item)
                del item

            stream = QDataStream(fh)
            stream.setVersion(QDataStream.Qt_5_7)
            # magic = stream.readInt32()
            # if magic != MagicNumber:
            #     raise IOError("not a valid .pgd file")
            # fileVersion = stream.readInt16()
            # if fileVersion != FileVersion:
            #     raise IOError("unrecognised .pgd file version")
            while not fh.atEnd():
                self.readItemFromStream(stream)
        except IOError as e:
            QMessageBox.warning(self, "打开出错",
                                "打开失败： {0}: {1}".format(self.filename, e))
        finally:
            if fh is not None:
                fh.close()

    def test_save(self):
        path = "."
        fname, filetype = QFileDialog.getSaveFileName(self,
                                                      "文件保存", path,
                                                      "pgd文件 (*.pgd)")
        if not fname:
            return
        self.filename = fname
        fh = None
        try:
            fh = QFile(self.filename)
            if not fh.open(QIODevice.WriteOnly):
                raise IOError(str(fh.errorString()))
            self.scene.clearSelection()
            stream = QDataStream(fh)
            stream.setVersion(QDataStream.Qt_5_7)
            # stream.writeInt32(0x70616765)
            # stream.writeInt16(1)
            for item in self.scene.items():
                self.writeItemToStream(stream, item)
        except IOError as e:
            QMessageBox.warning(self, "保存失败",
                                "保存失败： {0}: {1}".format(self.filename, e))
        finally:
            if fh is not None:
                fh.close()

    def itemscaled(self, scaled):
        self.horizontalSlider.setValue(scaled * 100)
        self.scaled_label.setText(str("{}%".format(int(scaled * 100))))

    def item_islike_PItem(self, item):
        if item.type() == 4:
            self.tailor.setEnabled(True)
        else:
            self.tailor.setEnabled(False)

    def itemcolorshow(self, item):
        # print(item.pen_color,item.brush_color)
        if isinstance(item, QGraphicsRectItem) == True and item.type() != 4:
            self.colorbox.createColorToolButtonIcon(item.pen_color)
            self.fillcolorbox.createColorToolButtonIcon(item.brush_color)

    def item_tailor(self):
        try:
            if self.selectedItem() != None:
                # print(self.tailor.isChecked())
                if self.tailor.isChecked():
                    self.selectedItem()[0].tailor = True
                else:
                    self.selectedItem()[0].tailor = False
        except Exception as e:
            print(e)

    def item_brush_color_changed(self, color):
        if self.selectedItem() != None:
            for i in self.selectedItem():
                i.brush_color = color
                i.update()

    def item_pen_width_changed(self, width):
        if self.selectedItem() != None:
            for i in self.selectedItem():
                i.pen_width = width
                i.update()

    def item_pen_color_changed(self, color):
        if self.selectedItem() != None:
            for i in self.selectedItem():
                i.pen_color = color
                i.update()

    def item_pen_style_changed(self, style):
        if self.selectedItem() != None:
            for i in self.selectedItem():
                i.pen_style = style
                i.update()

    def wh_change(self):
        # print(self.selectedItem())
        if self.selectedItem() != None:
            for i in self.selectedItem():
                if isinstance(i, QGraphicsRectItem) == True:
                    oldRect = i.rect()
                    # print("old",oldRect)
                    if isinstance(i, QGraphicsRectItem) == True:
                        origin_w = int(i.rect().width())  # + 12
                        origin_h = int(i.rect().height())  # + 12
                        modified_w = int(float(self.width_lineEdit.text()))
                        modified_h = int(float(self.height_lineEdit.text()))
                        diff_w = modified_w - origin_w
                        diff_h = modified_h - origin_h
                        if diff_h == 0:
                            final_w = modified_w
                            final_h = final_w * (origin_h / origin_w)
                        else:
                            final_h = modified_h
                            final_w = final_h * (origin_w / origin_h)

                        self.width_lineEdit.setText(str(final_w))
                        self.height_lineEdit.setText(str(final_h))
                        # i.setRect(0, 0, final_w - 12, final_h - 12)

                        newRect = QRectF(oldRect.x(), oldRect.y(), final_w, final_h)
                        pointO = i.mapToScene(oldRect.center())
                        pointC = i.mapToScene(newRect.center())
                        self.delta = pointO - pointC

                        w = newRect.width()
                        h = newRect.height()
                        # self.scene.itemResized.emit(i, oldRect, delta)
                        self.m_localRect = QRectF(-w / 2, -h / 2, w, h)
                        i.setRect(self.m_localRect)
                        self.scene.itemResized.emit(i, oldRect, self.delta)
                        i.setTransformOriginPoint(self.m_localRect.center())
                        # i.moveBy(-self.delta.x(), -self.delta.y())
                        # i.setRect(0, 0, final_w, final_h)
                        # print("new",i.rect())

                        # self.scene.itemResized.emit(i, oldRect, delta)

    def keyPressEvent(self, event):
        # print(self.selectedItem()[0])
        if event.key() == Qt.Key_Delete:
            self.delete()
        if len(self.selectedItem()) >= 1 and isinstance(self.selectedItem()[0], QGraphicsRectItem) == True:
            if event.modifiers() == Qt.ShiftModifier:
                self.selectedItem()[0].keepratio = True
            else:
                self.keepratio = False

        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_C:
            self.copyitem()

        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_V:
            self.pasteitem()

        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_A:
            for it in self.scene.items():
                it.setSelected(True)
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_S:
            self.on_btn_Save_Clicked()
            self.parentWin.save_picture_to_table()
        if event.key() == Qt.Key_Escape:
            self.scene.clearSelection()

    def keyReleaseEvent(self, event):
        if len(self.selectedItem()) >= 1 and isinstance(self.selectedItem()[0], QGraphicsRectItem) == True:
            self.selectedItem()[0].keepratio = False

    def delete(self):
        items = self.scene.selectedItems()
        # if (len(items) and QMessageBox.question(self,
        # "删除",
        # "删除{0}个元素?".format(len(items)
        # ),
        # QMessageBox.Yes | QMessageBox.No) ==
        # QMessageBox.Yes):
        while items:
            item = items.pop()
            self.scene.itemDeled.emit(self.scene, item)
            # self.scene.removeItem(item)
            del item

    def my_paint_print(self):
        self.printer = QPrinter(QPrinter.HighResolution)
        self.printer.setPageSize(QPrinter.Letter)
        dialog = QPrintDialog(self.printer)
        if dialog.exec_():
            painter = QPainter(self.printer)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            self.scene.clearSelection()
            self.scene.render(painter)

    def reload_size(self):
        item = self.graphics.scene.selectedItems()
        if item == []:
            pass
        else:
            # if item[0].type() == 7:
            #     self.graphics.reload_size(item[0])
            # else:
            self.graphics.remove_to_origin(item[0])

    # 图片保存功能
    def on_btn_Save_Clicked(self):
        try:
            # savePath = QFileDialog.getSaveFileName(self, '保存图片', '.\\', '*.jpg;*.png')
            #
            # if savePath[0] == "":
            #     print("取消保存")
            #     return
            # pm=QPixmap(self.pixfixed.width(), self.pixfixed.height())
            self.scene.clearSelection()
            pm = QPixmap(900, 600)  # 注意，设置画布的大小为Myscene的大小，下边保存时才不会产生黑边

            pm.fill(Qt.white)  # 当区域没有Item时，保存图片不产生黑色区域

            # 设置绘图工具
            painter1 = QPainter(pm)
            painter1.setRenderHint(QPainter.Antialiasing)
            painter1.setRenderHint(QPainter.SmoothPixmapTransform)

            # 使打印长和宽与导入的Pixmap图片长宽匹配，不会产生黑边
            # self.graphics.render(painter1,QRectF(0,0,self.pixfixed.width(),self.pixfixed.height()),QRect(0,0,self.pixfixed.width(),self.pixfixed.height()))

            # 注意，大小设置与Myscene的大小一致，画布大小一致时，才真的不会产生黑边,原始：600,500
            self.graphics.render(painter1, QRectF(0, 0, 900, 600), QRect(0, 0, 900, 600))
            # QRect(0, 0, 600, 500))
            painter1.end()
            # pm.save(savePath[0])

            self.item = QTableWidgetItem()
            self.item.setFlags(Qt.ItemIsEnabled)  # 用户点击时表格时，图片被选中
            icon = QIcon(pm)
            self.item.setIcon(QIcon(icon))


        except Exception as e:
            print(e)

    def line_btn_clicked1(self, *type):
        type = "line"
        self.graphics.Shape(type)

    def wc(self, item):
        if item:
            width = int(item.boundingRect().width() - 12)
            height = int(item.boundingRect().height() - 12)
            self.width_lineEdit.setText(str(width))
            self.height_lineEdit.setText(str(height))

    # 记录鼠标选择的items
    def selectedItem(self):
        items = self.scene.selectedItems()
        if len(items) == 1:
            # return items[0]
            return items
        else:
            return items

    # 添加可变矩形
    def item_rect_change(self):

        self.scene.addItem(Rectangle(200, 150, 100, 100))

    # 上移一层(实际为置顶)
    def item_up(self):
        try:
            selected = self.scene.selectedItems()[0]
            overlapItems = selected.collidingItems()
            if self.selectedItem() == None:
                print("no item selected")
            else:
                zValue = 0
                for item in overlapItems:
                    if item.zValue() >= zValue:
                        zValue = item.zValue() + 0.1
                # print(zValue)
                selected.setZValue(zValue)
        except Exception as e:
            print(e)

    # 下移一层(实际为置底)
    def item_down(self):
        try:
            selected = self.scene.selectedItems()[0]
            overlapItems = selected.collidingItems()
            if self.selectedItem() == None:
                print("no item selected")
            else:
                zValue = 0
                for item in overlapItems:
                    if item.zValue() <= zValue:
                        zValue = item.zValue() - 0.1
                # print(zValue)
                selected.setZValue(zValue)
        except Exception as e:
            print(e)

    # 撤销上一个绘图的图元
    def drawback(self, *item):
        try:
            self.undoStack.undo()
        except Exception as e:
            print(e)

    # 设置图片移动
    def on_pic_move_btn_clicked(self, *type):
        type = "move"
        self.graphics.Shape(type)
        self.scene.clearSelection()

    # 添加文本
    def addText(self):
        try:
            dialog = TextItemDlg(position=QPoint(200, 200),
                                 scene=self.scene, parent=None)
            dialog.exec_()
        except Exception as e:
            print(e)

    # def on_Scene_size_clicked(self):
    #     w = self.scene.width()
    #     h = self.scene.height()
    #     p = self.width()
    #     q = self.height()
    #     s = self.size()

    def on_Free_pen_btn_clicked1(self, *shape):
        shape = "Free pen"
        self.graphics.Shape(shape)

    # 设置画圆圈
    def on_circle_btn_clicked1(self, *shape):  # 注意传入参数为文字时，为*加上变量，即“*变量”
        try:
            shape = "circle"
            self.graphics.Shape(shape)
        except Exception as e:
            print(e)

    def on_rect_btn_clicked1(self, *shape):
        shape = "rect"
        self.graphics.Shape(shape)

    # 打开图片功能
    def on_btn_Open_Clicked(self):
        try:
            openPath = QFileDialog.getOpenFileName(self, '打开图片', '', '*.png;*.jpg')
            # print(openPath)
            if openPath[0] == "":
                print("已取消")
                return
            filename = openPath[0]
            # print(filename)
            self.pix = QPixmap()
            self.pix.load(filename)
            # print(self.pix.width(),self.pix.height())
            # 对于图片长宽超过800,600的，缩放后完全显示
            self.pixfixed = self.pix.scaled(900, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            # self.scene.addPixmap(self.pixfixed)
            # print(self.pixfixed.width(),self.pixfixed.height())
            item1 = PItem(filename, 0, 0, 900, 600)
            item1.updateCoordinate()
            item1.moveBy(item1.rect().width() / 2, item1.rect().height() / 2)
            self.scene.itemAdded.emit(self.scene, item1)
            # self.scene.addItem(item1)

            item = QGraphicsPixmapItem(self.pixfixed)
            # item.setFlag(QGraphicsItem.ItemIsSelectable)
            item.setFlag(QGraphicsItem.ItemIsMovable)
            item.setZValue(-1)
            # self.pixrect=item.boundingRect()
            # self.scene.addItem(item)
            self.pw = self.pixfixed.width()
            self.ph = self.pixfixed.height()
        except Exception as e:
            print(e)

    # 退出画板主窗口
    def on_btn_Quit_Clicked(self):
        self.close()

    # combobox填充颜色序列
    def __fillColorList(self, comboBox):
        index_red = 0
        index = 0
        for color in self.__colorList:
            if color == "red":
                index_red = index
            index += 1
            pix = QPixmap(120, 30)
            pix.fill(QColor(color))
            comboBox.addItem(QIcon(pix), None)
            comboBox.setIconSize(QSize(100, 20))
            comboBox.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        comboBox.setCurrentIndex(index_red)

    def __fillWidthList(self, comboBox):
        color = Qt.black
        set_current_index = 1
        for i in range(15):
            pix = QPixmap(200, i + 2)
            pix.fill(QColor(color))
            comboBox.addItem(QIcon(pix), str(i + 1))
            comboBox.setIconSize(QSize(100, 20))
            comboBox.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        comboBox.setCurrentIndex(set_current_index)

    def on_BrushColorChange(self, color):
        self.graphics.ChangeBrushColor(color)

    # 画笔颜色更改
    def on_PenColorChange(self, color):
        print(color)
        self.graphics.ChangePenColor(color)

    def on_PenStyleChange(self, style):
        print("style:", style)
        self.graphics.ChangePenStyle(style)

    # 画笔粗细调整
    def on_PenThicknessChange(self, thick):
        # penThickness = int(self.Pen_Thickness.currentText())
        print("thick:", thick)
        self.graphics.ChangePenThickness(thick)

    # 橡皮擦粗细调整
    def on_EraserThicknessChange(self):
        EraserThickness = self.Eraser_thickness.value()
        self.scene.ChangeEraserThickness(EraserThickness)
        pm = QPixmap('circle.ico')
        r = self.Eraser_thickness.value()
        pm = pm.scaled(r, r, Qt.KeepAspectRatio)
        cursor = QCursor(pm)
        self.setCursor(cursor)

    # 清除图元
    def clean_all(self):
        try:
            self.scene.clear()
            self.undoStack.clear()
        except Exception as e:
            print(e)

    # def closeEvent(self, QCloseEvent):


class ColorCombox(QWidget):
    # 发送颜色更改信号，类型为Qcolor的object类型
    signal = pyqtSignal(object)
    thick_signal = pyqtSignal(object)
    style_signal = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        # 设置场景颜色，大小是6*10二维列表
        theme_colors = [
            [QColor(255, 255, 255, 255), QColor(0, 0, 0, 255), QColor(231, 230, 230, 255), QColor(64, 84, 106, 255),
             QColor(91, 155, 213, 255), QColor(237, 124, 48, 255), QColor(165, 165, 165, 255), QColor(255, 192, 0, 255),
             QColor(68, 114, 196, 255), QColor(112, 173, 71, 255)],

            [QColor(242, 242, 242, 255), QColor(127, 127, 127, 255), QColor(208, 206, 206, 255),
             QColor(214, 220, 228, 255),
             QColor(222, 235, 246, 255), QColor(251, 229, 213, 255), QColor(237, 237, 237, 237),
             QColor(255, 242, 204, 255), QColor(217, 226, 243, 255), QColor(226, 239, 217, 255)],

            [QColor(216, 216, 216, 255), QColor(89, 89, 89, 255), QColor(174, 171, 171, 255),
             QColor(173, 185, 202, 255),
             QColor(189, 215, 238, 255), QColor(247, 203, 172, 255), QColor(219, 219, 219, 255),
             QColor(254, 229, 153, 255), QColor(180, 198, 231, 255), QColor(197, 224, 179, 255)],

            [QColor(191, 191, 191, 255), QColor(63, 63, 63, 255), QColor(117, 112, 112, 255),
             QColor(132, 150, 176, 255),
             QColor(156, 195, 229, 255), QColor(244, 177, 131, 255), QColor(201, 201, 201, 255),
             QColor(255, 217, 101, 255), QColor(142, 170, 219, 255), QColor(168, 208, 141, 255)],

            [QColor(165, 165, 165, 255), QColor(38, 38, 38, 255), QColor(58, 56, 56, 255), QColor(50, 63, 79, 255),
             QColor(39, 112, 179, 255), QColor(197, 90, 17, 255), QColor(123, 123, 123, 255), QColor(191, 144, 0, 255),
             QColor(47, 84, 150, 255), QColor(83, 129, 53, 255)],

            [QColor(124, 124, 124, 255), QColor(12, 12, 12, 255), QColor(23, 22, 22, 255), QColor(34, 42, 53, 255),
             QColor(34, 81, 123, 255), QColor(124, 48, 2, 255), QColor(82, 82, 82, 255), QColor(127, 96, 0, 255),
             QColor(31, 56, 100, 255), QColor(55, 86, 35, 255)]
        ]

        # 设置基础颜色，大小是1*10一维列表
        basic_colors = [
            QColor(192, 0, 0, 255), QColor(255, 0, 0, 255), QColor(255, 192, 0, 255),
            QColor(255, 255, 0, 255), QColor(146, 208, 80, 255), QColor(0, 176, 80, 255),
            QColor(0, 176, 240, 255), QColor(0, 112, 192, 255), QColor(0, 32, 96, 255),
            QColor(112, 48, 160, 255)
        ]

        # 设置下拉框总按钮
        self.ColorCombox = QToolButton()
        self.ColorCombox.setAutoRaise(True)
        self.ColorCombox.setPopupMode(QToolButton.InstantPopup)  # 设置下拉框按钮按下时弹出菜单窗口
        self.ColorCombox.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # self.ColorCombox.setArrowType(Qt.DownArrow)
        self.ColorCombox.setText("形状轮廓")
        # self.ColorCombox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # self.ColorCombox.setMinimumSize(100, 30)
        self.ColorCombox.setAutoFillBackground(True)
        # 利用setStyleSheet设置QToolButton不显示下箭头
        # self.ColorCombox.setStyleSheet("QToolButton::menu-indicator {image: none;} QToolButton{font:bold 9pt '微软雅黑'}")
        self.ColorCombox.setStyleSheet(
            "QToolButton::menu-indicator {image: url(./down1.ico);} QToolButton{font:bold 9pt '微软雅黑'}")

        # 设置颜色下拉按钮的自定义图标Icon，这里是初始化
        qp = QPixmap(30, 30)  # 设置QPixmap场景大小
        qp.fill(Qt.transparent)
        self.pix = QPixmap()
        self.pix.load("ICon/pen_color.png")  # 这是画笔Icon，请替换成自己的图片或者利用QPainter画出笔也行
        pixfixed = self.pix.scaled(25, 25, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        target = QRect(0, 0, 25, 25)
        source = QRect(0, 0, 25, 25)
        painter = QPainter(qp)  # 设置QPainter在自己设的QPixmap上画
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(target, pixfixed, source)
        painter.fillRect(QRect(0, 22, 24, 5), Qt.red)
        painter.end()
        self.ColorCombox.setIcon(QIcon(qp))
        self.ColorCombox.setIconSize(QSize(30, 40))

        # 设置主题色标签
        title = QLabel(u"主题颜色")
        title.setStyleSheet("QLabel{background:lightgray;color:black;font:bold 8pt '微软雅黑'}")

        # 设置颜色6*10大小的主题颜色框架，利用QGridLayout布局放置颜色块
        pGridLayout = QGridLayout()
        pGridLayout.setAlignment(Qt.AlignCenter)
        pGridLayout.setContentsMargins(0, 0, 0, 0)
        pGridLayout.setSpacing(2)
        for i in range(6):
            for j in range(10):
                action = QAction()
                action.setData(theme_colors[i][j])
                action.setIcon(self.createColorIcon(theme_colors[i][j]))
                pBtnColor = QToolButton()
                pBtnColor.setFixedSize(QSize(20, 20))
                pBtnColor.setAutoRaise(True)
                pBtnColor.setDefaultAction(action)
                action.triggered.connect(self.OnColorChanged)
                pBtnColor.setToolTip(str(theme_colors[i][j].getRgb()))
                pGridLayout.addWidget(pBtnColor, i, j)

        # 设置标准色标签
        btitle = QLabel(u"标准色")
        btitle.setStyleSheet("QLabel{background:lightgray;color:black;font:bold 8pt '微软雅黑'}")

        # 设置颜色1*10大小的标准色框架，利用QGridLayout布局放置颜色块
        bGridLayout = QGridLayout()
        bGridLayout.setAlignment(Qt.AlignCenter)
        bGridLayout.setContentsMargins(0, 0, 0, 0)
        bGridLayout.setSpacing(2)
        for m in range(10):
            baction = QAction()
            baction.setData(basic_colors[m])
            baction.setIcon(self.createColorIcon(basic_colors[m]))
            bBtnColor = QToolButton()
            bBtnColor.setFixedSize(QSize(20, 20))
            bBtnColor.setAutoRaise(True)
            bBtnColor.setDefaultAction(baction)
            baction.triggered.connect(self.OnColorChanged)
            bBtnColor.setToolTip(str(basic_colors[m].getRgb()))
            bGridLayout.addWidget(bBtnColor, 0, m)

        # 设置分割水平线，利用QFrame
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)

        # 设置“无边框（透明色）”按钮功能
        pBtnTransparent = QToolButton()
        pBtnTransparent.setArrowType(Qt.NoArrow)
        pBtnTransparent.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        pBtnTransparent.setFixedSize(218, 20)
        pBtnTransparent.setAutoRaise(True)
        pBtnTransparent.setStyleSheet("QToolButton{font:bold 8pt '微软雅黑'}")
        pBtnTransparent.setText("无轮廓")
        pBtnTransparent.setIcon(QIcon("ICon/Frame.png"))
        pBtnTransparent.setIconSize(QSize(20, 20))
        pBtnTransparent.clicked.connect(self.set_pen_Transparent)

        # 设置“选择其他颜色”按钮功能
        othercolor_btn = QToolButton()
        othercolor_btn.setArrowType(Qt.NoArrow)
        othercolor_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        othercolor_btn.setFixedSize(218, 20)
        othercolor_btn.setAutoRaise(True)
        othercolor_btn.setIcon(QIcon("ICon/color.png"))
        othercolor_btn.setText(u"选择其他颜色")
        othercolor_btn.setIconSize(QSize(15, 15))
        othercolor_btn.setStyleSheet("QToolButton{font:bold 8pt '微软雅黑'}")
        othercolor_btn.clicked.connect(self.on_colorboard_show)

        # 将设置好的颜色框架，用QWidget包装好
        widget = QWidget()
        widget.setLayout(pGridLayout)
        bwidget = QWidget()
        bwidget.setLayout(bGridLayout)

        #  将上述设置的这些所有颜色框架，小组件窗口，用QVBoxLayout包装好
        pVLayout = QVBoxLayout()
        pVLayout.setSpacing(1)
        pVLayout.addWidget(title)
        pVLayout.addWidget(widget)
        pVLayout.addWidget(btitle)
        pVLayout.addWidget(bwidget)
        pVLayout.addWidget(line)
        pVLayout.addWidget(pBtnTransparent)
        pVLayout.addWidget(othercolor_btn)

        # 设置分割水平线，利用QFrame
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Plain)
        pVLayout.addWidget(line2)

        # 画笔粗细按钮
        self.thicknessbtn = QToolButton(self, text="粗细")
        self.thicknessbtn.setFixedSize(218, 20)
        self.thicknessbtn.setAutoRaise(True)
        self.thicknessbtn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # 自定义画笔粗细的QIcon
        thickIcon = QPixmap(30, 30)
        thickIcon.fill(Qt.white)
        thickpainter = QPainter(thickIcon)
        d = 5
        for k in range(4):
            thickpainter.setPen(QPen(Qt.black, k + 1, Qt.SolidLine))
            thickpainter.drawLine(0, (d + 1) * k + 5, 30, (d + 1) * k + 5)
        thickpainter.end()
        self.thicknessbtn.setIcon(QIcon(thickIcon))

        self.thicknessbtn.setPopupMode(QToolButton.InstantPopup)
        self.thicknessbtn.setArrowType(Qt.NoArrow)
        self.thicknessbtn.setStyleSheet(
            "QToolButton::menu-indicator {image: none;} QToolButton{font:bold 8pt '微软雅黑'}")

        tLayout = QVBoxLayout()
        tLayout.setSpacing(0)
        self.thicknessmenu = QMenu(self)
        for i in range(10):
            action = QAction(parent=self.thicknessmenu)
            action.setData(i)
            action.setIcon(self.set_width_Icon(i + 1))
            action.setText("{}磅".format(i + 1))
            pBtnWidth = QToolButton()
            pBtnWidth.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            pBtnWidth.setIconSize(QSize(100, 10))
            pBtnWidth.setStyleSheet(
                "QToolButton::menu-indicator {image: none;}")
            pBtnWidth.setAutoRaise(True)
            pBtnWidth.setDefaultAction(action)
            action.triggered.connect(self.OnWidthChanged)
            pBtnWidth.setToolTip(str("粗细:{}磅".format(i + 1)))
            tLayout.addWidget(pBtnWidth, i)
        self.twidget = QWidget()
        self.twidget.setLayout(tLayout)
        tVLayout = QVBoxLayout()
        tVLayout.setSpacing(1)
        tVLayout.setContentsMargins(1, 1, 1, 1)
        tVLayout.addWidget(self.twidget)
        self.thicknessmenu.setLayout(tVLayout)
        self.thicknessbtn.setMenu(self.thicknessmenu)
        self.thicknessmenu.showEvent = self.thickness_show
        pVLayout.addWidget(self.thicknessbtn)

        # 画笔虚线设定
        style = [Qt.NoPen, Qt.SolidLine, Qt.DashLine, Qt.DotLine,
                 Qt.DashDotLine, Qt.DashDotDotLine, Qt.CustomDashLine]
        name = ["无", "实线", "虚线", "点线", "点虚线", "点点虚线", "自定义"]

        # 画笔虚线按钮
        self.stylebtn = QToolButton(self, text="虚线")
        self.stylebtn.setFixedSize(218, 20)
        self.stylebtn.setAutoRaise(True)
        self.stylebtn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # 自定义画笔虚线的QIcon
        styleIcon = QPixmap(30, 30)
        styleIcon.fill(Qt.white)
        stylepainter = QPainter(styleIcon)
        f = 5
        for k in range(4):
            stylepainter.setPen(style[k + 1])
            stylepainter.drawLine(0, (f + 1) * k + 5, 30, (f + 1) * k + 5)
        stylepainter.end()
        self.stylebtn.setIcon(QIcon(styleIcon))
        self.stylebtn.setPopupMode(QToolButton.InstantPopup)
        self.stylebtn.setArrowType(Qt.NoArrow)
        self.stylebtn.setStyleSheet(
            "QToolButton::menu-indicator {image: none;} QToolButton{font:bold 8pt '微软雅黑'}")

        sLayout = QVBoxLayout()
        sLayout.setSpacing(0)
        self.stylemenu = QMenu(self)
        for j in range(7):
            saction = QAction(parent=self.stylemenu)
            saction.setData(style[j])
            saction.setIcon(self.set_style_Icon(style[j]))
            saction.setText(name[j])
            sBtnStyle = QToolButton()
            sBtnStyle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            sBtnStyle.setIconSize(QSize(100, 10))
            sBtnStyle.setStyleSheet(
                "QToolButton::menu-indicator {image: none;}")
            sBtnStyle.setAutoRaise(True)
            sBtnStyle.setDefaultAction(saction)
            saction.triggered.connect(self.OnStyleChanged)
            sBtnStyle.setToolTip(str(style[j]))
            sLayout.addWidget(sBtnStyle, j)

        self.swidget = QWidget()
        self.swidget.setLayout(sLayout)
        sVLayout = QVBoxLayout()
        sVLayout.setSpacing(1)
        sVLayout.setContentsMargins(1, 1, 1, 1)
        sVLayout.addWidget(self.swidget)
        self.stylemenu.setLayout(sVLayout)
        self.stylebtn.setMenu(self.stylemenu)
        self.stylemenu.showEvent = self.style_show
        pVLayout.addWidget(self.stylebtn)

        # 设置弹出菜单，菜单打上上述打包好所有颜色框架、窗口的pVLayout内容
        self.colorMenu = QMenu(self)
        self.colorMenu.setLayout(pVLayout)

        # 设置下拉框按钮菜单为上述菜单
        self.ColorCombox.setMenu(self.colorMenu)

        ### 将所有上述打包好的内，用本类设置的QWidget打包成窗口控件 ###
        alLayout = QVBoxLayout()
        alLayout.setSpacing(0)
        alLayout.addWidget(self.ColorCombox)
        self.setLayout(alLayout)

    ### ——以下为本类所用到的函数—— ###

    # 重设画笔粗细按钮按下后菜单出现在右侧
    def thickness_show(self, e):
        parent = self.colorMenu.pos()
        pos = self.thicknessbtn.geometry()
        m = self.thicknessmenu.geometry()
        w = pos.width()
        self.thicknessmenu.move(parent.x() + w + 13, m.y() - pos.height())

    # 重设画笔虚线按钮按下后菜单出现在右侧
    def style_show(self, e):
        parent = self.colorMenu.pos()
        pos = self.stylebtn.geometry()
        m = self.stylemenu.geometry()
        w = pos.width()
        self.stylemenu.move(parent.x() + w + 13, m.y() - pos.height())

    # 设置画笔粗细菜单栏中的所有Icon图标
    def set_width_Icon(self, width):
        color = Qt.black
        pix = QPixmap(100, width)
        pix.fill(QColor(color))
        return QIcon(pix)

    # 设置画笔粗细选中时的操作
    def OnWidthChanged(self):
        width = self.sender().data() + 1
        # print(width)
        self.thicknessmenu.close()
        self.colorMenu.close()
        self.thick_signal.emit(width)

    # 设置画笔虚线菜单栏中的所有Icon图标
    def set_style_Icon(self, style):
        # print(style)
        color = Qt.black
        pix = QPixmap(100, 6)
        pix.fill(Qt.white)
        painter = QPainter(pix)
        pp = QPen()
        pp.setStyle(style)
        pp.setColor(color)
        pp.setWidth(3)
        painter.setPen(pp)
        painter.drawLine(0, 3, 100, 3)
        painter.end()
        return QIcon(pix)

    # 设置画笔虚线形状选中时的操作
    def OnStyleChanged(self):
        style = self.sender().data()
        # print(Qt.PenStyle(style))
        self.stylemenu.close()
        self.colorMenu.close()
        self.style_signal.emit(style)

    # 用于设置QAction颜色块的槽函数
    def createColorIcon(self, color):
        pixmap = QPixmap(18, 18)
        pixmap.fill(QColor(color))
        return QIcon(pixmap)

    # 当透明色设置按钮按下后的槽函数
    def set_pen_Transparent(self):
        color = Qt.transparent
        self.colorMenu.close()
        self.signal.emit(color)

    # 设置颜色下拉按钮的自定义图标Icon，这里是颜色变化时改变图标下层矩形填充颜色
    def createColorToolButtonIcon(self, color):
        # print(color)
        qp = QPixmap(30, 30)
        qp.fill(Qt.transparent)
        self.pix = QPixmap()
        self.pix.load("ICon/pen_color.png")
        pixfix = self.pix.scaled(25, 25, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        target = QRect(0, 0, 25, 25)
        source = QRect(0, 0, 25, 25)
        painter = QPainter(qp)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(target, pixfix, source)
        painter.fillRect(QRect(0, 22, 24, 5), color)
        painter.end()
        self.ColorCombox.setIcon(QIcon(qp))
        self.ColorCombox.setIconSize(QSize(30, 40))

    # 当颜色色块QAction按下后的槽函数
    def OnColorChanged(self):
        color = self.sender().data()
        self.colorMenu.close()
        self.signal.emit(color)

    # 当其他颜色按钮按下时弹出Qt自带的颜色选择器
    def on_colorboard_show(self):
        color = QColorDialog.getColor(Qt.black, self)
        if color.isValid():
            self.signal.emit(color)
            return color


class FillColorCombox(QWidget):
    # 发送颜色更改信号，类型为Qcolor的object类型
    signal = pyqtSignal(object)
    thick_signal = pyqtSignal(object)
    style_signal = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        # 设置场景颜色，大小是6*10二维列表
        theme_colors = [
            [QColor(255, 255, 255, 255), QColor(0, 0, 0, 255), QColor(231, 230, 230, 255), QColor(64, 84, 106, 255),
             QColor(91, 155, 213, 255), QColor(237, 124, 48, 255), QColor(165, 165, 165, 255), QColor(255, 192, 0, 255),
             QColor(68, 114, 196, 255), QColor(112, 173, 71, 255)],

            [QColor(242, 242, 242, 255), QColor(127, 127, 127, 255), QColor(208, 206, 206, 255),
             QColor(214, 220, 228, 255),
             QColor(222, 235, 246, 255), QColor(251, 229, 213, 255), QColor(237, 237, 237, 237),
             QColor(255, 242, 204, 255), QColor(217, 226, 243, 255), QColor(226, 239, 217, 255)],

            [QColor(216, 216, 216, 255), QColor(89, 89, 89, 255), QColor(174, 171, 171, 255),
             QColor(173, 185, 202, 255),
             QColor(189, 215, 238, 255), QColor(247, 203, 172, 255), QColor(219, 219, 219, 255),
             QColor(254, 229, 153, 255), QColor(180, 198, 231, 255), QColor(197, 224, 179, 255)],

            [QColor(191, 191, 191, 255), QColor(63, 63, 63, 255), QColor(117, 112, 112, 255),
             QColor(132, 150, 176, 255),
             QColor(156, 195, 229, 255), QColor(244, 177, 131, 255), QColor(201, 201, 201, 255),
             QColor(255, 217, 101, 255), QColor(142, 170, 219, 255), QColor(168, 208, 141, 255)],

            [QColor(165, 165, 165, 255), QColor(38, 38, 38, 255), QColor(58, 56, 56, 255), QColor(50, 63, 79, 255),
             QColor(39, 112, 179, 255), QColor(197, 90, 17, 255), QColor(123, 123, 123, 255), QColor(191, 144, 0, 255),
             QColor(47, 84, 150, 255), QColor(83, 129, 53, 255)],

            [QColor(124, 124, 124, 255), QColor(12, 12, 12, 255), QColor(23, 22, 22, 255), QColor(34, 42, 53, 255),
             QColor(34, 81, 123, 255), QColor(124, 48, 2, 255), QColor(82, 82, 82, 255), QColor(127, 96, 0, 255),
             QColor(31, 56, 100, 255), QColor(55, 86, 35, 255)]
        ]

        # 设置基础颜色，大小是1*10一维列表
        basic_colors = [
            QColor(192, 0, 0, 255), QColor(255, 0, 0, 255), QColor(255, 192, 0, 255),
            QColor(255, 255, 0, 255), QColor(146, 208, 80, 255), QColor(0, 176, 80, 255),
            QColor(0, 176, 240, 255), QColor(0, 112, 192, 255), QColor(0, 32, 96, 255),
            QColor(112, 48, 160, 255)
        ]

        # 设置下拉框总按钮
        self.ColorCombox = QToolButton()
        self.ColorCombox.setAutoRaise(True)
        self.ColorCombox.setPopupMode(QToolButton.InstantPopup)  # 设置下拉框按钮按下时弹出菜单窗口
        self.ColorCombox.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # self.ColorCombox.setArrowType(Qt.DownArrow)
        self.ColorCombox.setText("形状填充")
        # self.ColorCombox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # self.ColorCombox.setMinimumSize(100, 30)
        self.ColorCombox.setAutoFillBackground(True)
        # 利用setStyleSheet设置QToolButton不显示下箭头
        # self.ColorCombox.setStyleSheet("QToolButton::menu-indicator {image: none;} QToolButton{font:bold 9pt '微软雅黑'}")
        self.ColorCombox.setStyleSheet(
            "QToolButton::menu-indicator {image: url(./down1.ico);} QToolButton{font:bold 9pt '微软雅黑'}")

        # 设置颜色下拉按钮的自定义图标Icon，这里是初始化
        qp = QPixmap(30, 30)  # 设置QPixmap场景大小
        qp.fill(Qt.transparent)
        self.pix = QPixmap()
        self.pix.load("ICon/filled.png")  # 这是填充Icon，请替换成自己的图片或者利用QPainter画出笔也行
        pixfix = self.pix.scaled(25, 25, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        target = QRect(0, 0, 25, 25)
        source = QRect(0, 0, 25, 25)
        painter = QPainter(qp)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(target, pixfix, source)
        painter.fillRect(QRect(0, 22, 24, 5), Qt.transparent)
        painter.end()
        self.ColorCombox.setIcon(QIcon(qp))
        self.ColorCombox.setIconSize(QSize(30, 40))

        # 设置主题色标签
        title = QLabel(u"主题颜色")
        title.setStyleSheet("QLabel{background:lightgray;color:black;font:bold 8pt '微软雅黑'}")

        # 设置颜色6*10大小的主题颜色框架，利用QGridLayout布局放置颜色块
        pGridLayout = QGridLayout()
        pGridLayout.setAlignment(Qt.AlignCenter)
        pGridLayout.setContentsMargins(0, 0, 0, 0)
        pGridLayout.setSpacing(2)
        for i in range(6):
            for j in range(10):
                action = QAction()
                action.setData(theme_colors[i][j])
                action.setIcon(self.createColorIcon(theme_colors[i][j]))
                pBtnColor = QToolButton()
                pBtnColor.setFixedSize(QSize(20, 20))
                pBtnColor.setAutoRaise(True)
                pBtnColor.setDefaultAction(action)
                action.triggered.connect(self.OnColorChanged)
                pBtnColor.setToolTip(str(theme_colors[i][j].getRgb()))
                pGridLayout.addWidget(pBtnColor, i, j)

        # 设置标准色标签
        btitle = QLabel(u"标准色")
        btitle.setStyleSheet("QLabel{background:lightgray;color:black;font:bold 8pt '微软雅黑'}")

        # 设置颜色1*10大小的标准色框架，利用QGridLayout布局放置颜色块
        bGridLayout = QGridLayout()
        bGridLayout.setAlignment(Qt.AlignCenter)
        bGridLayout.setContentsMargins(0, 0, 0, 0)
        bGridLayout.setSpacing(2)
        for m in range(10):
            baction = QAction()
            baction.setData(basic_colors[m])
            baction.setIcon(self.createColorIcon(basic_colors[m]))
            bBtnColor = QToolButton()
            bBtnColor.setFixedSize(QSize(20, 20))
            bBtnColor.setAutoRaise(True)
            bBtnColor.setDefaultAction(baction)
            baction.triggered.connect(self.OnColorChanged)
            bBtnColor.setToolTip(str(basic_colors[m].getRgb()))
            bGridLayout.addWidget(bBtnColor, 0, m)

        # 设置分割水平线，利用QFrame
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)

        # 设置“无边框（透明色）”按钮功能
        pBtnTransparent = QToolButton()
        pBtnTransparent.setArrowType(Qt.NoArrow)
        pBtnTransparent.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        pBtnTransparent.setFixedSize(218, 20)
        pBtnTransparent.setAutoRaise(True)
        pBtnTransparent.setStyleSheet("QToolButton{font:bold 8pt '微软雅黑'}")
        pBtnTransparent.setText("无填充")
        pBtnTransparent.setIcon(QIcon("ICon/Frame.png"))
        pBtnTransparent.setIconSize(QSize(20, 20))
        pBtnTransparent.clicked.connect(self.set_pen_Transparent)

        # 设置“选择其他颜色”按钮功能
        othercolor_btn = QToolButton()
        othercolor_btn.setArrowType(Qt.NoArrow)
        othercolor_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        othercolor_btn.setFixedSize(218, 20)
        othercolor_btn.setAutoRaise(True)
        othercolor_btn.setIcon(QIcon("ICon/color.png"))
        othercolor_btn.setText(u"选择其他颜色")
        othercolor_btn.setIconSize(QSize(15, 15))
        othercolor_btn.setStyleSheet("QToolButton{font:bold 8pt '微软雅黑'}")
        othercolor_btn.clicked.connect(self.on_colorboard_show)

        # 将设置好的颜色框架，用QWidget包装好
        widget = QWidget()
        widget.setLayout(pGridLayout)
        bwidget = QWidget()
        bwidget.setLayout(bGridLayout)

        #  将上述设置的这些所有颜色框架，小组件窗口，用QVBoxLayout包装好
        pVLayout = QVBoxLayout()
        pVLayout.setSpacing(1)
        pVLayout.addWidget(title)
        pVLayout.addWidget(widget)
        pVLayout.addWidget(btitle)
        pVLayout.addWidget(bwidget)
        pVLayout.addWidget(line)
        pVLayout.addWidget(pBtnTransparent)
        pVLayout.addWidget(othercolor_btn)

        # 设置弹出菜单，菜单打上上述打包好所有颜色框架、窗口的pVLayout内容
        self.colorMenu = QMenu(self)
        self.colorMenu.setLayout(pVLayout)

        # 设置下拉框按钮菜单为上述菜单
        self.ColorCombox.setMenu(self.colorMenu)

        ### 将所有上述打包好的内，用本类设置的QWidget打包成窗口控件 ###
        alLayout = QVBoxLayout()
        alLayout.setSpacing(0)
        alLayout.addWidget(self.ColorCombox)
        self.setLayout(alLayout)

    ### ——以下为本类所用到的函数—— ###

    # 重设画笔粗细按钮按下后菜单出现在右侧
    def thickness_show(self, e):
        parent = self.colorMenu.pos()
        pos = self.thicknessbtn.geometry()
        m = self.thicknessmenu.geometry()
        w = pos.width()
        self.thicknessmenu.move(parent.x() + w + 16, m.y() - pos.height())

    # 重设画笔虚线按钮按下后菜单出现在右侧
    def style_show(self, e):
        parent = self.colorMenu.pos()
        pos = self.stylebtn.geometry()
        m = self.stylemenu.geometry()
        w = pos.width()
        self.stylemenu.move(parent.x() + w + 16, m.y() - pos.height())

    # 设置画笔粗细菜单栏中的所有Icon图标
    def set_width_Icon(self, width):
        color = Qt.black
        pix = QPixmap(100, width)
        pix.fill(QColor(color))
        return QIcon(pix)

    # 设置画笔粗细选中时的操作
    def OnWidthChanged(self):
        width = self.sender().data() + 1
        # print(width)
        self.thicknessmenu.close()
        self.colorMenu.close()
        self.thick_signal.emit(width)

    # 设置画笔虚线菜单栏中的所有Icon图标
    def set_style_Icon(self, style):
        # print(style)
        color = Qt.black
        pix = QPixmap(100, 6)
        pix.fill(Qt.white)
        painter = QPainter(pix)
        pp = QPen()
        pp.setStyle(style)
        pp.setColor(color)
        pp.setWidth(3)
        painter.setPen(pp)
        painter.drawLine(0, 3, 100, 3)
        painter.end()
        return QIcon(pix)

    # 设置画笔虚线形状选中时的操作
    def OnStyleChanged(self):
        style = self.sender().data()
        # print(Qt.PenStyle(style))
        self.stylemenu.close()
        self.colorMenu.close()
        self.style_signal.emit(style)

    # 用于设置QAction颜色块的槽函数
    def createColorIcon(self, color):
        pixmap = QPixmap(18, 18)
        pixmap.fill(QColor(color))
        return QIcon(pixmap)

    # 当透明色设置按钮按下后的槽函数
    def set_pen_Transparent(self):
        color = Qt.transparent
        self.colorMenu.close()
        self.signal.emit(color)

    # 设置颜色下拉按钮的自定义图标Icon，这里是颜色变化时改变图标下层矩形填充颜色
    def createColorToolButtonIcon(self, color):
        # print(color)
        qp = QPixmap(30, 30)
        qp.fill(Qt.transparent)
        self.pix = QPixmap()
        self.pix.load("ICon/filled.png")
        pixfix = self.pix.scaled(25, 25, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        target = QRect(0, 0, 25, 25)
        source = QRect(0, 0, 25, 25)
        painter = QPainter(qp)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(target, pixfix, source)
        painter.fillRect(QRect(0, 22, 24, 5), color)
        painter.end()
        self.ColorCombox.setIcon(QIcon(qp))
        self.ColorCombox.setIconSize(QSize(30, 40))

    # 当颜色色块QAction按下后的槽函数
    def OnColorChanged(self):
        color = self.sender().data()
        self.colorMenu.close()
        self.signal.emit(color)

    # 当其他颜色按钮按下时弹出Qt自带的颜色选择器
    def on_colorboard_show(self):
        color = QColorDialog.getColor(Qt.black, self)
        if color.isValid():
            self.signal.emit(color)
            return color


# 本案例是利用QtDesigner拉出的控件，然后赋予控件功能为自定义的本类功能 #
class ThicknessCombox(QWidget):
    thick_signal = pyqtSignal(object)
    style_signal = pyqtSignal(object)

    def __init__(self, parent):  # 利用传入QtDesigner创建好的控件，把他的名字用“parent”名义传进来，代替self
        super().__init__()
        # 本案例是利用QtDesigner拉出的控件，然后赋予控件功能为自定义的本类功能
        pLayout = QVBoxLayout()
        pLayout.setSpacing(0)
        for i in range(10):
            action = QAction()
            action.setData(i)
            action.setIcon(self.set_width_Icon(i + 1))
            action.setText("{}磅".format(i + 1))
            pBtnWidth = QToolButton()
            pBtnWidth.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            pBtnWidth.setIconSize(QSize(100, 10))
            pBtnWidth.setStyleSheet(
                "QToolButton::menu-indicator {image: none;}")

            pBtnWidth.setAutoRaise(True)
            pBtnWidth.setDefaultAction(action)
            action.triggered.connect(self.OnWidthChanged)
            pBtnWidth.setToolTip(str("粗细:{}磅".format(i + 1)))
            pLayout.addWidget(pBtnWidth, i)

        style = [Qt.NoPen, Qt.SolidLine, Qt.DashLine, Qt.DotLine,
                 Qt.DashDotLine, Qt.DashDotDotLine, Qt.CustomDashLine]
        name = ["无", "实线", "虚线", "点线", "点虚线", "点点虚线", "自定义"]

        sLayout = QVBoxLayout()
        sLayout.setSpacing(0)

        for j in range(7):
            saction = QAction()
            saction.setData(style[j])
            saction.setIcon(self.set_style_Icon(style[j]))
            saction.setText(name[j])
            sBtnStyle = QToolButton()
            sBtnStyle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            sBtnStyle.setIconSize(QSize(100, 10))
            sBtnStyle.setStyleSheet(
                "QToolButton::menu-indicator {image: none;}")
            sBtnStyle.setAutoRaise(True)
            sBtnStyle.setDefaultAction(saction)
            saction.triggered.connect(self.OnStyleChanged)
            sBtnStyle.setToolTip(name[j])
            sLayout.addWidget(sBtnStyle, j)

        widget = QWidget()
        widget.setLayout(pLayout)

        swidget = QWidget()
        swidget.setLayout(sLayout)

        pVLayout = QVBoxLayout()
        pVLayout.setSpacing(1)
        pVLayout.setContentsMargins(1, 1, 1, 1)
        pVLayout.addWidget(widget)

        sVLayout = QVBoxLayout()
        sVLayout.setSpacing(1)
        sVLayout.setContentsMargins(1, 1, 1, 1)
        sVLayout.addWidget(swidget)

        # 设置弹出菜单，菜单打上上述打包好所有颜色框架、窗口的pVLayout内容
        self.thicknessmenu = QMenu(self)
        thick = QMenu(self.thicknessmenu)
        thick.setTitle("粗细")
        thick.setIcon(QIcon('ICon/noun_line weight.png'))
        self.thicknessmenu.addMenu(thick)
        thick.setLayout(pVLayout)
        style = QMenu(self.thicknessmenu)
        style.setTitle("画笔样式")
        style.setIcon(QIcon('ICon/noun_line weight.png'))
        self.thicknessmenu.addMenu(style)
        style.setLayout(sVLayout)

        # 设置下拉框按钮菜单为上述菜单
        # self.ThicknessCombox.setMenu(self.thicknessmenu)

        ### 将所有上述打包好的内，用本类设置的QWidget打包成窗口控件 ###
        alLayout = QVBoxLayout()
        alLayout.setSpacing(0)
        parent.setMenu(self.thicknessmenu)
        parent.setPopupMode(QToolButton.InstantPopup)
        parent.setLayout(alLayout)
        parent.setStyleSheet(
            "QToolButton::menu-indicator {image: none;}")

    def set_width_Icon(self, width):
        color = Qt.black
        pix = QPixmap(100, width)
        pix.fill(QColor(color))
        return QIcon(pix)

    def set_style_Icon(self, style):
        color = Qt.black
        pix = QPixmap(100, 6)
        pix.fill(Qt.white)
        painter = QPainter(pix)
        pp = QPen()
        pp.setStyle(style)
        pp.setColor(color)
        pp.setWidth(3)
        painter.setPen(pp)
        painter.drawLine(0, 3, 100, 3)
        painter.end()
        return QIcon(pix)

    def OnWidthChanged(self):
        width = self.sender().data() + 1
        self.thicknessmenu.close()
        self.thick_signal.emit(width)

    def OnStyleChanged(self):
        style = self.sender().data()
        self.thicknessmenu.close()
        self.style_signal.emit(style)


class MyScene(QGraphicsScene):  # 自定场景
    itemClicked = pyqtSignal(object)
    itemScaled = pyqtSignal(object)
    itemAdded = pyqtSignal(QGraphicsScene, QGraphicsItem)
    itemMoved = pyqtSignal(object, QPointF)
    itemResized = pyqtSignal(object, object, object)
    itemRotated = pyqtSignal(QGraphicsItem, float)
    itemDeled = pyqtSignal(QGraphicsScene, QGraphicsItem)

    def __init__(self):  # 初始函数
        super(MyScene, self).__init__(parent=None)  # 实例化QGraphicsScene
        self.setSceneRect(0, 0, 900, 600)  # 设置场景起始及大小，默认场景是中心为起始，不方便后面的代码

    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.drawRect(0, 0, 900, 600)


# 主程序代码：
def main():
    # QApplication.setAttribute(Qt.AA_EnableHighDpiScaling) 自适应DPI，缺点：会糊，所以不建议使用
    app = QApplication([])
    # 设置展示的style
    QApplication.setStyle(QStyleFactory.create("Fusion"))
    window = PaintBoard(parent=None)
    window.show()
    app.exec()


# Python真正执行代码
if __name__ == '__main__':
    main()
