import sys
import os
import re
import binascii
import time
from PIL import Image
from threading import Thread
from PyQt5.QtCore import QDir, QFile, QFileInfo, QSettings, Qt, QTextStream, QTimer, QThread, QRegExp, QElapsedTimer,QEvent, pyqtSignal 
from PyQt5.QtWidgets import QStyleFactory,QSizePolicy, QMainWindow, QDockWidget,QListWidget, QTextEdit,QGroupBox, QMenu, QPushButton, QAction, QApplication, QMessageBox, QFileDialog, QDialog, QCheckBox, QLabel, QComboBox,QGroupBox,QHBoxLayout, QGridLayout,QFormLayout,QVBoxLayout,QDialogButtonBox, QSplashScreen
from PyQt5.QtGui import  QIcon, QImage, QPainter, QPalette, QPixmap, QFont, QColor, QTextCharFormat, QSyntaxHighlighter
from PyQt5.QtPrintSupport import QPrintPreviewDialog, QPrintDialog
import webbrowser
try:
    import configparser
except:
    from six.moves import configparser

from shutil import copyfile

def str2bool(v):
  return str(v).lower() in ("yes", "true", "t", "1")

class ConvertImage(QThread):
    sec_signal = pyqtSignal(str)

    def __init__(self, parent=None, image_file='', var_name ='customChar', lcd_width = 64, lcd_height= 128, threshold= 0, invert= False, syntax='0', wrap= True):
        super(ConvertImage, self).__init__(parent)
        self.current_time = 0
        self.wrap = wrap
        self.threshold = threshold
        self.invert = invert
        self.syntax = syntax
        self.image_file = image_file
        self.lcd_width = lcd_width
        self.lcd_height = lcd_height
        self.var_name = var_name #self.get_declaration(image_file)
        self.newline_bit = 16
        self.is_version3 = False

        if (sys.version_info > (3, 0)):
            # Python 3 code in this block
            self.is_version3 = True
    
    def get_declaration(self,img_file):
        trim_name = str(img_file).split('\\')[-1:][0]
        trim_name = re.sub(' +', ' ', img_file)
        trim_name = trim_name.replace(' ', '_')
        return trim_name.replace('-', '').upper()


    def __del__(self):
        self.wait()

    def load_image(self, filename):
        """
        Loads an image, resized it to the target dimensions and returns it's data.
        """

        image = Image.open(filename, 'r')
        image = image.resize((self.lcd_width, self.lcd_height), Image.NEAREST)
        image_data = image.load()

        return image.size[0], image.size[1], image_data


    def get_pixel_intensity(self, pixel, max_value=255):
        """
        Gets the average intensity of a pixel.
        """
        intensity = 0

        # Pixel is multi channel
        if type(pixel) is list or type(pixel) is tuple:
            for channel_intensity in pixel:
                intensity += channel_intensity
            intensity /= len(pixel)
        # Pixel is single channel
        elif type(pixel) is int or type(pixel) is float:
            intensity = pixel
        # Pixel is magic
        else:
            raise ValueError('Not a clue what format the pixel data is: ' + str(type(pixel)))

        if self.invert:
            return max_value - intensity
        else:
            return intensity


    def get_average_pixel_intensity(self,width, height, pixel_data):
        """
        Gets the average intensity over all pixels.
        """

        avg_intensity = 0

        for x_idx in range(0, width):
            for y_idx in range(0, height):
                avg_intensity += self.get_pixel_intensity(pixel_data[x_idx, y_idx])

        avg_intensity = avg_intensity / (width * height)

        return avg_intensity


    def output_image_c_array(self,width, height, pixel_data, crossover):
        """
        Outputs the data in a C bitmap array format.
        """
        code = ''
        print ('{')

        for y_idx in range(0, height):
            next_line = ''
            next_value = 0

            for x_idx in range(0, width):
                if (x_idx % 8 == 0 or x_idx == width - 1) and x_idx > 0:
                    next_line += str('0x%0.2X' % next_value).lower() + ","
                    next_value = 0

                if self.get_pixel_intensity(pixel_data[x_idx, y_idx]) > crossover:
                    next_value += 2 ** (7 - (x_idx % 8))

            print (next_line)
            code = code +next_line            

        print ('};')
        self.sec_signal.emit(self.get_output(code))  # display code to text area


    def convert(self, image_file):
        """
        Runs an image conversion.
        """

        print (image_file)

        width, height, self.image_data = self.load_image(image_file)
        if self.threshold == 0:
            crossover_intensity = self.get_average_pixel_intensity(width, height, self.image_data)
        else:
            crossover_intensity = self.threshold
        self.output_image_c_array(width, height, self.image_data, crossover_intensity)



    def get_output(self, code):
        if self.syntax =='0':
            return "#include <LiquidCrystal.h>\n\nLiquidCrystal lcd(12, 11, 5, 4, 3, 2);\n\nbyte char%s[] = {\n%s\n};\n\nvoid setup(){\n    lcd.begin(86, 48);\n    lcd.write(byte(0));\n}\nvoid loop(){\n}\n" % ( self.var_name,code)
        elif self.syntax=='1':
            return "byte char%s[] = {\n%s\n};" % (self.var_name,code)
        else:
            return code
    

    def run(self):
        # this is a special fxn that's called with the start() fxn
        if os.path.isfile(self.image_file):
            # start of code variable declaration based from audio filename           
            code = ''
            try:
                self.convert(self.image_file)

            except Exception as ex:
                self.sec_signal.emit(str(ex))  # display code to text area
                print("Exception: %s" % ex)
            finally:
                pass
                      
        pass

class Highlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super(Highlighter, self).__init__(parent)

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor(0, 151, 156))
        #keywordFormat.setForeground(Qt.darkBlue)
        keywordFormat.setFontWeight(QFont.Bold)

        keywordPatterns = ["\\bchar\\b", "\\bclass\\b", "\\bconst\\b",
                "\\bdouble\\b", "\\benum\\b", "\\bexplicit\\b", "\\bfriend\\b",
                "\\binline\\b", "\\bint\\b", "\\blong\\b", "\\bnamespace\\b",
                "\\boperator\\b", "\\bprivate\\b", "\\bprotected\\b",
                "\\bpublic\\b", "\\bshort\\b", "\\bsignals\\b", "\\bsigned\\b",
                "\\bslots\\b", "\\bstatic\\b", "\\bstruct\\b",
                "\\btemplate\\b", "\\btypedef\\b", "\\btypename\\b",
                "\\bunion\\b", "\\bunsigned\\b", "\\bvirtual\\b", "\\bvoid\\b",
                "\\bvolatile\\b", "\\bPROGMEM\\b", "\\byte\\b"]

        self.highlightingRules = [(QRegExp(pattern), keywordFormat)
                for pattern in keywordPatterns]

        classFormat = QTextCharFormat()
        classFormat.setFontWeight(QFont.Bold)
        classFormat.setForeground(Qt.darkMagenta)
        self.highlightingRules.append((QRegExp("\\bQ[A-Za-z]+\\b"),
                classFormat))

        singleLineCommentFormat = QTextCharFormat()
        singleLineCommentFormat.setForeground(Qt.red)
        self.highlightingRules.append((QRegExp("//[^\n]*"),
                singleLineCommentFormat))

        self.multiLineCommentFormat = QTextCharFormat()
        self.multiLineCommentFormat.setForeground(Qt.red)

        quotationFormat = QTextCharFormat()
        quotationFormat.setForeground(Qt.darkGreen)
        self.highlightingRules.append((QRegExp("\".*\""), quotationFormat))

        notesFormat = QTextCharFormat()
        notesFormat.setForeground(Qt.red)
        self.highlightingRules.append((QRegExp("^Note.+"), notesFormat))

        labelFormat = QTextCharFormat()
        labelFormat.setForeground(Qt.blue)
        self.highlightingRules.append((QRegExp(r"\w+: "), labelFormat))

        datatypeFormat = QTextCharFormat()
        datatypeFormat.setForeground(Qt.darkGreen)
        self.highlightingRules.append((QRegExp("byte"), datatypeFormat))

        talkieFormat = QTextCharFormat()
        talkieFormat.setForeground(QColor(233, 115, 0))
        self.highlightingRules.append((QRegExp("LiquidCrystal"), talkieFormat))

        includeFormat = QTextCharFormat()
        includeFormat.setForeground(QColor(94, 109, 3))
        self.highlightingRules.append((QRegExp("^#include"), includeFormat))

        functionFormat = QTextCharFormat()
        functionFormat.setFontItalic(True)
        functionFormat.setForeground(Qt.blue)
        self.highlightingRules.append((QRegExp("\\b[A-Za-z0-9_]+(?=\\()"),
                functionFormat))

        self.commentStartExpression = QRegExp("/\\*")
        self.commentEndExpression = QRegExp("\\*/")

    def highlightBlock(self, text):
        for pattern, format in self.highlightingRules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)

        startIndex = 0
        if self.previousBlockState() != 1:
            startIndex = self.commentStartExpression.indexIn(text)

        while startIndex >= 0:
            endIndex = self.commentEndExpression.indexIn(text, startIndex)

            if endIndex == -1:
                self.setCurrentBlockState(1)
                commentLength = len(text) - startIndex
            else:
                commentLength = endIndex - startIndex + self.commentEndExpression.matchedLength()

            self.setFormat(startIndex, commentLength,
                    self.multiLineCommentFormat)
            startIndex = self.commentStartExpression.indexIn(text,
                    startIndex + commentLength)

class OptionDialog(QDialog):
    NumGridRows = 3
    NumButtons = 4

    def __init__(self, parent=None):
        super(OptionDialog, self).__init__(parent)
        self.init_variables()
        self.createThemesGroupBox()
        self.createGridGroupBox()
        self.createFormGroupBox()


        buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.horizontalGroupBox)
        mainLayout.addWidget(self.formGroupBox)
        mainLayout.addWidget(self.gridGroupBox)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)

        #self.changeStyle('Windows')
        self.setWindowTitle("Options")
        self.setWindowIcon(QIcon('images/convert.png'))
        self.selectionchange(self.output)

    def init_variables(self):
        self.output_formats = ["Arduino Syntax -Full","Arduino Syntax -Declaration","Plain Bytes"]

        self.config_global = configparser.ConfigParser()      
        self.dir_name = os.path.dirname(os.path.realpath(__file__))
        self.opts_preview = os.path.join(self.dir_name, "configs","preview")
        self.global_file = os.path.join(self.dir_name, "configs/global.ini")
        self.config_global.read(self.global_file)

        self.output= self.config_global.get('global', 'output')
        self.theme  = self.config_global.get('global', 'theme')
        self.wrap  = self.config_global.get('global', 'wrap')
        self.is_bin  = self.config_global.get('global', 'binary')
        

    def createThemesGroupBox(self):
        self.horizontalGroupBox = QGroupBox("Themes")
        self.horizontalGroupBox.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)#disabled auto stretching
        layout = QHBoxLayout()
        self.originalPalette = QApplication.palette()

        styleComboBox = QComboBox()
        styleComboBox.addItems(QStyleFactory.keys())
        styleComboBox.setCurrentIndex(styleComboBox.findText(self.theme))
        styleComboBox.activated[str].connect(self.changeStyle)

        styleLabel = QLabel("&Style:")
        styleLabel.setBuddy(styleComboBox)
        
        layout.addWidget(styleLabel)
        layout.addWidget(styleComboBox)

        self.horizontalGroupBox.setLayout(layout)

    def createGridGroupBox(self):
        self.gridGroupBox = QGroupBox("Ouput Preview")
        layout = QGridLayout()

        font = QFont()
        font.setFamily('Courier')
        font.setFixedPitch(True)
        font.setPointSize(8)

        self.smallEditor = QTextEdit()
        self.smallEditor.setPlainText("Tarsier Preview")
        self.smallEditor.setReadOnly(True)
        self.smallEditor.setFont(font)
        self.highlighter = Highlighter(self.smallEditor.document())

        layout.addWidget(self.smallEditor, 0, 2, 4, 1)

        #layout.setColumnStretch(1, 10)
        #layout.setColumnStretch(2, 20)
        self.gridGroupBox.setLayout(layout)

    def createFormGroupBox(self):
        self.formGroupBox = QGroupBox("Output")
        self.formGroupBox.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed) #disabled auto stretching
        layout = QFormLayout()
        self.cb = QComboBox()
        for f in self.output_formats:
            self.cb.addItem(f)
        self.cb.currentIndexChanged.connect(self.selectionchange)
        self.cb.setCurrentIndex(int(self.output))
        layout.addRow(QLabel("Formatting: "), self.cb)
        
        self.checkboxWrap = QCheckBox("Newline created every 16 byte in converted output. ")
        self.checkboxWrap.setChecked(str2bool(self.wrap))
        self.checkboxWrap.toggled.connect(self.check_changed)
        layout.addRow(QLabel("Wrapping"), self.checkboxWrap)
        
        self.checkboxBinary = QCheckBox("Check if you want Binary output type in byte conversion otherwise default Hex.")
        self.checkboxBinary.setChecked(str2bool(self.is_bin))
        self.checkboxBinary.toggled.connect(self.check_changed)
        layout.addRow(QLabel("Type"), self.checkboxBinary)

        self.formGroupBox.setLayout(layout)

    def selectionchange(self,i):
        self.output =str(i)
        self.opts_file = os.path.join(self.opts_preview, ("%s.txt" %i))
        if os.path.isfile(self.opts_file):
            f = open(self.opts_file, 'r')
            with f:
                data = f.read()
                self.smallEditor.setText(data)
        self.save_config()
        
    def check_changed(self):
        self.wrap = str(self.checkboxWrap.isChecked())
        self.is_bin = str(self.checkboxBinary.isChecked())
        self.save_config()

    def changeStyle(self, styleName):
        self.theme = styleName
        print (self.theme)
        self.save_config()
        QApplication.setStyle(QStyleFactory.create(self.theme))
        QApplication.setPalette(self.originalPalette)
        
    def save_config(self):        
        self.config_global.set('global', 'theme', self.theme)
        self.config_global.set('global', 'output', self.output)
        self.config_global.set('global', 'wrap', self.wrap)
        self.config_global.set('global', 'binary', self.is_bin)
        # Writing our configuration file
        with open(self.global_file, 'w') as configfile:
            self.config_global.write(configfile)
        pass
        
class PyTalkieWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.copiedtext = ""
        self.init_vars()
        self.init_config()
        self.init_vars()
        self.init_editor()
        self.init_ui()
        self.init_docks()

    def init_config(self):
        self.config_opts = configparser.ConfigParser()
        self.config_global = configparser.ConfigParser()
        self.config_menus = configparser.ConfigParser()
        self.config_tools = configparser.ConfigParser()
        self.dir_name = os.path.dirname(os.path.realpath(__file__))
        self.opts_file = os.path.join(self.dir_name, "configs/options.ini")
        self.menu_file = os.path.join(self.dir_name, "configs/menus.ini")
        self.tool_file = os.path.join(self.dir_name, "configs/toolbars.ini")
        self.global_file = os.path.join(self.dir_name, "configs/global.ini")

    def save_config(self):
        self.config_global.set('global', 'width', str(
            self.frameGeometry().width()))
        self.config_global.set('global', 'height', str(
            self.frameGeometry().height()))
        self.config_global.set('global', 'init_dir', self.lastOpenedFolder)
        self.config_global.set('global', 'image_file', self.image_filename)
        # Writing our configuration file
        with open(self.global_file, 'w') as configfile:
            self.config_global.write(configfile)
        pass
    
    def reinit_configs(self):
        self.config_global.read(self.global_file)
        self.lastOpenedFolder = self.config_global.get('global', 'init_dir')
        self.image_filename = self.config_global.get('global', 'image_file')       
        self.width = self.config_global.get('global', 'width')
        self.height = self.config_global.get('global', 'height')
        self.geometry = self.config_global.get('global', 'geometry')
        self.theme = self.config_global.get('global', 'theme')
        self.syntax = self.config_global.get('global', 'output')
        self.wrap = self.config_global.get('global', 'wrap')
        self.is_bin = self.config_global.get('global', 'binary')
        self.dithering = self.config_global.get('global', 'dithering')
        self.resize =  self.config_global.get('global', 'resize')
        self.convert_mono =  self.config_global.get('global', 'convert_mono')
        self.lcd_width = int(self.config_global.get('global', 'lcd_width'))
        self.lcd_height =  int(self.config_global.get('global', 'lcd_height'))

    def init_vars(self):
        self.threshold = 0
        self.scaleFactor = 0.0
        self.invert = False
        self.lcd_width = 84
        self.lcd_height = 48
        self.is_loading = False
        self.lastOpenedFolder = "C:\\"
        self.image_filename = ''
        self.var_name =''
        self.geometry = ''
        self.theme = ''
        self.syntax = ''
        self.wrap = True
        self.dithering = False
        self.resize = False
        self.convert_mono = False

    def init_editor(self):
        font = QFont()
        font.setFamily('Courier')
        font.setFixedPitch(True)
        font.setPointSize(8)

        self.textEdit = QTextEdit()
        self.setCentralWidget(self.textEdit)
        self.textEdit.setFont(font)
        self.highlighter = Highlighter(self.textEdit.document())

    def init_ui(self):    
        self.menus = {}
        self.config_menus.read(self.menu_file)
        menubar = self.menuBar()
        for section in self.config_menus.sections():
            topMenu = menubar.addMenu(section)
            for option in self.config_menus.options(section):
                menuLabel = self.config_menus.get(section, option)
                self.menus[option] = QAction(
                    QIcon('images/%s.png' % option), menuLabel, self)
                # self.menus[option].setShortcut('Ctrl+Q')
                self.menus[option].setStatusTip(menuLabel)
                self.menus[option].triggered.connect(
                    lambda checked, tag=option: self.do_clickEvent(checked, tag))
                topMenu.addAction(self.menus[option])

        self.toolbars = {}
        self.config_tools.read(self.tool_file)
        for section in self.config_tools.sections():
            topToolbar = self.addToolBar(section)
            for option in self.config_tools.options(section):
                toolLabel = self.config_tools.get(section, option)
                self.toolbars[option] = QAction(
                    QIcon('images/%s.png' % option), toolLabel, self)
                # self.menus[option].setShortcut('Ctrl+Q')
                self.toolbars[option].setStatusTip(toolLabel)
                self.toolbars[option].triggered.connect(
                    lambda checked, tag=option: self.do_clickEvent(checked, tag))
                topToolbar.addAction(self.toolbars[option])

        self.reinit_configs()

        self.statusBar()
        self.setGeometry(200, 200, int(self.width), int(self.height))
        self.setWindowTitle('Tarsier Image-LCD Converter')
        self.setWindowIcon(QIcon('images/marianz.bmp'))
        QApplication.setStyle(QStyleFactory.create(self.theme))

        self.set_details(self.image_filename)
        self.show()

        pass
    
    def init_docks(self):
        self.dock = QDockWidget("Image Preview", self)
        self.dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock.setMinimumWidth(200)
        self.dock.setMinimumHeight(200)
       
        self.imagePreview = QLabel()
        self.imagePreview.setBackgroundRole(QPalette.Base)
        self.imagePreview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.imagePreview.setScaledContents(True)
        self.dock.setWidget(self.imagePreview)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)

        self.dock = QDockWidget("Monochrome Preview", self)        
        self.dock.setMinimumWidth(200)
        self.dock.setMinimumHeight(200)

        self.imageMonoPreview = QLabel()
        self.imageMonoPreview.setBackgroundRole(QPalette.Base)
        self.imageMonoPreview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.imageMonoPreview.setScaledContents(True)

     
        self.dock.setWidget(self.imageMonoPreview)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)

        #self.imagePreview.setPixmap(QPixmap.fromImage(self.get_defaultImage()))

    def get_defaultImage(self):
        image = QImage('images/default.png')
        return image

    def set_monoimage(self, source_image):
        image_file = Image.open(source_image) # open colour image
        if str2bool(self.dithering) == True:
            image_file = image_file.convert('1') # convert image to black and white
        else:
            image_file = image_file.convert('1',dither=Image.NONE)
        
        self.basewidth = int(self.lcd_width)
        if str2bool(self.resize)== True:
            #wpercent = (self.basewidth / float(image_file.size[0]))
            #hsize = int((float(image_file.size[1]) * float(wpercent)))
            #image_file = image_file.resize((self.basewidth, hsize), Image.ANTIALIAS)
            image_file= image_file.resize((int(self.lcd_width), int(self.lcd_height)), Image.ANTIALIAS)

        image_file.save('images/result.bmp')
        result_image = os.path.join(self.dir_name,'images/result.bmp')

        image = QImage(result_image)
        self.imageMonoPreview.setPixmap(QPixmap.fromImage(image))

        if str2bool(self.convert_mono) == True:
            self.image_filename = result_image

    def do_clickEvent(self, checked, tag):
        if self.is_loading == True:
            return
        if tag == 'open':
            self.open_image()
            pass
        elif tag == 'convert':
            self.start_convert()
            pass
        elif tag == 'save':
            self.save()
            pass
        elif tag == 'option':
            self.option_dialog()
            pass
        elif tag=='copy':
            self.copy()
            pass
        elif tag == 'about':
            self.about()
            pass
        elif tag == 'print':
            self.print()
            pass
        elif tag == 'preview':
            self.print_preview()
            pass
        elif tag == 'exit':
            self.close()
            pass
        elif tag == 'qt':
            QApplication.instance().aboutQt()
            pass
        else:
            print(tag)
        pass

    def closeEvent(self, event):
        self.save_config()
        reply = QMessageBox.question(self, 'Exit',
                                     "Are you sure to quit?", QMessageBox.Yes |
                                     QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.statusBar().showMessage('Quiting...')
            event.accept()
        else:
            event.ignore()
            #self.save()
            #event.accept()

    def start_convert(self):
        if os.path.isfile(self.image_filename):
            # change the cursor
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.is_loading = True
            self._converter = ConvertImage(image_file= self.image_filename ,var_name=self.var_name, syntax=self.syntax, wrap= str2bool(self.wrap))
            self._converter.sec_signal.connect(self.textEdit.setText)
            self._converter.start()
            self._converter.wait()
            QApplication.restoreOverrideCursor()
            self.is_loading = False

    def convert_completed(self):
        if self.thread.is_alive():
            self.statusBar().showMessage("Converting %s" % self.image_filename )
        else:
            QApplication.restoreOverrideCursor()
            self.is_loading = False
            self.statusBar().showMessage('Ready...')

    def get_varName(self, filename):
        #trim_name = re.sub(' +', ' ', filename)
        filename_w_ext = os.path.basename(filename)
        filename, file_extension = os.path.splitext(filename_w_ext)
        trim_name = filename.replace(' ', '_')
        return trim_name.replace('-', '').upper()
    
    def open_image(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Open File", QDir.currentPath())
        if fileName:
            self.image_filename = fileName
            image = QImage(self.image_filename)
            if image.isNull():
                QMessageBox.information(self, "Image Viewer","Cannot load %s." % self.image_filename)
                return
            
            self.var_name = self.get_varName(self.image_filename)

            self.imagePreview.setPixmap(QPixmap.fromImage(image))
            width = QPixmap.fromImage(image).width
            self.scaleFactor = 1.0

            #self.printAct.setEnabled(True)
            #self.fitToWindowAct.setEnabled(True)
            #self.updateActions()

            #if not self.fitToWindowAct.isChecked():
            #    self.imagePreview.adjustSize()
            #self.imagePreview.adjustSize()

            self.set_details(self.image_filename)
            self.set_monoimage(self.image_filename)
           
    def set_details(self, full_filename):
        if os.path.isfile(full_filename):
            folder, filename = os.path.split(full_filename)
            file_details = "[Source Details]\n Size: %s\n Filename: %s\n Directory: %s\n FullPath: %s\n WrapOutput: %s\n" % (os.path.getsize(full_filename),filename,  folder,full_filename,self.wrap)
            file_details += "\nClick Convert to generate byte array of opened image file compatible for Arduino-NOKIA 3310/5110 LCD...\n\nNote: the bigger file size of audio file, the longer it takes to execute conversion."
            self.textEdit.setText(file_details)

    def save(self):
        data = self.textEdit.toPlainText()
        if data.strip():
            self.statusBar().showMessage('Add extension to file name')
            fname = QFileDialog.getSaveFileName(self, 'Save File', self.lastOpenedFolder,"All Files (*);;Text Files (*.txt);;Arduino Sketch (*.ino)")
            if fname and os.path.isfile(fname[0]):
                try:
                    file = open(fname[0], 'w')
                    file.write(data)
                    file.close()
                except:
                    pass

    def copy(self):
        self.copiedtext = self.textEdit.toPlainText()
        clipboard = QApplication.clipboard()
        clipboard.setText(self.copiedtext , mode=clipboard.Clipboard)
        event = QEvent(QEvent.Clipboard)
        QApplication.sendEvent(clipboard, event)

    def option_dialog(self):
        opt_dialog = OptionDialog(self)
        opt_dialog.setWindowModality(Qt.ApplicationModal)
        opt_dialog.resize(500,500)
        opt_dialog.exec_()
        self.reinit_configs()

    def print(self):
        try:
            dialog = QPrintDialog()
            if dialog.exec_() == QDialog.Accepted:
                self.textEdit.document().print_(dialog.printer())
        except:
            pass

    def print_preview(self):
        try:
            dialog = QPrintPreviewDialog()
            dialog.setWindowIcon(QIcon('images/convert.png'))
            dialog.paintRequested.connect(self.textEdit.print_)
            dialog.exec_()
        except:
            pass

    def about(self):
        QMessageBox.about(self, "About Image2LCDConverter",
                          "<b>Image2LCDConverter</b><br>"
                          "Version: <b>1.1.8101.99616</b><br><br>"
                          "Copyright  © <b> Tarsier 2018</b><br><br>"
                          "A simple image to LCD converter compatible<br>"
                          "to <b> Nokia 3310/5110 LCD </b> ")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    '''
    #Dark Fusion Theme
    app.setStyle('Fusion')
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53,53,53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(15,15,15))
    palette.setColor(QPalette.AlternateBase, QColor(53,53,53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53,53,53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
         
    palette.setColor(QPalette.Highlight, QColor(142,45,197).lighter())
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    '''

    # create splashscreen, use the pic in folder img/bee2.jpg
    splash_pix = QPixmap('images/splash.png')
    splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    # set the splash window flag, keep the window stay on tophint and frameless
    splash.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    splash.setEnabled(False)
    #splash.setMask(splash_pix.mask())
    # show the splashscreen
    splash.show()

    # create elapse timer to cal time
    timer = QElapsedTimer()
    timer.start()
    # we give 3 secs
    while timer.elapsed() < 3000 :
        app.processEvents()

    pywin = PyTalkieWindow()

     # call finish method to destory the splashscreen
    splash.finish(pywin)
    sys.exit(app.exec_())
